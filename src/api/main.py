"""
Основной FastAPI приложение для веб API и webhook'ов
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
import os

from utils.logger import app_logger
from src.ai.consultant_v2 import AmberAIConsultantV2
from src.payments.yukassa_client import YuKassaClient
from src.payments.webhook_handler import YuKassaWebhookHandler

# Создание FastAPI приложения
app = FastAPI(
    title="Amber AI Consultant API",
    description="API для ИИ консультанта янтарного магазина с полной автоматизацией заказов",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "health",
            "description": "Операции проверки здоровья системы",
        },
        {
            "name": "chat",
            "description": "Взаимодействие с ИИ консультантом",
        },
        {
            "name": "payments",
            "description": "Управление платежами",
        },
        {
            "name": "webhooks",
            "description": "Webhook endpoints для внешних сервисов",
        },
    ]
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация компонентов
ai_consultant = AmberAIConsultantV2()
yukassa_client = YuKassaClient()
webhook_handler = YuKassaWebhookHandler()


class ChatMessage(BaseModel):
    """Модель сообщения чата"""
    message: str
    user_id: int
    
    class Config:
        schema_extra = {
            "example": {
                "message": "Хочу купить кольцо за 8000 рублей",
                "user_id": 123456789
            }
        }


class PaymentRequest(BaseModel):
    """Модель запроса на создание платежа"""
    amount: float
    order_id: str
    description: str
    moysklad_order_id: str = None
    telegram_user_id: int = None
    
    class Config:
        schema_extra = {
            "example": {
                "amount": 8500.00,
                "order_id": "order_123",
                "description": "Янтарное кольцо",
                "moysklad_order_id": "ms_order_456",
                "telegram_user_id": 123456789
            }
        }


@app.get("/", tags=["health"])
async def root():
    """Корневая страница API"""
    return {
        "message": "Amber AI Consultant API v2",
        "description": "ИИ консультант с полной автоматизацией заказов",
        "status": "active",
        "version": "2.0.0",
        "features": [
            "Интеллектуальный диалог с клиентами",
            "Автоматизация заказов от запроса до оплаты",
            "Интеграция с МойСклад и AmoCRM",
            "Обработка платежей через ЮKassa",
            "Webhook обработка в реальном времени"
        ]
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        # Проверяем основные компоненты
        health_status = {
            "status": "healthy",
            "timestamp": int(__import__('time').time()),
            "components": {
                "ai_consultant": "ready" if ai_consultant else "error",
                "payment_system": "ready" if yukassa_client else "error",
                "webhook_handler": "ready" if webhook_handler else "error"
            },
            "integrations": {
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "moysklad": bool(os.getenv("MOYSKLAD_LOGIN")),
                "amocrm": bool(os.getenv("AMOCRM_ACCESS_TOKEN")),
                "yukassa": bool(os.getenv("YUKASSA_SHOP_ID"))
            }
        }
        
        # Определяем общий статус
        if all(status == "ready" for status in health_status["components"].values()):
            health_status["status"] = "healthy"
        else:
            health_status["status"] = "degraded"
            
        return health_status
    except Exception as e:
        app_logger.error(f"Ошибка health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.post("/chat", tags=["chat"])
async def chat_endpoint(message: ChatMessage):
    """
    Эндпоинт для общения с ИИ консультантом
    
    Поддерживает полную автоматизацию заказов:
    - Определение намерений клиента
    - Адаптивные уточнения
    - Подбор товаров
    - Оформление заказа
    - Расчет доставки
    - Выставление счета
    
    Args:
        message: Сообщение от пользователя
        
    Returns:
        Ответ ИИ консультанта с возможными действиями
    """
    try:
        app_logger.info(f"API запрос от пользователя {message.user_id}: {message.message[:100]}...")
        
        response = await ai_consultant.process_message(message.user_id, message.message)
        
        return {
            "response": response,
            "user_id": message.user_id,
            "timestamp": int(__import__('time').time()),
            "status": "success"
        }
        
    except Exception as e:
        app_logger.error(f"Ошибка в chat API: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@app.post("/payment/create", tags=["payments"])
async def create_payment(payment_request: PaymentRequest):
    """
    Создание платежа через ЮKassa
    
    Автоматически создает платеж с привязкой к заказу в МойСклад
    и пользователю Telegram для последующей обработки webhook'ов.
    
    Args:
        payment_request: Данные для создания платежа
        
    Returns:
        Данные о созданном платеже с URL для оплаты
    """
    try:
        app_logger.info(f"Создание платежа на сумму {payment_request.amount} для заказа {payment_request.order_id}")
        
        payment_result = await yukassa_client.create_payment(
            amount=payment_request.amount,
            order_id=payment_request.order_id,
            description=payment_request.description,
            moysklad_order_id=payment_request.moysklad_order_id,
            telegram_user_id=payment_request.telegram_user_id
        )
        
        if payment_result.get("success"):
            payment = payment_result["payment"]
            return {
                "success": True,
                "payment_id": payment["id"],
                "payment_url": payment["confirmation"]["confirmation_url"],
                "amount": payment["amount"]["value"],
                "currency": payment["amount"]["currency"],
                "status": payment["status"],
                "expires_at": payment.get("expires_at"),
                "order_id": payment_request.order_id
            }
        else:
            error_msg = payment_result.get("error", "Не удалось создать платеж")
            app_logger.error(f"Ошибка создания платежа: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
            
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Неожиданная ошибка создания платежа: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка при создании платежа")


@app.post("/webhook/yukassa", tags=["webhooks"])
async def yukassa_webhook(webhook_data: Dict):
    """
    Webhook для получения уведомлений от ЮKassa
    
    Автоматически обрабатывает события платежей:
    - payment.succeeded - успешная оплата
    - payment.canceled - отмена платежа
    - payment.waiting_for_capture - ожидание подтверждения
    
    При успешной оплате:
    - Обновляет статус заказа в МойСклад
    - Создает входящий платеж в МойСклад
    - Обновляет сделку в AmoCRM
    - Уведомляет клиента в Telegram
    
    Args:
        webhook_data: Данные события от ЮKassa
        
    Returns:
        Статус обработки webhook'а
    """
    try:
        # Передаем обработку в специализированный handler
        result = await webhook_handler.handle_webhook(webhook_data)
        
        if result.get("success"):
            return {
                "status": "processed",
                "event": webhook_data.get("event"),
                "payment_id": webhook_data.get("object", {}).get("id"),
                "message": result.get("message", "Webhook обработан успешно")
            }
        else:
            app_logger.warning(f"Webhook не обработан: {result.get('error')}")
            raise HTTPException(status_code=400, detail=result.get("error", "Ошибка обработки webhook"))
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Критическая ошибка обработки webhook: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@app.get("/metrics", tags=["health"])
async def metrics():
    """
    Метрики системы в формате Prometheus
    
    Returns:
        Основные метрики работы системы
    """
    try:
        # Простые метрики для мониторинга
        metrics_data = {
            "system_status": 1,
            "active_scenarios": len(getattr(ai_consultant, 'active_order_scenarios', {})),
            "components_healthy": 1 if all([
                ai_consultant,
                yukassa_client,
                webhook_handler
            ]) else 0,
            "integrations_configured": sum([
                1 if os.getenv("OPENAI_API_KEY") else 0,
                1 if os.getenv("MOYSKLAD_LOGIN") else 0,
                1 if os.getenv("AMOCRM_ACCESS_TOKEN") else 0,
                1 if os.getenv("YUKASSA_SHOP_ID") else 0
            ])
        }
        
        # Конвертируем в Prometheus format
        prometheus_output = []
        for key, value in metrics_data.items():
            prometheus_output.append(f"amber_ai_{key} {value}")
            
        return {"metrics": "\n".join(prometheus_output)}
        
    except Exception as e:
        app_logger.error(f"Ошибка получения метрик: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения метрик")


# Добавляем health check для webhook'ов
@app.get("/webhook/yukassa/health", tags=["webhooks"])
async def yukassa_webhook_health():
    """
    Проверка работоспособности webhook обработчика ЮKassa
    
    Returns:
        Статус готовности к обработке webhook'ов
    """
    try:
        webhook_status = {
            "status": "ready",
            "handler_initialized": bool(webhook_handler),
            "yukassa_configured": bool(os.getenv("YUKASSA_SHOP_ID") and os.getenv("YUKASSA_SECRET_KEY")),
            "webhook_secret_configured": bool(os.getenv("YUKASSA_WEBHOOK_SECRET")),
            "integrations_ready": {
                "moysklad": bool(webhook_handler.moysklad_client if webhook_handler else False),
                "amocrm": bool(webhook_handler.amocrm_client if webhook_handler else False)
            }
        }
        
        # Определяем общий статус
        if not all([
            webhook_status["handler_initialized"],
            webhook_status["yukassa_configured"]
        ]):
            webhook_status["status"] = "not_ready"
            
        return webhook_status
        
    except Exception as e:
        app_logger.error(f"Ошибка проверки webhook health: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    app_logger.info(f"🚀 Запуск Amber AI Consultant API v2.0 на {host}:{port}")
    app_logger.info("📋 Доступные endpoints:")
    app_logger.info("   • GET  / - Информация об API")
    app_logger.info("   • GET  /docs - Swagger документация")
    app_logger.info("   • GET  /health - Проверка здоровья системы")
    app_logger.info("   • POST /chat - Общение с ИИ консультантом")
    app_logger.info("   • POST /payment/create - Создание платежа")
    app_logger.info("   • POST /webhook/yukassa - Webhook ЮKassa")
    app_logger.info("   • GET  /metrics - Метрики системы")
    
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "False").lower() == "true",
        log_level="info"
    )