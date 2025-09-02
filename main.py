#!/usr/bin/env python3
"""
Главный файл запуска ИИ консультанта янтарного магазина
"""
import asyncio
import os
from dotenv import load_dotenv

from utils.logger import app_logger
from src.bot.telegram_client import AmberTelegramClient
from src.ai.consultant import AmberAIConsultant


async def main():
    """Основная функция запуска"""
    
    # Загрузка переменных окружения
    load_dotenv()
    
    app_logger.info("🚀 Запуск ИИ консультанта янтарного магазина")
    
    # Получение настроек из переменных окружения
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    
    # Создание компонентов системы
    app_logger.info("Инициализация компонентов...")
    
    # ИИ консультант
    ai_consultant = AmberAIConsultant()
    
    # Telegram клиент
    telegram_client = AmberTelegramClient(api_id, api_hash)
    
    try:
        # Запуск Telegram клиента
        app_logger.info("Запуск Telegram клиента...")
        await telegram_client.start_client()
        
        # Обработка сообщений
        @telegram_client.client.on(telegram_client.client.events.NewMessage)
        async def handle_new_message(event):
            """Обработчик новых сообщений"""
            try:
                user_id = event.sender_id
                message_text = event.message.text
                
                # Логирование входящего сообщения
                from utils.logger import log_conversation
                log_conversation(user_id, "user_message", message_text)
                
                # Обработка сообщения через ИИ
                ai_response = await ai_consultant.process_message(message_text)
                
                # Проверка необходимости эскалации
                if ai_consultant.should_escalate(message_text, ai_response):
                    escalation_message = ("🔄 Ваш запрос передан нашему менеджеру. "
                                         "Он свяжется с вами в ближайшее время.")
                    await telegram_client.send_message(user_id, escalation_message)
                    
                    # TODO: Отправить уведомление менеджеру
                    app_logger.info(f"Эскалация для пользователя {user_id}")
                else:
                    # Отправка ответа ИИ
                    await telegram_client.send_message(user_id, ai_response)
                
            except Exception as e:
                app_logger.error(f"Ошибка обработки сообщения: {e}")
                error_message = ("Извините, произошла техническая ошибка. "
                               "Попробуйте еще раз или обратитесь к нашему менеджеру.")
                await telegram_client.send_message(user_id, error_message)
        
        app_logger.info("🎉 ИИ консультант запущен и готов к работе!")
        app_logger.info("Нажмите Ctrl+C для остановки")
        
        # Ожидание сообщений
        await telegram_client.client.run_until_disconnected()
        
    except KeyboardInterrupt:
        app_logger.info("Получен сигнал остановки...")
    except Exception as e:
        app_logger.error(f"Критическая ошибка: {e}")
    finally:
        # Остановка клиента
        app_logger.info("Остановка Telegram клиента...")
        await telegram_client.stop_client()
        
        app_logger.info("👋 ИИ консультант остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Программа остановлена пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        exit(1)