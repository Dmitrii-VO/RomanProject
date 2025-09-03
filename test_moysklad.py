#!/usr/bin/env python3
"""
Тестирование интеграции с МойСклад API
"""
import asyncio
import os
from src.integrations.moysklad_client import MoySkladClient
from src.catalog.product_manager import ProductManager
from utils.logger import app_logger


async def test_moysklad_connection():
    """Тестирует подключение к МойСклад API"""
    print("🔧 Тестирование подключения к МойСклад...")
    
    client = MoySkladClient()
    
    # Тест получения товаров
    products = await client.get_products(limit=5)
    
    if products:
        print(f"✅ Подключение успешно! Загружено {len(products)} товаров")
        for i, product in enumerate(products, 1):
            print(f"  {i}. {product['name']} - {product['price']:.0f}₽ (в наличии: {product['stock']})")
    else:
        print("❌ Ошибка подключения или товары не найдены")
    
    return products


async def test_product_search():
    """Тестирует поиск товаров по различным параметрам"""
    print("\n🔍 Тестирование поиска товаров...")
    
    manager = ProductManager()
    
    # Тест 1: Поиск по ключевому слову "янтарь"
    print("\n📍 Поиск по слову 'янтарь':")
    products = await manager.search_products("янтарь")
    print(f"Найдено: {len(products)} товаров")
    
    # Тест 2: Поиск по категории "кольца"
    print("\n📍 Поиск в категории 'кольца':")
    rings = await manager.search_products("", category="кольца")
    print(f"Найдено колец: {len(rings)}")
    
    # Тест 3: Поиск по бюджету 5000-10000 руб
    print("\n📍 Поиск в диапазоне 5000-10000₽:")
    budget_products = await manager.search_products("", budget_min=5000, budget_max=10000)
    print(f"Найдено товаров в бюджете: {len(budget_products)}")
    
    # Тест 4: Рекомендации для конкретного бюджета и категории
    print("\n📍 Рекомендации: кольца до 8000₽:")
    recommendations = await manager.get_product_recommendations(8000, "кольца")
    print(f"Рекомендаций: {len(recommendations)}")
    for product in recommendations:
        print(f"  • {product['name']} - {product['price']:.0f}₽")
    
    return products


async def test_budget_parsing():
    """Тестирует извлечение бюджета из текста"""
    print("\n💰 Тестирование парсинга бюджета...")
    
    manager = ProductManager()
    
    test_messages = [
        "Ищу кольцо до 5000 рублей",
        "Бюджет 10 тысяч",
        "Хочу серьги за 3000₽",
        "До 15000 руб",
        "Бюджет примерно 7 500 рублей"
    ]
    
    for message in test_messages:
        budget = manager.parse_budget_from_text(message)
        print(f"  '{message}' → {budget}₽")


async def test_category_extraction():
    """Тестирует определение категории из текста"""
    print("\n📂 Тестирование извлечения категории...")
    
    manager = ProductManager()
    
    test_messages = [
        "Покажите кольца с янтарем",
        "Хочу посмотреть серьги",
        "Есть ли браслеты в наличии?",
        "Ищу красивый кулон",
        "Покажите бусы из янтаря"
    ]
    
    for message in test_messages:
        category = manager.extract_category_from_text(message)
        print(f"  '{message}' → {category}")


async def test_product_formatting():
    """Тестирует форматирование товаров для чата"""
    print("\n💬 Тестирование форматирования товаров...")
    
    manager = ProductManager()
    
    # Получаем несколько товаров
    products = await manager.search_products("янтарь")
    
    if products:
        # Форматируем список
        formatted_list = manager.format_products_list(products[:3], max_products=3)
        print("Форматированный список товаров:")
        print(formatted_list)
        
        # Форматируем один товар
        print("\nФорматирование одного товара:")
        formatted_product = manager.format_product_for_chat(products[0])
        print(formatted_product)


async def test_categories_summary():
    """Тестирует получение сводки категорий"""
    print("\n📋 Тестирование сводки категорий...")
    
    manager = ProductManager()
    
    categories_info = await manager.get_categories_summary()
    print(categories_info)


async def main():
    """Основная функция тестирования"""
    print("🧪 Запуск тестов МойСклад интеграции")
    print("=" * 50)
    
    try:
        # Проверяем переменные окружения
        required_vars = ['MOYSKLAD_TOKEN', 'MOYSKLAD_LOGIN', 'MOYSKLAD_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
            return
        
        # Выполняем тесты
        products = await test_moysklad_connection()
        
        if products:
            await test_product_search()
            await test_budget_parsing()
            await test_category_extraction() 
            await test_product_formatting()
            await test_categories_summary()
        
        print("\n✅ Все тесты завершены!")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        app_logger.error(f"Ошибка тестирования МойСклад: {e}")


if __name__ == "__main__":
    asyncio.run(main())