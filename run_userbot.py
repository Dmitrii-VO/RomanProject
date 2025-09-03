#!/usr/bin/env python3
"""
Запуск userbot с корректной обработкой событий
"""
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient, events

from utils.logger import app_logger, log_conversation
from src.ai.consultant_v2 import AmberAIConsultantV2

class AmberUserBot:
    def __init__(self):
        load_dotenv()
        
        # Telegram credentials
        self.api_id = int(os.getenv("TELEGRAM_API_ID"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        
        # Создаем клиент
        self.client = TelegramClient('amber_bot', self.api_id, self.api_hash)
        
        # ИИ консультант
        self.ai_consultant = AmberAIConsultantV2()
        
        app_logger.info("AmberUserBot инициализирован")
    
    async def start(self):
        """Запуск userbot"""
        try:
            app_logger.info("🚀 Запуск Amber AI UserBot...")
            
            # Запускаем клиент
            await self.client.start()
            
            # Получаем информацию о себе
            me = await self.client.get_me()
            app_logger.info(f"✅ Подключен как: @{me.username} (ID: {me.id})")
            
            # Добавляем обработчик входящих сообщений
            @self.client.on(events.NewMessage(incoming=True))
            async def handle_message(event):
                await self.process_message(event)
            
            app_logger.info("🎉 UserBot запущен и готов к работе!")
            app_logger.info("Отправьте сообщение боту для тестирования")
            
            # Ожидание сообщений
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            app_logger.info("Получен сигнал остановки...")
        except Exception as e:
            app_logger.error(f"Критическая ошибка: {e}")
        finally:
            await self.stop()
    
    async def process_message(self, event):
        """Обработка входящего сообщения"""
        try:
            user_id = event.sender_id
            message_text = event.message.text or ""
            
            # Пропускаем сообщения от самого себя
            if hasattr(event, 'is_self') and event.is_self:
                return
            
            # Дополнительная проверка - пропускаем сообщения от бота
            me = await self.client.get_me()
            if user_id == me.id:
                return
                
            # Логируем входящее сообщение
            app_logger.info(f"📩 Получено от {user_id}: {message_text[:100]}...")
            log_conversation(user_id, "user_message", message_text)
            
            # Обработка через ИИ консультант v2
            ai_response = await self.ai_consultant.process_message(user_id, message_text)
            
            # Отправляем ответ
            await event.reply(ai_response)
            
            # Логируем ответ
            app_logger.info(f"📤 Отправлен ответ пользователю {user_id}")
            log_conversation(user_id, "bot_response", ai_response)
            
        except Exception as e:
            app_logger.error(f"Ошибка обработки сообщения: {e}")
            try:
                error_response = "Извините, произошла техническая ошибка. Попробуйте еще раз!"
                await event.reply(error_response)
                log_conversation(user_id, "bot_response", error_response)
            except:
                pass  # Если не можем отправить даже error message
    
    async def stop(self):
        """Остановка userbot"""
        try:
            await self.client.disconnect()
            app_logger.info("👋 UserBot остановлен")
        except:
            pass

async def main():
    """Главная функция"""
    bot = AmberUserBot()
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 UserBot остановлен пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")