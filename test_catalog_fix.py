#!/usr/bin/env python3
"""
Тест исправлений логики показа каталога товаров
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.ai.consultant_v2 import AmberAIConsultantV2

async def test_catalog_viewing():
    """
    Тестирует исправленную логику показа каталога товаров
    """
    print("🔧 Тестирование исправлений логики каталога товаров")
    print("=" * 60)
    
    # Инициализируем консультанта
    consultant = AmberAIConsultantV2()
    
    # Тестовый пользователь
    test_user_id = 12345
    
    # Тестовые сценарии
    test_cases = [
        {
            "message": "покажите браслеты",
            "expected": "catalog_view",
            "description": "Просмотр каталога браслетов"
        },
        {
            "message": "покажи кольца",
            "expected": "catalog_view", 
            "description": "Просмотр каталога колец"
        },
        {
            "message": "какие есть серьги",
            "expected": "catalog_view",
            "description": "Просмотр каталога сережек"
        },
        {
            "message": "хочу купить браслет за 5000 рублей",
            "expected": "order_automation",
            "description": "Автоматизация заказа с намерением покупки"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Тест {i}: {test_case['description']}")
        print(f"💬 Сообщение: \"{test_case['message']}\"")
        print(f"🎯 Ожидается: {test_case['expected']}")
        print("-" * 50)
        
        try:
            # Обрабатываем сообщение
            response = await consultant.process_message(test_user_id, test_case['message'])
            
            # Анализируем ответ
            is_catalog = "🛍️" in response and "каталога" in response.lower()
            is_order = "заказ" in response.lower() and ("оформ" in response.lower() or "автомат" in response.lower())
            
            if test_case['expected'] == "catalog_view" and is_catalog:
                print("✅ ПРОЙДЕН: Показан каталог товаров")
            elif test_case['expected'] == "order_automation" and is_order:
                print("✅ ПРОЙДЕН: Запущена автоматизация заказа")
            else:
                print("❌ НЕ ПРОЙДЕН: Неожиданный результат")
            
            print(f"📤 Ответ системы:")
            print(response[:300] + ("..." if len(response) > 300 else ""))
            
        except Exception as e:
            print(f"❌ ОШИБКА: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 Тестирование завершено")

if __name__ == "__main__":
    asyncio.run(test_catalog_viewing())