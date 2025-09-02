#!/usr/bin/env python3
"""
Тестовый скрипт для проверки окружения ИИ консультанта янтарного магазина
"""
import os
import sys
from dotenv import load_dotenv
from utils.logger import app_logger, log_conversation

def test_environment():
    """Тестирование настройки окружения"""
    
    app_logger.info("🚀 Запуск тестирования окружения ИИ консультанта")
    
    # Тест загрузки переменных окружения
    load_dotenv()
    
    # Проверка ключевых переменных
    required_vars = [
        "OPENAI_API_KEY",
        "TELEGRAM_BOT_TOKEN", 
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH",
        "MOYSKLAD_TOKEN"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            app_logger.warning(f"❌ Переменная {var} не установлена")
        else:
            # Не логируем полные ключи в целях безопасности
            value = os.getenv(var)
            masked_value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            app_logger.info(f"✅ {var}: {masked_value}")
    
    if missing_vars:
        app_logger.error(f"Отсутствуют обязательные переменные: {', '.join(missing_vars)}")
        return False
    
    # Тест импорта библиотек
    try:
        import telethon
        app_logger.info(f"✅ Telethon {telethon.__version__} импортирован")
    except ImportError as e:
        app_logger.error(f"❌ Ошибка импорта Telethon: {e}")
        return False
    
    try:
        import openai
        app_logger.info(f"✅ OpenAI {openai.__version__} импортирован")
    except ImportError as e:
        app_logger.error(f"❌ Ошибка импорта OpenAI: {e}")
        return False
    
    try:
        import fastapi
        app_logger.info(f"✅ FastAPI {fastapi.__version__} импортирован")
    except ImportError as e:
        app_logger.error(f"❌ Ошибка импорта FastAPI: {e}")
        return False
    
    # Тест логирования диалогов
    log_conversation(
        user_id=12345, 
        chat_type="test_message", 
        message="Тестовое сообщение в систему логирования диалогов"
    )
    app_logger.info("✅ Система логирования диалогов работает")
    
    # Проверка настроек ИИ
    ai_settings = {
        "temperature": os.getenv("AI_TEMPERATURE", "0.7"),
        "max_tokens": os.getenv("AI_MAX_TOKENS", "500"),
        "presence_penalty": os.getenv("AI_PRESENCE_PENALTY", "0.6"),
        "frequency_penalty": os.getenv("AI_FREQUENCY_PENALTY", "0.5")
    }
    
    app_logger.info("🧠 Настройки ИИ:")
    for key, value in ai_settings.items():
        app_logger.info(f"   {key}: {value}")
    
    # Проверка структуры проекта
    required_dirs = ["logs", "utils", "knowledge_map"]
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            app_logger.info(f"✅ Директория {dir_name}/ существует")
        else:
            app_logger.warning(f"⚠️  Директория {dir_name}/ не найдена")
    
    app_logger.info("🎉 Тестирование окружения завершено успешно!")
    return True

def test_hello_world():
    """Простой тест Hello World"""
    
    app_logger.info("👋 Hello, Мир янтарных украшений!")
    app_logger.info("🏪 ИИ консультант готов к работе")
    
    # Эмуляция простого диалога
    log_conversation(
        user_id=99999,
        chat_type="user_message", 
        message="Привет! Хочу посмотреть янтарные украшения"
    )
    
    log_conversation(
        user_id=99999,
        chat_type="bot_response",
        message="Добро пожаловать в наш магазин янтарных украшений! Я помогу вам выбрать идеальное изделие. Что вас интересует больше всего - кольца, серьги, браслеты или подвески?"
    )
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("🔍 ТЕСТИРОВАНИЕ ОКРУЖЕНИЯ ИИ КОНСУЛЬТАНТА")
    print("=" * 60)
    
    try:
        # Тестируем окружение
        env_ok = test_environment()
        
        print("\n" + "=" * 60)
        print("👋 HELLO WORLD ТЕСТ")
        print("=" * 60)
        
        # Hello World тест
        hello_ok = test_hello_world()
        
        print("\n" + "=" * 60)
        if env_ok and hello_ok:
            print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
            print("📝 Логи сохранены в директории logs/")
            sys.exit(0)
        else:
            print("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
            print("🔧 Проверьте конфигурацию и повторите тест")
            sys.exit(1)
            
    except Exception as e:
        print(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        sys.exit(1)