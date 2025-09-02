"""
Интеграция с ЮKassa для обработки платежей
"""
import os
import requests
import uuid
from typing import Dict, Optional
from utils.logger import app_logger


class YuKassaClient:
    """
    Клиент для работы с ЮKassa API
    """
    
    def __init__(self):
        """Инициализация клиента ЮKassa"""
        self.shop_id = os.getenv("YUKASSA_SHOP_ID")
        self.secret_key = os.getenv("YUKASSA_SECRET_KEY")
        self.base_url = "https://api.yookassa.ru/v3"
        
        app_logger.info("ЮKassa клиент инициализирован")
    
    async def create_payment(self, amount: float, description: str, 
                           customer_email: str = None, 
                           return_url: str = None) -> Optional[Dict]:
        """
        Создание платежа
        
        Args:
            amount: Сумма платежа
            description: Описание платежа
            customer_email: Email клиента
            return_url: URL для возврата после оплаты
            
        Returns:
            Данные о созданном платеже
        """
        try:
            url = f"{self.base_url}/payments"
            
            headers = {
                "Authorization": f"Basic {self._get_auth_header()}",
                "Content-Type": "application/json",
                "Idempotence-Key": str(uuid.uuid4())
            }
            
            payment_data = {
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url or "https://example.com/payment/success"
                },
                "capture": True,
                "description": description
            }
            
            # Добавляем email если указан
            if customer_email:
                payment_data["receipt"] = {
                    "customer": {
                        "email": customer_email
                    },
                    "items": [{
                        "description": description,
                        "quantity": "1",
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": "RUB"
                        },
                        "vat_code": 1
                    }]
                }
            
            response = requests.post(url, headers=headers, json=payment_data)
            response.raise_for_status()
            
            payment = response.json()
            app_logger.info(f"Создан платеж ЮKassa: {payment['id']}")
            
            return payment
            
        except Exception as e:
            app_logger.error(f"Ошибка создания платежа ЮKassa: {e}")
            return None
    
    async def get_payment_status(self, payment_id: str) -> Optional[str]:
        """
        Получение статуса платежа
        
        Args:
            payment_id: ID платежа
            
        Returns:
            Статус платежа
        """
        try:
            url = f"{self.base_url}/payments/{payment_id}"
            
            headers = {
                "Authorization": f"Basic {self._get_auth_header()}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            payment = response.json()
            status = payment.get("status")
            
            app_logger.info(f"Статус платежа {payment_id}: {status}")
            return status
            
        except Exception as e:
            app_logger.error(f"Ошибка получения статуса платежа: {e}")
            return None
    
    async def cancel_payment(self, payment_id: str) -> bool:
        """
        Отмена платежа
        
        Args:
            payment_id: ID платежа
            
        Returns:
            True если отмена прошла успешно
        """
        try:
            url = f"{self.base_url}/payments/{payment_id}/cancel"
            
            headers = {
                "Authorization": f"Basic {self._get_auth_header()}",
                "Content-Type": "application/json",
                "Idempotence-Key": str(uuid.uuid4())
            }
            
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            
            app_logger.info(f"Платеж {payment_id} отменен")
            return True
            
        except Exception as e:
            app_logger.error(f"Ошибка отмены платежа: {e}")
            return False
    
    def _get_auth_header(self) -> str:
        """
        Получение заголовка авторизации
        
        Returns:
            Base64 encoded строка для авторизации
        """
        import base64
        auth_string = f"{self.shop_id}:{self.secret_key}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        return auth_b64