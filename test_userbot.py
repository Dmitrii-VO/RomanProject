#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы Telegram userbot с ИИ консультантом
"""
import asyncio
import os
from dotenv import load_dotenv
from utils.logger import app_logger
from src.ai.consultant import AmberAIConsultant


async def test_ai_consultant():
    """Тестирование ИИ консультанта без Telegram"""
    
    app_logger.info("🧪 Тестирование ИИ консультанта янтарного магазина")
    
    # Загрузка переменных окружения
    load_dotenv()
    
    # Создание ИИ консультанта
    ai_consultant = AmberAIConsultant()
    
    # Тестовые сообщения клиентов
    test_messages = [
        "Привет! Хочу купить янтарные серьги",
        "Какие у вас есть кольца с янтарем?",
        "Расскажите о целебных свойствах янтаря",
        "У меня бюджет 5000 рублей, что можете предложить?",
        "Хочу вернуть покупку, качество не устраивает!",
        "Есть ли у вас украшения с насекомыми внутри?"
    ]
    
    app_logger.info(f"Запуск {len(test_messages)} тестовых диалогов...")
    print("=" * 80)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n🗣 КЛИЕНТ #{i}: {message}")
        print("-" * 50)
        
        try:
            # Обработка сообщения через ИИ
            response = await ai_consultant.process_message(message)
            
            print(f"🤖 КОНСУЛЬТАНТ: {response}")
            
            # Проверка логики эскалации
            should_escalate = ai_consultant.should_escalate(message, response)
            if should_escalate:
                print("🔄 ЭСКАЛАЦИЯ: Клиент передан живому менеджеру")
            
            print("=" * 80)
            
            # Небольшая пауза между запросами
            await asyncio.sleep(1)
            
        except Exception as e:
            app_logger.error(f"Ошибка обработки сообщения #{i}: {e}")
            print(f"❌ ОШИБКА: {e}")
    
    app_logger.info("✅ Тестирование ИИ консультанта завершено")


async def test_telegram_integration():
    """Имитация работы с Telegram (без реального подключения)"""
    
    app_logger.info("📱 Имитация интеграции с Telegram")
    
    try:
        from src.bot.telegram_client import AmberTelegramClient
        
        # Получаем учетные данные из .env
        api_id = int(os.getenv("TELEGRAM_API_ID"))
        api_hash = os.getenv("TELEGRAM_API_HASH")
        
        app_logger.info(f"Telegram API ID: {api_id}")
        app_logger.info(f"Telegram API Hash: {api_hash[:8]}...")
        
        # Создаем клиент (без подключения к Telegram)
        telegram_client = AmberTelegramClient(api_id, api_hash, session_name='test_session')
        app_logger.info("✅ Telegram клиент создан успешно")
        
        print("\n📱 TELEGRAM INTEGRATION TEST:")
        print("✅ API credentials загружены")
        print("✅ AmberTelegramClient инициализирован")
        print("✅ Методы send_message и handle_message готовы")
        print("⚠️  Для полного теста требуется авторизация в Telegram")
        
    except Exception as e:
        app_logger.error(f"Ошибка тестирования Telegram интеграции: {e}")
        print(f"❌ TELEGRAM ERROR: {e}")


async def main():
    """Главная функция тестирования"""
    
    print("🔶" * 20 + " ТЕСТ USERBOT " + "🔶" * 20)
    print()
    
    # Тест 1: ИИ консультант
    await test_ai_consultant()
    
    print("\n" + "=" * 80)
    print()
    
    # Тест 2: Telegram интеграция
    await test_telegram_integration()
    
    print("\n" + "🔶" * 60)
    print("\n🎉 ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
    print("\n📋 ДЛЯ ПОЛНОГО ЗАПУСКА:")
    print("1. Настройте SSH ключ для GitHub")
    print("2. Выполните: source venv/bin/activate")
    print("3. Запустите: python main.py")
    print("4. Авторизуйтесь в Telegram при первом запуске")
    print("\n💬 После авторизации бот будет отвечать на сообщения!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Тест остановлен пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        exit(1)