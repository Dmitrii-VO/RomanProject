"""
Клиент для работы с API ЮKassa
"""
import os
import uuid
import base64
import hashlib
import hmac
import aiohttp
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from utils.logger import app_logger


class YuKassaClient:
    """
    Клиент для интеграции с ЮKassa API
    
    Документация: https://yookassa.ru/developers/api
    """
    
    def __init__(self):
        """Инициализация клиента ЮKassa"""
        # API настройки
        self.shop_id = os.getenv("YUKASSA_SHOP_ID", "test_shop_id")
        self.secret_key = os.getenv("YUKASSA_SECRET_KEY", "test_secret_key")
        self.webhook_secret = os.getenv("YUKASSA_WEBHOOK_SECRET", "test_webhook_secret")
        
        # API endpoints
        self.base_url = "https://api.yookassa.ru/v3"
        self.test_base_url = "https://api.yookassa.ru/v3"  # Тот же URL для тестирования
        
        # Используем тестовый режим по умолчанию
        self.is_test_mode = os.getenv("YUKASSA_TEST_MODE", "true").lower() == "true"
        
        # Создаем Basic Auth заголовок
        credentials = f"{self.shop_id}:{self.secret_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
            "Idempotence-Key": ""  # Будет заполняться для каждого запроса
        }
        
        # Настройки по умолчанию
        self.currency = "RUB"
        self.default_payment_methods = ["bank_card", "sberbank", "yoo_money", "qiwi", "sbp"]
        
        # Конфигурация НДС
        self.tax_system_code = int(os.getenv("YUKASSA_TAX_SYSTEM", "1"))  # 1 - ОСН
        self.vat_code = int(os.getenv("YUKASSA_VAT_CODE", "2"))  # 2 - НДС 20%
        
        app_logger.info(f"ЮKassa клиент инициализирован (тест: {self.is_test_mode})")
    
    async def create_payment(
        self,
        amount: float,
        order_id: str,
        description: str,
        customer_email: Optional[str] = None,
        customer_phone: Optional[str] = None,
        return_url: Optional[str] = None,
        payment_methods: Optional[List[str]] = None,
        items: Optional[List[Dict]] = None,
        moysklad_order_id: Optional[str] = None,
        telegram_user_id: Optional[int] = None
    ) -> Dict:
        """
        Создает платеж в ЮKassa
        
        Args:
            amount: Сумма платежа в рублях
            order_id: Уникальный ID заказа
            description: Описание платежа
            customer_email: Email клиента
            customer_phone: Телефон клиента  
            return_url: URL для возврата после оплаты
            payment_methods: Разрешенные способы оплаты
            items: Товары для фискализации
            
        Returns:
            Данные созданного платежа
        """
        try:
            # Генерируем уникальный ключ идемпотентности
            idempotence_key = str(uuid.uuid4())
            
            # Подготавливаем данные платежа
            payment_data = {
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": self.currency
                },
                "description": description,
                "metadata": {
                    "order_id": order_id,
                    "moysklad_order_id": moysklad_order_id or order_id,
                    "telegram_user_id": str(telegram_user_id) if telegram_user_id else None,
                    "created_at": datetime.now().isoformat()
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url or "https://example.com/payment/success"
                },
                "capture": True,  # Автоматическое списание
                "save_payment_method": False  # Не сохраняем карту
            }
            
            # Добавляем информацию о клиенте если есть
            if customer_email or customer_phone:
                payment_data["recipient"] = {}
                if customer_email:
                    payment_data["recipient"]["email"] = customer_email
                if customer_phone:
                    payment_data["recipient"]["phone"] = customer_phone
            
            # Ограничиваем способы оплаты если указано
            if payment_methods:
                payment_data["payment_method_data"] = {
                    "type": payment_methods[0] if len(payment_methods) == 1 else None
                }
            
            # Добавляем товары для фискализации (54-ФЗ)
            if items and self._should_send_receipt():
                payment_data["receipt"] = self._prepare_receipt(items, customer_email, customer_phone)
            
            # Устанавливаем заголовок идемпотентности
            headers = self.headers.copy()
            headers["Idempotence-Key"] = idempotence_key
            
            # Выполняем запрос к ЮKassa
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/payments",
                    headers=headers,
                    json=payment_data
                ) as response:
                    
                    response_data = await response.json()
                    
                    if response.status == 200:
                        app_logger.info(f"Платеж создан: {response_data['id']}, сумма: {amount}₽")
                        return {
                            "success": True,
                            "payment_id": response_data["id"],
                            "payment_url": response_data["confirmation"]["confirmation_url"],
                            "status": response_data["status"],
                            "amount": amount,
                            "currency": self.currency,
                            "description": description,
                            "order_id": order_id
                        }
                    else:
                        app_logger.error(f"Ошибка создания платежа: {response.status} - {response_data}")
                        return {
                            "success": False,
                            "error": response_data.get("description", "Неизвестная ошибка"),
                            "error_code": response_data.get("code", "unknown")
                        }
                        
        except Exception as e:
            app_logger.error(f"Исключение при создании платежа: {e}")
            return {
                "success": False,
                "error": f"Техническая ошибка: {e}",
                "error_code": "technical_error"
            }
    
    async def get_payment_status(self, payment_id: str) -> Dict:
        """
        Получает статус платежа
        
        Args:
            payment_id: ID платежа в ЮKassa
            
        Returns:
            Информация о статусе платежа
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/payments/{payment_id}",
                    headers=self.headers
                ) as response:
                    
                    if response.status == 200:
                        payment_data = await response.json()
                        
                        return {
                            "success": True,
                            "payment_id": payment_data["id"],
                            "status": payment_data["status"],
                            "paid": payment_data.get("paid", False),
                            "amount": float(payment_data["amount"]["value"]),
                            "currency": payment_data["amount"]["currency"],
                            "created_at": payment_data["created_at"],
                            "metadata": payment_data.get("metadata", {}),
                            "payment_method": payment_data.get("payment_method", {}),
                            "cancellation_details": payment_data.get("cancellation_details")
                        }
                    else:
                        app_logger.error(f"Ошибка получения статуса платежа: {response.status}")
                        return {
                            "success": False,
                            "error": "Не удалось получить статус платежа"
                        }
                        
        except Exception as e:
            app_logger.error(f"Ошибка получения статуса платежа: {e}")
            return {
                "success": False,
                "error": f"Техническая ошибка: {e}"
            }
    
    async def cancel_payment(self, payment_id: str, reason: str = "cancelled_by_merchant") -> Dict:
        """
        Отменяет платеж
        
        Args:
            payment_id: ID платежа
            reason: Причина отмены
            
        Returns:
            Результат отмены
        """
        try:
            idempotence_key = str(uuid.uuid4())
            headers = self.headers.copy()
            headers["Idempotence-Key"] = idempotence_key
            
            cancel_data = {
                "reason": reason
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/payments/{payment_id}/cancel",
                    headers=headers,
                    json=cancel_data
                ) as response:
                    
                    if response.status == 200:
                        app_logger.info(f"Платеж {payment_id} отменен")
                        return {"success": True, "status": "cancelled"}
                    else:
                        error_data = await response.json()
                        app_logger.error(f"Ошибка отмены платежа: {error_data}")
                        return {
                            "success": False,
                            "error": error_data.get("description", "Ошибка отмены")
                        }
                        
        except Exception as e:
            app_logger.error(f"Ошибка отмены платежа: {e}")
            return {"success": False, "error": f"Техническая ошибка: {e}"}
    
    def verify_webhook(self, body: bytes, signature: str) -> bool:
        """
        Проверяет подпись webhook от ЮKassa
        
        Args:
            body: Тело запроса в байтах
            signature: Подпись из заголовка
            
        Returns:
            True если подпись валидна
        """
        try:
            # Вычисляем HMAC SHA256
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            
            # Сравниваем подписи
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            app_logger.error(f"Ошибка проверки подписи webhook: {e}")
            return False
    
    def parse_webhook(self, webhook_data: Dict) -> Dict:
        """
        Парсит данные webhook от ЮKassa
        
        Args:
            webhook_data: Данные webhook
            
        Returns:
            Обработанные данные события
        """
        try:
            event_type = webhook_data.get("event")
            payment_data = webhook_data.get("object", {})
            
            parsed_data = {
                "event_type": event_type,
                "payment_id": payment_data.get("id"),
                "status": payment_data.get("status"),
                "paid": payment_data.get("paid", False),
                "amount": float(payment_data.get("amount", {}).get("value", 0)),
                "currency": payment_data.get("amount", {}).get("currency"),
                "metadata": payment_data.get("metadata", {}),
                "created_at": payment_data.get("created_at"),
                "captured_at": payment_data.get("captured_at"),
                "payment_method": payment_data.get("payment_method", {}),
                "order_id": payment_data.get("metadata", {}).get("order_id")
            }
            
            app_logger.info(f"Webhook получен: {event_type}, платеж: {parsed_data['payment_id']}")
            
            return parsed_data
            
        except Exception as e:
            app_logger.error(f"Ошибка парсинга webhook: {e}")
            return {}
    
    def _should_send_receipt(self) -> bool:
        """Определяет, нужно ли отправлять чек (54-ФЗ)"""
        # В реальном проекте это должно зависеть от настроек магазина
        return os.getenv("YUKASSA_SEND_RECEIPT", "true").lower() == "true"
    
    def _prepare_receipt(
        self, 
        items: List[Dict], 
        email: Optional[str] = None, 
        phone: Optional[str] = None
    ) -> Dict:
        """
        Подготавливает данные чека для фискализации
        
        Args:
            items: Список товаров
            email: Email покупателя
            phone: Телефон покупателя
            
        Returns:
            Данные чека
        """
        receipt = {
            "customer": {},
            "items": [],
            "tax_system_code": self.tax_system_code
        }
        
        # Контактные данные покупателя
        if email:
            receipt["customer"]["email"] = email
        if phone:
            receipt["customer"]["phone"] = phone
        
        # Обработка товаров
        for item in items:
            receipt_item = {
                "description": item.get("name", "Товар"),
                "quantity": str(item.get("quantity", 1)),
                "amount": {
                    "value": f"{item.get('price', 0):.2f}",
                    "currency": self.currency
                },
                "vat_code": self.vat_code,
                "payment_mode": "full_payment",  # Полная оплата
                "payment_subject": "commodity"   # Товар
            }
            receipt["items"].append(receipt_item)
        
        return receipt
    
    def format_payment_info(self, payment_data: Dict) -> str:
        """
        Форматирует информацию о платеже для показа клиенту
        
        Args:
            payment_data: Данные платежа
            
        Returns:
            Отформатированная строка
        """
        if not payment_data.get("success"):
            return f"❌ Ошибка создания платежа: {payment_data.get('error', 'Неизвестная ошибка')}"
        
        amount = payment_data["amount"]
        description = payment_data.get("description", "Заказ")
        payment_url = payment_data.get("payment_url", "")
        
        return f"""💳 **Счет для оплаты создан**

📄 Описание: {description}
💰 Сумма: **{amount:,.0f} ₽**
🔗 Ссылка для оплаты: {payment_url}

✅ Доступные способы оплаты:
• Банковская карта (Visa, Mastercard, МИР)
• СБП (Система быстрых платежей)
• Яндекс.Деньги, Qiwi
• Сбербанк Онлайн

⏰ Счет действителен 24 часа
🔒 Оплата защищена ЮKassa"""

    def get_test_card_data(self) -> Dict:
        """
        Возвращает данные тестовых карт для проверки платежей
        
        Returns:
            Словарь с тестовыми картами
        """
        return {
            "successful_payment": {
                "number": "5555555555554444",
                "expiry": "12/24", 
                "cvv": "123",
                "description": "Успешный платеж"
            },
            "failed_payment": {
                "number": "5555555555554477",
                "expiry": "12/24",
                "cvv": "123", 
                "description": "Неуспешный платеж"
            },
            "3ds_payment": {
                "number": "5555555555554495",
                "expiry": "12/24",
                "cvv": "123",
                "description": "Платеж с 3-D Secure"
            }
        }