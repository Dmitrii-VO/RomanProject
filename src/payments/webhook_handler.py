"""
Обработчик webhooks от ЮKassa
"""
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
from datetime import datetime
from utils.logger import app_logger
from src.payments.yukassa_client import YuKassaClient
from src.integrations.moysklad_client import MoySkladClient
from src.integrations.amocrm_client import AmoCRMClient


class YuKassaWebhookHandler:
    """
    Обработчик webhooks от ЮKassa для обновления заказов и сделок
    """
    
    def __init__(self):
        """Инициализация обработчика webhooks"""
        self.yukassa_client = YuKassaClient()
        self.moysklad_client = MoySkladClient()
        self.amocrm_client = AmoCRMClient()
        
        app_logger.info("YuKassaWebhookHandler инициализирован")
    
    async def handle_payment_webhook(self, request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
        """
        Основной обработчик webhook от ЮKassa
        
        Args:
            request: HTTP запрос с webhook
            background_tasks: Фоновые задачи FastAPI
            
        Returns:
            HTTP ответ для ЮKassa
        """
        try:
            # Читаем тело запроса
            body = await request.body()
            
            # Получаем подпись из заголовков
            signature = request.headers.get("Authorization")
            if not signature:
                app_logger.error("Отсутствует подпись в webhook")
                raise HTTPException(status_code=400, detail="Missing signature")
            
            # Убираем префикс из подписи
            if signature.startswith("sha256="):
                signature = signature[7:]
            
            # Проверяем подпись webhook
            if not self.yukassa_client.verify_webhook(body, signature):
                app_logger.error("Неверная подпись webhook")
                raise HTTPException(status_code=403, detail="Invalid signature")
            
            # Парсим JSON данные
            try:
                webhook_data = json.loads(body.decode())
            except json.JSONDecodeError as e:
                app_logger.error(f"Ошибка парсинга JSON webhook: {e}")
                raise HTTPException(status_code=400, detail="Invalid JSON")
            
            # Обрабатываем webhook в фоновой задаче
            background_tasks.add_task(self._process_webhook_data, webhook_data)
            
            # Возвращаем успешный ответ ЮKassa
            return JSONResponse(
                status_code=200,
                content={"status": "success", "message": "Webhook received"}
            )
            
        except HTTPException:
            raise
        except Exception as e:
            app_logger.error(f"Критическая ошибка обработки webhook: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _process_webhook_data(self, webhook_data: Dict[str, Any]):
        """
        Обрабатывает данные webhook в фоновом режиме
        
        Args:
            webhook_data: Данные webhook от ЮKassa
        """
        try:
            # Парсим данные платежа
            parsed_data = self.yukassa_client.parse_webhook(webhook_data)
            
            if not parsed_data:
                app_logger.error("Не удалось распарсить данные webhook")
                return
            
            event_type = parsed_data.get("event_type")
            payment_id = parsed_data.get("payment_id")
            payment_status = parsed_data.get("status")
            order_id = parsed_data.get("order_id")
            
            app_logger.info(f"Обработка webhook: {event_type}, платеж: {payment_id}, статус: {payment_status}")
            
            # Обрабатываем различные типы событий
            if event_type == "payment.succeeded":
                await self._handle_payment_success(parsed_data)
            elif event_type == "payment.canceled":
                await self._handle_payment_cancellation(parsed_data)
            elif event_type == "payment.waiting_for_capture":
                await self._handle_payment_waiting(parsed_data)
            else:
                app_logger.info(f"Необрабатываемый тип события: {event_type}")
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки данных webhook: {e}")
    
    async def _handle_payment_success(self, payment_data: Dict[str, Any]):
        """
        Обрабатывает успешную оплату
        
        Args:
            payment_data: Данные платежа
        """
        try:
            payment_id = payment_data.get("payment_id")
            amount = payment_data.get("amount")
            metadata = payment_data.get("metadata", {})
            
            # Получаем ID заказа в МойСклад из metadata
            moysklad_order_id = metadata.get("moysklad_order_id")
            telegram_user_id = metadata.get("telegram_user_id")
            
            app_logger.info(f"✅ Успешная оплата: платеж {payment_id}, заказ МойСклад {moysklad_order_id}, сумма {amount}₽")
            
            # Главный процесс: обрабатываем платеж в МойСклад
            if moysklad_order_id:
                result = await self.moysklad_client.process_payment_webhook(
                    moysklad_order_id=moysklad_order_id,
                    payment_amount=amount,
                    payment_id=payment_id,
                    telegram_user_id=int(telegram_user_id) if telegram_user_id and telegram_user_id.isdigit() else None
                )
                
                if result.get("success"):
                    app_logger.info(f"✅ МойСклад: заказ {moysklad_order_id} обновлен, платеж создан")
                    
                    # Обновляем сделку в AmoCRM
                    if telegram_user_id and telegram_user_id.isdigit():
                        await self._update_amocrm_deal_status(
                            int(telegram_user_id),
                            "paid",
                            f"✅ {result.get('message', 'Оплата получена')}\n💰 Сумма: {amount}₽\n🆔 Платеж: {payment_id}"
                        )
                    
                    # TODO: Отправить уведомление клиенту в Telegram
                    # message = result.get('message', 'Оплата получена, заказ готов к отправке')
                    # await self._send_telegram_notification(telegram_user_id, message)
                    
                    app_logger.info(f"🎉 Платеж {payment_id} полностью обработан")
                else:
                    app_logger.error(f"❌ Ошибка обработки платежа в МойСклад: {result.get('error')}")
            else:
                app_logger.error(f"❌ Отсутствует moysklad_order_id в metadata платежа {payment_id}")
            
        except Exception as e:
            app_logger.error(f"❌ Критическая ошибка обработки успешной оплаты: {e}")
    
    async def _handle_payment_cancellation(self, payment_data: Dict[str, Any]):
        """
        Обрабатывает отмену платежа
        
        Args:
            payment_data: Данные платежа
        """
        try:
            payment_id = payment_data.get("payment_id")
            order_id = payment_data.get("order_id")
            
            app_logger.info(f"Отмена платежа: {payment_id}, заказ {order_id}")
            
            # Обновляем статус заказа в МойСклад
            if order_id:
                await self._update_moysklad_order_status(
                    order_id,
                    "cancelled",
                    f"Платеж отменен, ЮKassa платеж {payment_id}"
                )
            
            # Обновляем сделку в AmoCRM
            telegram_user_id = payment_data.get("metadata", {}).get("telegram_user_id")
            if telegram_user_id:
                await self._update_amocrm_deal_status(
                    telegram_user_id,
                    "cancelled", 
                    f"❌ Платеж отменен\\nПлатеж ЮKassa: {payment_id}\\nЗаказ: {order_id}"
                )
            
            app_logger.info(f"Отмена платежа {payment_id} обработана")
            
        except Exception as e:
            app_logger.error(f"Ошибка обработки отмены платежа: {e}")
    
    async def _handle_payment_waiting(self, payment_data: Dict[str, Any]):
        """
        Обрабатывает платеж в ожидании подтверждения
        
        Args:
            payment_data: Данные платежа
        """
        try:
            payment_id = payment_data.get("payment_id") 
            order_id = payment_data.get("order_id")
            
            app_logger.info(f"Платеж ожидает подтверждения: {payment_id}, заказ {order_id}")
            
            # Обновляем статус в системах
            if order_id:
                await self._update_moysklad_order_status(
                    order_id,
                    "payment_pending",
                    f"Ожидается подтверждение платежа {payment_id}"
                )
            
            telegram_user_id = payment_data.get("metadata", {}).get("telegram_user_id")
            if telegram_user_id:
                await self._update_amocrm_deal_status(
                    telegram_user_id,
                    "payment_pending",
                    f"⏳ Платеж ожидает подтверждения\\nПлатеж ЮKassa: {payment_id}\\nЗаказ: {order_id}"
                )
            
        except Exception as e:
            app_logger.error(f"Ошибка обработки ожидания платежа: {e}")
    
    async def _update_moysklad_order_status(self, order_id: str, status: str, note: str) -> bool:
        """
        Обновляет статус заказа в МойСклад
        
        Args:
            order_id: ID заказа в МойСклад
            status: Новый статус
            note: Комментарий
            
        Returns:
            True если успешно обновлено
        """
        try:
            # Здесь должна быть логика обновления заказа в МойСклад
            # Пока оставляем заглушку, так как точный API зависит от реализации MoySkladClient
            
            app_logger.info(f"Попытка обновления заказа {order_id} в МойСклад: {status} - {note}")
            
            # Обновляем статус через MoySkladClient
            result = await self.moysklad_client.update_order_status(order_id, status, note)
            return result.get("success", False)
            
        except Exception as e:
            app_logger.error(f"Ошибка обновления статуса заказа в МойСклад: {e}")
            return False
    
    async def _update_amocrm_deal_status(self, telegram_user_id: int, status: str, note: str):
        """
        Обновляет статус сделки в AmoCRM
        
        Args:
            telegram_user_id: ID пользователя Telegram
            status: Новый статус
            note: Примечание
        """
        try:
            # Добавляем примечание к сделке
            await self.amocrm_client.add_note_to_lead(
                telegram_user_id,  # Используем как lead_id
                note
            )
            
            # Обновляем статус сделки (если есть соответствующий метод)
            # TODO: Добавить метод update_deal_status в AmoCRMClient если нужно
            
            app_logger.info(f"Обновлен статус сделки в AmoCRM для пользователя {telegram_user_id}: {status}")
            
        except Exception as e:
            app_logger.error(f"Ошибка обновления статуса сделки в AmoCRM: {e}")


# Создаем глобальный обработчик
webhook_handler = YuKassaWebhookHandler()


def setup_webhook_routes(app: FastAPI):
    """
    Настраивает маршруты для webhooks в FastAPI приложении
    
    Args:
        app: Экземпляр FastAPI приложения
    """
    
    @app.post("/webhooks/yukassa")
    async def yukassa_webhook(request: Request, background_tasks: BackgroundTasks):
        """Endpoint для webhooks от ЮKassa"""
        return await webhook_handler.handle_payment_webhook(request, background_tasks)
    
    @app.get("/webhooks/yukassa/test")
    async def yukassa_webhook_test():
        """Тестовый endpoint для проверки доступности webhooks"""
        return {
            "status": "ok",
            "service": "yukassa_webhooks",
            "timestamp": datetime.now().isoformat()
        }
    
    app_logger.info("Webhook маршруты ЮKassa настроены: POST /webhooks/yukassa")


# Пример использования с FastAPI
if __name__ == "__main__":
    import uvicorn
    
    app = FastAPI(title="ЮKassa Webhooks", version="1.0.0")
    setup_webhook_routes(app)
    
    # Запуск для тестирования
    uvicorn.run(app, host="0.0.0.0", port=8000)