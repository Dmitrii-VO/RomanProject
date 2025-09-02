"""
Telegram клиент для взаимодействия с пользователями
"""
from typing import Optional
from telethon import TelegramClient
from utils.logger import app_logger, log_conversation


class AmberTelegramClient:
    """
    Основной класс для работы с Telegram API
    """
    
    def __init__(self, api_id: int, api_hash: str, session_name: str = 'amber_bot'):
        """
        Инициализация Telegram клиента
        
        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            session_name: Имя сессии
        """
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.app_logger = app_logger
        
    async def start_client(self):
        """Запуск Telegram клиента"""
        await self.client.start()
        me = await self.client.get_me()
        self.app_logger.info(f"Telegram клиент запущен: @{me.username}")
        
    async def send_message(self, chat_id: int, message: str):
        """
        Отправка сообщения пользователю
        
        Args:
            chat_id: ID чата
            message: Текст сообщения
        """
        try:
            await self.client.send_message(chat_id, message)
            log_conversation(chat_id, "bot_response", message)
            self.app_logger.info(f"Сообщение отправлено пользователю {chat_id}")
        except Exception as e:
            self.app_logger.error(f"Ошибка отправки сообщения: {e}")
            
    async def handle_message(self, event):
        """
        Обработчик входящих сообщений
        
        Args:
            event: Событие Telegram
        """
        user_id = event.sender_id
        message_text = event.message.text
        
        # Логируем входящее сообщение
        log_conversation(user_id, "user_message", message_text)
        self.app_logger.info(f"Получено сообщение от {user_id}: {message_text[:50]}...")
        
        # TODO: Здесь будет интеграция с ИИ
        response = f"Спасибо за ваше сообщение: {message_text}"
        await self.send_message(user_id, response)
        
    async def stop_client(self):
        """Остановка клиента"""
        await self.client.disconnect()
        self.app_logger.info("Telegram клиент остановлен")