#!/usr/bin/env python3
"""
Скрипт для авторизации в Telegram и создания сессии
"""
import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

async def authorize_telegram():
    """Авторизация в Telegram"""
    
    # Загрузка переменных окружения
    load_dotenv()
    
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    
    print("🔑 АВТОРИЗАЦИЯ В TELEGRAM")
    print("=" * 50)
    print(f"API ID: {api_id}")
    print(f"API Hash: {api_hash[:10]}...")
    print()
    
    # Создание клиента
    client = TelegramClient('amber_bot', api_id, api_hash)
    
    try:
        print("🔗 Подключение к Telegram...")
        await client.start()
        
        # Получение информации о пользователе
        me = await client.get_me()
        print(f"✅ Авторизация успешна!")
        print(f"👤 Пользователь: {me.first_name} (@{me.username})")
        print(f"📱 Телефон: {me.phone}")
        print()
        print("🎉 Сессия создана! Теперь можно запускать userbot:")
        print("   python main.py")
        
    except Exception as e:
        print(f"❌ Ошибка авторизации: {e}")
        print()
        print("💡 Проверьте:")
        print("- Правильность API ID и API Hash в .env")
        print("- Подключение к интернету")
        print("- Доступность серверов Telegram")
        
    finally:
        await client.disconnect()
        print("\n👋 Отключение от Telegram")

if __name__ == "__main__":
    print("📱 Подготовка к авторизации Telegram userbot...")
    print("⚠️  Вам потребуется ввести номер телефона и код подтверждения")
    print()
    
    try:
        asyncio.run(authorize_telegram())
    except KeyboardInterrupt:
        print("\n👋 Авторизация отменена пользователем")
    except Exception as e:
        print(f"💥 Ошибка: {e}")