#!/usr/bin/env python3
"""
Простой тест Telegram клиента для диагностики
"""
import asyncio
import os
from dotenv import load_dotenv
from utils.logger import app_logger

async def test_telegram():
    """Тест подключения к Telegram"""
    
    load_dotenv()
    
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    
    print(f"API_ID: {api_id}")
    print(f"API_HASH: {api_hash[:10]}..." if api_hash else "API_HASH: None")
    
    try:
        from telethon import TelegramClient
        
        # Создаем клиента
        client = TelegramClient('test_session', api_id, api_hash)
        
        print("Подключение к Telegram...")
        await client.start()
        
        # Получаем информацию о себе
        me = await client.get_me()
        print(f"✅ Успешно подключен как: @{me.username}")
        print(f"   ID: {me.id}")
        print(f"   Имя: {me.first_name} {me.last_name or ''}")
        
        # Проверяем диалоги
        dialogs = await client.get_dialogs(limit=5)
        print(f"   Диалогов: {len(dialogs)}")
        
        await client.disconnect()
        print("✅ Тест завершен успешно")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(test_telegram())