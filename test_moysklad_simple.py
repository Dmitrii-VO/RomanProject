#!/usr/bin/env python3
"""
Упрощенное тестирование интеграции с МойСклад API
"""
import asyncio
import os
from src.integrations.moysklad_client import MoySkladClient
from src.catalog.product_manager import ProductManager
from utils.logger import app_logger


async def test_basic_connection():
    """Тестирует базовое подключение к МойСклад API"""
    print("🔧 Тестирование базового подключения к МойСклад...")
    
    client = MoySkladClient()
    
    # Тест получения товаров без фильтров
    products = await client.get_products(limit=3)
    
    if products:
        print(f"✅ Подключение успешно! Загружено {len(products)} товаров")
        for i, product in enumerate(products, 1):
            print(f"  {i}. {product['name']} - {product['price']:.0f}₽")
            print(f"     Категория: {product['category']}")
            if product.get('article'):
                print(f"     Артикул: {product['article']}")
    else:
        print("❌ Ошибка подключения или товары не найдены")
    
    return products


async def test_product_manager_basic():
    """Тестирует базовые функции ProductManager"""
    print("\n🔍 Тестирование ProductManager...")
    
    manager = ProductManager()
    
    # Тест поиска без фильтров
    print("\n📍 Поиск товаров без фильтров:")
    products = await manager.search_products("", budget_min=None, budget_max=None, category=None)
    print(f"Найдено: {len(products)} товаров")
    
    if products:
        # Показываем первые 3 товара
        for i, product in enumerate(products[:3], 1):
            print(f"  {i}. {product['name']} - {product['price']:.0f}₽")
    
    return products


async def test_text_parsing():
    """Тестирует парсинг бюджета и категорий из текста"""
    print("\n💰 Тестирование парсинга текста...")
    
    manager = ProductManager()
    
    # Тест парсинга бюджета
    test_messages = [
        "Ищу кольцо до 5000 рублей",
        "Бюджет 10000",
        "Хочу серьги за 3000₽"
    ]
    
    print("\nПарсинг бюджета:")
    for message in test_messages:
        budget = manager.parse_budget_from_text(message)
        print(f"  '{message}' → {budget}₽")
    
    # Тест парсинга категорий
    category_messages = [
        "Покажите кольца",
        "Хочу серьги",
        "Есть браслеты?"
    ]
    
    print("\nПарсинг категорий:")
    for message in category_messages:
        category = manager.extract_category_from_text(message)
        print(f"  '{message}' → {category}")


async def test_product_formatting():
    """Тестирует форматирование товаров"""
    print("\n💬 Тестирование форматирования...")
    
    manager = ProductManager()
    
    # Получаем товары для форматирования
    products = await manager.search_products("")
    
    if products:
        print("\nФорматирование одного товара:")
        formatted = manager.format_product_for_chat(products[0])
        print(formatted)
        
        print("\nФорматирование списка (первые 2 товара):")
        formatted_list = manager.format_products_list(products[:2], max_products=2)
        print(formatted_list)


async def main():
    """Основная функция упрощенного тестирования"""
    print("🧪 Упрощенное тестирование МойСклад интеграции")
    print("=" * 50)
    
    try:
        # Проверяем переменные окружения
        if not os.getenv("MOYSKLAD_TOKEN"):
            print("❌ Отсутствует MOYSKLAD_TOKEN")
            return
        
        # Выполняем базовые тесты
        products = await test_basic_connection()
        
        if products:
            await test_product_manager_basic()
            await test_text_parsing()
            await test_product_formatting()
        
        print("\n✅ Упрощенное тестирование завершено!")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        app_logger.error(f"Ошибка упрощенного тестирования МойСклад: {e}")


if __name__ == "__main__":
    asyncio.run(main())