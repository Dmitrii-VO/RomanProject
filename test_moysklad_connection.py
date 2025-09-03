#!/usr/bin/env python3
"""
Тест подключения к МойСклад с новыми настройками
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.integrations.moysklad_client import MoySkladClient
from utils.logger import app_logger


async def test_moysklad_connection():
    """Тестирует подключение и основные операции с МойСклад"""
    print("🧪 Тестирование подключения к МойСклад...")
    
    try:
        # Инициализируем клиента
        client = MoySkladClient()
        
        print(f"✅ Клиент инициализирован")
        print(f"📊 URL: {client.base_url}")
        print(f"🔐 Авторизация: {'Bearer токен' if client.token else 'Basic auth'}")
        
        # Тест 1: Простой GET запрос к API
        print("\n🔌 Тест 1: Проверка подключения к API")
        
        # Делаем базовый запрос к context/employee (информация о текущем пользователе)
        response = await client._make_request("GET", "context/employee")
        
        if response:
            print("✅ Подключение к API работает")
            user_name = response.get('name', 'Неизвестно') 
            print(f"👤 Пользователь: {user_name}")
        else:
            print("❌ Не удалось подключиться к API")
            return False
            
        # Тест 2: Получение списка товаров  
        print("\n📦 Тест 2: Получение списка товаров")
        products_response = await client._make_request("GET", "entity/product", params={"limit": 3})
        
        if products_response and 'rows' in products_response:
            products = products_response['rows']
            print(f"✅ Найдено товаров: {len(products)}")
            
            for i, product in enumerate(products[:2], 1):
                name = product.get('name', 'Без названия')
                # Цены в МойСклад хранятся в копейках
                sale_prices = product.get('salePrices', [])
                price = sale_prices[0].get('value', 0) / 100 if sale_prices else 0
                print(f"  {i}. {name} - {price}₽")
        else:
            print("❌ Не удалось получить список товаров")
            
        # Тест 3: Получение списка контрагентов
        print("\n👥 Тест 3: Получение списка контрагентов")  
        counterparties_response = await client._make_request("GET", "entity/counterparty", params={"limit": 3})
        
        if counterparties_response and 'rows' in counterparties_response:
            counterparties = counterparties_response['rows']
            print(f"✅ Найдено контрагентов: {len(counterparties)}")
            
            for i, cp in enumerate(counterparties[:2], 1):
                name = cp.get('name', 'Без названия')
                print(f"  {i}. {name}")
        else:
            print("❌ Не удалось получить список контрагентов")
        
        print(f"\n🎉 Базовое тестирование завершено успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        app_logger.error(f"Ошибка тестирования МойСклад: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_moysklad_connection())
    if success:
        print("\n✅ МойСклад работает корректно!")
    else:
        print("\n❌ Есть проблемы с подключением к МойСклад")