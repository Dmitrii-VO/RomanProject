"""
Клиент для работы с AmoCRM API
"""
import os
import json
import asyncio
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
import aiohttp
from utils.logger import app_logger
from .token_manager import TokenManager


class AmoCRMClient:
    """
    Клиент для работы с AmoCRM API
    """
    
    def __init__(self):
        """Инициализация AmoCRM клиента"""
        self.subdomain = os.getenv("AMOCRM_SUBDOMAIN")
        self.client_id = os.getenv("AMOCRM_CLIENT_ID")
        self.client_secret = os.getenv("AMOCRM_CLIENT_SECRET")
        self.redirect_uri = os.getenv("AMOCRM_REDIRECT_URI")
        self.base_url = os.getenv("AMOCRM_BASE_URL", f"https://{self.subdomain}.amocrm.ru")
        
        # Менеджер токенов
        self.token_manager = TokenManager()
        
        # Токены (приоритет: из TokenManager, затем из переменных окружения)
        self.access_token = self.token_manager.get_amocrm_access_token() or os.getenv("AMOCRM_ACCESS_TOKEN")
        self.refresh_token = self.token_manager.get_amocrm_refresh_token() or os.getenv("AMOCRM_REFRESH_TOKEN")
        
        # Кэш для хранения ID созданных объектов
        self.telegram_to_contact_cache = {}
        self.contact_to_lead_cache = {}
        
        app_logger.info("AmoCRM клиент инициализирован")
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[Dict]:
        """
        Выполняет HTTP запрос к AmoCRM API
        
        Args:
            method: HTTP метод (GET, POST, PATCH)
            endpoint: Endpoint API
            data: Данные для отправки
            headers: Дополнительные заголовки
            
        Returns:
            Ответ от API или None при ошибке
        """
        if not self.access_token:
            app_logger.error("Отсутствует access_token для AmoCRM")
            return None
            
        url = f"{self.base_url}/api/v4/{endpoint}"
        
        default_headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        if headers:
            default_headers.update(headers)
        
        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == 'GET':
                    async with session.get(url, headers=default_headers, params=data) as response:
                        if response.status == 401:
                            # Токен истек, пытаемся обновить
                            if await self._refresh_access_token():
                                default_headers['Authorization'] = f'Bearer {self.access_token}'
                                async with session.get(url, headers=default_headers, params=data) as retry_response:
                                    return await retry_response.json() if retry_response.status == 200 else None
                        return await response.json() if response.status == 200 else None
                        
                elif method.upper() in ['POST', 'PATCH']:
                    json_data = json.dumps(data) if data else None
                    async with session.request(method.upper(), url, headers=default_headers, data=json_data) as response:
                        if response.status == 401:
                            # Токен истек, пытаемся обновить
                            if await self._refresh_access_token():
                                default_headers['Authorization'] = f'Bearer {self.access_token}'
                                async with session.request(method.upper(), url, headers=default_headers, data=json_data) as retry_response:
                                    return await retry_response.json() if retry_response.status in [200, 201] else None
                        return await response.json() if response.status in [200, 201] else None
                        
        except Exception as e:
            app_logger.error(f"Ошибка запроса к AmoCRM API: {e}")
            return None
    
    async def _refresh_access_token(self) -> bool:
        """
        Обновляет access_token используя refresh_token
        
        Returns:
            True если токен успешно обновлен
        """
        if not self.refresh_token:
            app_logger.error("Отсутствует refresh_token для AmoCRM")
            return False
        
        url = f"{self.base_url}/oauth2/access_token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "redirect_uri": self.redirect_uri
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data.get('access_token')
                        self.refresh_token = token_data.get('refresh_token')
                        expires_in = token_data.get('expires_in', 86400)
                        
                        # Сохраняем токены через TokenManager
                        self.token_manager.save_amocrm_tokens(
                            self.access_token, 
                            self.refresh_token, 
                            expires_in
                        )
                        
                        # Синхронизируем с .env файлом
                        self.token_manager.sync_amocrm_tokens_to_env()
                        
                        app_logger.info("AmoCRM access_token успешно обновлен и сохранен")
                        return True
                    else:
                        app_logger.error(f"Ошибка обновления токена AmoCRM: {response.status}")
                        return False
                        
        except Exception as e:
            app_logger.error(f"Ошибка обновления токена AmoCRM: {e}")
            return False
    
    async def create_contact(self, telegram_user_id: int, name: str = None, phone: str = None) -> Optional[int]:
        """
        Создает контакт в AmoCRM
        
        Args:
            telegram_user_id: ID пользователя Telegram
            name: Имя контакта
            phone: Телефон контакта
            
        Returns:
            ID созданного контакта или None
        """
        # Проверяем кэш
        if telegram_user_id in self.telegram_to_contact_cache:
            return self.telegram_to_contact_cache[telegram_user_id]
        
        contact_data = {
            "name": name or f"Telegram User {telegram_user_id}",
            "custom_fields_values": [
                {
                    "field_id": 123456,  # TODO: Заменить на реальный ID поля Telegram ID
                    "values": [{"value": str(telegram_user_id)}]
                }
            ]
        }
        
        if phone:
            contact_data["custom_fields_values"].append({
                "field_id": 123457,  # TODO: Заменить на реальный ID поля телефона
                "values": [{"value": phone, "enum_code": "WORK"}]
            })
        
        result = await self._make_request("POST", "contacts", [contact_data])
        
        if result and "_embedded" in result and "contacts" in result["_embedded"]:
            contact_id = result["_embedded"]["contacts"][0]["id"]
            self.telegram_to_contact_cache[telegram_user_id] = contact_id
            app_logger.info(f"Создан контакт AmoCRM ID: {contact_id} для Telegram ID: {telegram_user_id}")
            return contact_id
            
        app_logger.error(f"Ошибка создания контакта для Telegram ID: {telegram_user_id}")
        return None
    
    async def create_lead(self, contact_id: int, telegram_user_id: int, name: str = None) -> Optional[int]:
        """
        Создает сделку в AmoCRM
        
        Args:
            contact_id: ID контакта
            telegram_user_id: ID пользователя Telegram
            name: Название сделки
            
        Returns:
            ID созданной сделки или None
        """
        # Проверяем кэш
        if contact_id in self.contact_to_lead_cache:
            return self.contact_to_lead_cache[contact_id]
        
        lead_data = {
            "name": name or f"Консультация Telegram {telegram_user_id}",
            "price": 0,
            "status_id": 123456,  # TODO: Заменить на реальный ID статуса "Новая заявка"
            "_embedded": {
                "contacts": [{"id": contact_id}]
            },
            "custom_fields_values": [
                {
                    "field_id": 123458,  # TODO: Заменить на реальный ID поля "Источник"
                    "values": [{"value": "Telegram Bot"}]
                }
            ]
        }
        
        result = await self._make_request("POST", "leads", [lead_data])
        
        if result and "_embedded" in result and "leads" in result["_embedded"]:
            lead_id = result["_embedded"]["leads"][0]["id"]
            self.contact_to_lead_cache[contact_id] = lead_id
            app_logger.info(f"Создана сделка AmoCRM ID: {lead_id} для контакта ID: {contact_id}")
            return lead_id
            
        app_logger.error(f"Ошибка создания сделки для контакта ID: {contact_id}")
        return None
    
    async def add_note_to_lead(self, lead_id: int, message: str, note_type: str = "common") -> bool:
        """
        Добавляет примечание к сделке
        
        Args:
            lead_id: ID сделки
            message: Текст примечания
            note_type: Тип примечания (common, call_in, call_out)
            
        Returns:
            True если примечание добавлено успешно
        """
        note_data = {
            "entity_id": lead_id,
            "note_type": note_type,
            "params": {
                "text": message
            }
        }
        
        result = await self._make_request("POST", f"leads/{lead_id}/notes", [note_data])
        
        if result:
            app_logger.info(f"Добавлено примечание к сделке {lead_id}")
            return True
        else:
            app_logger.error(f"Ошибка добавления примечания к сделке {lead_id}")
            return False
    
    async def create_task(self, lead_id: int, task_text: str, responsible_user_id: int = None) -> Optional[int]:
        """
        Создает задачу в AmoCRM
        
        Args:
            lead_id: ID сделки
            task_text: Текст задачи
            responsible_user_id: ID ответственного пользователя
            
        Returns:
            ID созданной задачи или None
        """
        # Устанавливаем срок выполнения на завтра в 10:00
        complete_till = int((datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0).timestamp())
        
        task_data = {
            "task_type_id": 1,  # Обычная задача
            "text": task_text,
            "complete_till": complete_till,
            "entity_id": lead_id,
            "entity_type": "leads"
        }
        
        if responsible_user_id:
            task_data["responsible_user_id"] = responsible_user_id
        
        result = await self._make_request("POST", "tasks", [task_data])
        
        if result and "_embedded" in result and "tasks" in result["_embedded"]:
            task_id = result["_embedded"]["tasks"][0]["id"]
            app_logger.info(f"Создана задача AmoCRM ID: {task_id} для сделки ID: {lead_id}")
            return task_id
            
        app_logger.error(f"Ошибка создания задачи для сделки ID: {lead_id}")
        return None
    
    async def get_or_create_contact_and_lead(self, telegram_user_id: int, user_name: str = None) -> Tuple[Optional[int], Optional[int]]:
        """
        Получает или создает контакт и сделку для пользователя Telegram
        
        Args:
            telegram_user_id: ID пользователя Telegram
            user_name: Имя пользователя
            
        Returns:
            Кортеж (contact_id, lead_id)
        """
        # Проверяем кэш
        contact_id = self.telegram_to_contact_cache.get(telegram_user_id)
        
        if not contact_id:
            # Создаем новый контакт
            contact_id = await self.create_contact(telegram_user_id, user_name)
            
        if not contact_id:
            return None, None
            
        # Проверяем наличие активной сделки
        lead_id = self.contact_to_lead_cache.get(contact_id)
        
        if not lead_id:
            # Создаем новую сделку
            lead_id = await self.create_lead(contact_id, telegram_user_id)
            
        return contact_id, lead_id
    
    async def log_conversation(self, telegram_user_id: int, user_message: str, bot_response: str):
        """
        Логирует переписку в AmoCRM
        
        Args:
            telegram_user_id: ID пользователя Telegram
            user_message: Сообщение пользователя
            bot_response: Ответ бота
        """
        contact_id, lead_id = await self.get_or_create_contact_and_lead(telegram_user_id)
        
        if not lead_id:
            app_logger.error(f"Не удалось получить или создать сделку для пользователя {telegram_user_id}")
            return
            
        # Формируем текст переписки
        conversation_text = f"👤 Клиент: {user_message}\n🤖 Бот: {bot_response}"
        
        # Добавляем примечание к сделке
        await self.add_note_to_lead(lead_id, conversation_text)
    
    async def escalate_to_manager(self, telegram_user_id: int, reason: str = "Требуется вмешательство менеджера"):
        """
        Создает задачу для менеджера при эскалации
        
        Args:
            telegram_user_id: ID пользователя Telegram
            reason: Причина эскалации
        """
        contact_id, lead_id = await self.get_or_create_contact_and_lead(telegram_user_id)
        
        if not lead_id:
            app_logger.error(f"Не удалось получить или создать сделку для эскалации пользователя {telegram_user_id}")
            return
            
        # Создаем задачу для менеджера
        task_text = f"🔄 Подключить менеджера к клиенту Telegram ID: {telegram_user_id}\n\nПричина: {reason}"
        
        task_id = await self.create_task(lead_id, task_text)
        
        if task_id:
            app_logger.info(f"Создана задача эскалации {task_id} для пользователя {telegram_user_id}")
        else:
            app_logger.error(f"Ошибка создания задачи эскалации для пользователя {telegram_user_id}")