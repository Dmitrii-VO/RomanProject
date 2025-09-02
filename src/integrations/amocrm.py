"""
Интеграция с AmoCRM для управления клиентами и сделками
"""
import os
import requests
from typing import Dict, Optional
from utils.logger import app_logger


class AmoCRMClient:
    """
    Клиент для работы с AmoCRM API
    """
    
    def __init__(self):
        """Инициализация клиента AmoCRM"""
        self.client_id = os.getenv("AMOCRM_CLIENT_ID")
        self.client_secret = os.getenv("AMOCRM_CLIENT_SECRET")
        self.redirect_uri = os.getenv("AMOCRM_REDIRECT_URI")
        self.auth_code = os.getenv("AMOCRM_AUTH_CODE")
        
        self.base_url = "https://your-domain.amocrm.ru/api/v4"  # TODO: Настроить домен
        self.access_token = None
        
        app_logger.info("AmoCRM клиент инициализирован")
    
    async def get_access_token(self) -> bool:
        """
        Получение access token
        
        Returns:
            True если токен получен успешно
        """
        try:
            url = f"{self.base_url}/oauth2/access_token"
            
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "authorization_code",
                "code": self.auth_code,
                "redirect_uri": self.redirect_uri
            }
            
            response = requests.post(url, json=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            app_logger.info("Access token для AmoCRM получен")
            return True
            
        except Exception as e:
            app_logger.error(f"Ошибка получения токена AmoCRM: {e}")
            return False
    
    async def create_contact(self, name: str, phone: str = None, telegram_id: str = None) -> Optional[int]:
        """
        Создание контакта в AmoCRM
        
        Args:
            name: Имя контакта
            phone: Телефон
            telegram_id: Telegram ID
            
        Returns:
            ID созданного контакта
        """
        try:
            if not self.access_token:
                await self.get_access_token()
            
            url = f"{self.base_url}/contacts"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            contact_data = [{
                "name": name,
                "custom_fields_values": []
            }]
            
            # Добавляем телефон если есть
            if phone:
                contact_data[0]["custom_fields_values"].append({
                    "field_code": "PHONE",
                    "values": [{"value": phone}]
                })
            
            # Добавляем Telegram ID
            if telegram_id:
                contact_data[0]["custom_fields_values"].append({
                    "field_code": "IM",
                    "values": [{"value": f"telegram_{telegram_id}"}]
                })
            
            response = requests.post(url, headers=headers, json=contact_data)
            response.raise_for_status()
            
            result = response.json()
            contact_id = result["_embedded"]["contacts"][0]["id"]
            
            app_logger.info(f"Создан контакт в AmoCRM: {contact_id}")
            return contact_id
            
        except Exception as e:
            app_logger.error(f"Ошибка создания контакта в AmoCRM: {e}")
            return None
    
    async def create_lead(self, contact_id: int, name: str, price: int = 0) -> Optional[int]:
        """
        Создание сделки в AmoCRM
        
        Args:
            contact_id: ID контакта
            name: Название сделки
            price: Сумма сделки
            
        Returns:
            ID созданной сделки
        """
        try:
            if not self.access_token:
                await self.get_access_token()
            
            url = f"{self.base_url}/leads"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            lead_data = [{
                "name": name,
                "price": price,
                "_embedded": {
                    "contacts": [{
                        "id": contact_id
                    }]
                }
            }]
            
            response = requests.post(url, headers=headers, json=lead_data)
            response.raise_for_status()
            
            result = response.json()
            lead_id = result["_embedded"]["leads"][0]["id"]
            
            app_logger.info(f"Создана сделка в AmoCRM: {lead_id}")
            return lead_id
            
        except Exception as e:
            app_logger.error(f"Ошибка создания сделки в AmoCRM: {e}")
            return None
    
    async def add_note(self, entity_type: str, entity_id: int, note_text: str):
        """
        Добавление примечания к сущности
        
        Args:
            entity_type: Тип сущности (contacts, leads)
            entity_id: ID сущности
            note_text: Текст примечания
        """
        try:
            if not self.access_token:
                await self.get_access_token()
            
            url = f"{self.base_url}/{entity_type}/{entity_id}/notes"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            note_data = [{
                "note_type": "common",
                "params": {
                    "text": note_text
                }
            }]
            
            response = requests.post(url, headers=headers, json=note_data)
            response.raise_for_status()
            
            app_logger.info(f"Добавлено примечание к {entity_type}/{entity_id}")
            
        except Exception as e:
            app_logger.error(f"Ошибка добавления примечания в AmoCRM: {e}")