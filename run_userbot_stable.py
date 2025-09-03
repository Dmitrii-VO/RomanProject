#!/usr/bin/env python3
"""
Максимально стабильная версия userbot с улучшенной обработкой ошибок
"""
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient, events

from utils.logger import app_logger, log_conversation
from src.ai.consultant_v2 import AmberAIConsultantV2

class StableAmberUserBot:
    def __init__(self):
        load_dotenv()
        
        # Telegram credentials
        self.api_id = int(os.getenv("TELEGRAM_API_ID"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        
        # Создаем клиент
        self.client = TelegramClient('amber_bot', self.api_id, self.api_hash)
        
        # ИИ консультант
        self.ai_consultant = None
        self.me = None
        
        app_logger.info("StableAmberUserBot инициализирован")
    
    async def start(self):
        """Запуск userbot с улучшенной обработкой ошибок"""
        try:
            app_logger.info("🚀 Запуск Stable Amber AI UserBot...")
            
            # Запускаем клиент
            await self.client.start()
            
            # Получаем информацию о себе
            self.me = await self.client.get_me()
            app_logger.info(f"✅ Подключен как: @{self.me.username} (ID: {self.me.id})")
            
            # Инициализируем ИИ консультант только после успешного подключения
            try:
                self.ai_consultant = AmberAIConsultantV2()
                app_logger.info("✅ ИИ консультант v2 инициализирован")
            except Exception as e:
                app_logger.error(f"❌ Ошибка инициализации ИИ: {e}")
                app_logger.info("⚠️  Работаю в режиме эхо-бота без ИИ")
            
            # Добавляем обработчик входящих сообщений
            @self.client.on(events.NewMessage(incoming=True))
            async def handle_message(event):
                await self.process_message(event)
            
            app_logger.info("🎉 UserBot запущен и готов к работе!")
            app_logger.info("📱 Отправьте сообщение для тестирования")
            
            # Ожидание сообщений
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            app_logger.info("🛑 Получен сигнал остановки...")
        except Exception as e:
            app_logger.error(f"💥 Критическая ошибка: {e}")
        finally:
            await self.stop()
    
    async def process_message(self, event):
        """Обработка входящего сообщения с максимальной стабильностью"""
        user_id = None
        message_text = ""
        
        try:
            # Безопасное извлечение данных
            user_id = getattr(event, 'sender_id', None)
            message_obj = getattr(event, 'message', None)
            message_text = getattr(message_obj, 'text', '') if message_obj else ""
            
            # Проверяем корректность данных
            if not user_id or not message_text:
                app_logger.warning("⚠️  Получено сообщение с некорректными данными")
                return
            
            # Пропускаем собственные сообщения
            if self.me and user_id == self.me.id:
                return
                
            # Дополнительная проверка на исходящие сообщения
            if hasattr(event, 'out') and event.out:
                return
                
            # Логируем входящее сообщение
            app_logger.info(f"📩 Получено от {user_id}: {message_text[:50]}...")
            log_conversation(user_id, "user_message", message_text)
            
            # Обработка через ИИ или эхо-режим
            if self.ai_consultant:
                try:
                    ai_response = await self.ai_consultant.process_message(user_id, message_text)
                except Exception as ai_error:
                    app_logger.error(f"❌ Ошибка ИИ: {ai_error}")
                    ai_response = "Простите, ИИ консультант временно недоступен. Попробуйте позже!"
            else:
                # Эхо-режим без ИИ
                ai_response = f"Эхо: {message_text}"
            
            # Отправляем ответ
            try:
                await event.reply(ai_response)
                app_logger.info(f"📤 Отправлен ответ пользователю {user_id}")
                log_conversation(user_id, "bot_response", ai_response)
            except Exception as send_error:
                app_logger.error(f"❌ Ошибка отправки: {send_error}")
                
        except Exception as e:
            app_logger.error(f"💥 Критическая ошибка обработки сообщения: {e}")
            
            # Попытка отправить error message
            try:
                if hasattr(event, 'reply'):
                    error_response = "Извините, произошла техническая ошибка. Попробуйте позже!"
                    await event.reply(error_response)
                    if user_id:
                        log_conversation(user_id, "bot_response", error_response)
            except:
                app_logger.error("❌ Не удалось отправить error message")
    
    async def stop(self):
        """Остановка userbot"""
        try:
            if self.client.is_connected():
                await self.client.disconnect()
            app_logger.info("👋 UserBot остановлен")
        except Exception as e:
            app_logger.error(f"Ошибка при остановке: {e}")

async def main():
    """Главная функция с обработкой ошибок"""
    bot = StableAmberUserBot()
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            app_logger.info(f"🔄 Попытка запуска {attempt + 1}/{max_retries}")
            await bot.start()
            break
        except KeyboardInterrupt:
            app_logger.info("🛑 Остановлено пользователем")
            break
        except Exception as e:
            app_logger.error(f"💥 Ошибка запуска (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                app_logger.info("⏰ Ожидание 5 секунд до повторной попытки...")
                await asyncio.sleep(5)
            else:
                app_logger.error("❌ Исчерпаны все попытки запуска")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 UserBot остановлен пользователем")
    except Exception as e:
        print(f"💥 Фатальная ошибка: {e}")