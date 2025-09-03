#!/usr/bin/env python3
"""
Тесты для системы доставки Почта России
"""
import asyncio
import pytest
import os
import sys
from typing import List, Dict

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.delivery.russian_post_client import RussianPostClient
from src.catalog.product_manager import ProductManager
from utils.logger import app_logger


class TestDeliverySystem:
    """Тесты системы доставки"""
    
    @pytest.fixture
    def delivery_client(self):
        """Фикстура для RussianPostClient"""
        return RussianPostClient()
    
    @pytest.fixture
    def product_manager(self):
        """Фикстура для ProductManager"""
        return ProductManager()
    
    def test_postcode_validation(self, delivery_client):
        """Тестирует валидацию почтовых индексов"""
        
        # Валидные индексы
        valid_postcodes = ["101000", "190000", "344002", "630007", "690091"]
        for postcode in valid_postcodes:
            assert delivery_client._is_valid_postcode(postcode), f"Индекс {postcode} должен быть валидным"
        
        # Невалидные индексы
        invalid_postcodes = [
            "000000",  # Начинается с 0
            "12345",   # Слишком короткий
            "1234567", # Слишком длинный
            "12345a",  # Содержит буквы
            "",        # Пустой
            None,      # None
            "101 000", # Со пробелом
        ]
        for postcode in invalid_postcodes:
            assert not delivery_client._is_valid_postcode(postcode), f"Индекс {postcode} должен быть невалидным"
        
        print("✅ Тесты валидации почтовых индексов пройдены")
    
    async def test_delivery_calculation_mock(self, delivery_client):
        """Тестирует расчет доставки (заглушка)"""
        
        test_cases = [
            {"postcode": "101000", "description": "Москва"},
            {"postcode": "190000", "description": "СПб"},
            {"postcode": "344002", "description": "Ростов (местный)"},
            {"postcode": "630007", "description": "Новосибирск"},
            {"postcode": "999999", "description": "Неизвестный регион"}
        ]
        
        print("\n🧪 Тестирование расчета доставки:")
        
        for case in test_cases:
            postcode = case["postcode"]
            description = case["description"]
            
            print(f"\n--- {description} ({postcode}) ---")
            
            delivery_info = await delivery_client.calculate_delivery_cost(postcode)
            
            # Проверяем структуру ответа
            assert "success" in delivery_info
            assert "cost" in delivery_info
            assert "delivery_time" in delivery_info
            
            if delivery_info["success"]:
                assert delivery_info["cost"] > 0, "Стоимость должна быть больше 0"
                assert delivery_info["delivery_time"] > 0, "Срок доставки должен быть больше 0"
                assert "service_name" in delivery_info
                assert "delivery_date" in delivery_info
                
                print(f"Стоимость: {delivery_info['cost']}₽")
                print(f"Срок: {delivery_info['delivery_time']} дней")
                print(f"Дата: {delivery_info['delivery_date']}")
                print(f"Сервис: {delivery_info['service_name']}")
            else:
                print(f"Ошибка: {delivery_info.get('error')}")
        
        print("\n✅ Тесты расчета доставки пройдены")
    
    async def test_delivery_with_products(self, product_manager):
        """Тестирует расчет доставки с учетом товаров"""
        
        # Создаем тестовые товары
        test_products = [
            {
                "id": "test_ring_1",
                "name": "Кольцо с янтарем",
                "category": "кольца",
                "price": 2500,
                "quantity": 1
            },
            {
                "id": "test_earrings_1", 
                "name": "Серьги янтарные",
                "category": "серьги",
                "price": 3200,
                "quantity": 1
            }
        ]
        
        postcode = "101000"  # Москва
        
        print("\n🧪 Тестирование доставки с товарами:")
        print(f"Товары: {len(test_products)} шт.")
        
        # Рассчитываем параметры
        total_weight = product_manager._calculate_total_weight(test_products)
        total_value = product_manager._calculate_total_value(test_products)
        
        print(f"Общий вес: {total_weight}г")
        print(f"Общая стоимость: {total_value}₽")
        
        # Рассчитываем доставку
        delivery_info = await product_manager.calculate_delivery_cost(postcode, test_products)
        
        assert delivery_info["success"], "Расчет доставки должен быть успешным"
        assert delivery_info["cost"] > 0, "Стоимость доставки должна быть больше 0"
        
        # Форматируем информацию
        formatted_info = product_manager.format_delivery_info_with_products(delivery_info, test_products)
        
        print(f"\nФорматированная информация:")
        print(formatted_info)
        
        print("\n✅ Тесты доставки с товарами пройдены")
    
    def test_postcode_parsing(self, product_manager):
        """Тестирует извлечение индекса из текста"""
        
        test_texts = [
            ("Мой индекс 101000", "101000"),
            ("Доставка на 344002 пожалуйста", "344002"),
            ("Живу в городе с индексом 630007", "630007"),
            ("Без индекса", None),
            ("000000 неправильный", None),
            ("Индекс 12345 короткий", None),
            ("Несколько 101000 и 190000 индексов", "101000")  # Берет первый
        ]
        
        print("\n🧪 Тестирование парсинга индексов:")
        
        for text, expected in test_texts:
            result = product_manager.parse_postcode_from_text(text)
            print(f"'{text[:30]}...' → {result}")
            assert result == expected, f"Ожидался {expected}, получен {result}"
        
        print("\n✅ Тесты парсинга индексов пройдены")
    
    async def test_delivery_options(self, product_manager):
        """Тестирует получение вариантов доставки"""
        
        postcode = "344002"  # Ростов
        
        print("\n🧪 Тестирование вариантов доставки:")
        
        options = await product_manager.get_delivery_options(postcode)
        
        assert isinstance(options, list), "Должен возвращать список"
        
        if options:
            print(f"Найдено {len(options)} вариантов:")
            
            for i, option in enumerate(options, 1):
                print(f"\n{i}. {option['name']}")
                print(f"   Тип: {option['type']}")
                print(f"   Стоимость: {option['cost']}₽")
                print(f"   Срок: {option['delivery_time']} дней")
                print(f"   Дата: {option['delivery_date']}")
                
                # Проверяем структуру опции
                assert "type" in option
                assert "name" in option
                assert "cost" in option
                assert "delivery_time" in option
                assert option["cost"] > 0
                assert option["delivery_time"] > 0
        else:
            print("Варианты доставки не найдены")
        
        print("\n✅ Тесты вариантов доставки пройдены")
    
    def test_weight_calculation(self, product_manager):
        """Тестирует расчет веса товаров"""
        
        test_products = [
            {
                "name": "Кольцо",
                "category": "кольца",
                "quantity": 2
            },
            {
                "name": "Серьги",
                "category": "серьги", 
                "quantity": 1
            },
            {
                "name": "Браслет",
                "category": "браслеты",
                "quantity": 1
            }
        ]
        
        print("\n🧪 Тестирование расчета веса:")
        
        # Ожидаемый вес: 2*15 (кольца) + 1*25 (серьги) + 1*40 (браслеты) + упаковка (20 + 3*5)
        # = 30 + 25 + 40 + 35 = 130г
        expected_weight = 130
        
        actual_weight = product_manager._calculate_total_weight(test_products)
        
        print(f"Товары: {len(test_products)} позиций")
        print(f"Ожидаемый вес: {expected_weight}г")
        print(f"Рассчитанный вес: {actual_weight}г")
        
        assert actual_weight == expected_weight, f"Вес {actual_weight}г не совпадает с ожидаемым {expected_weight}г"
        
        # Тест без товаров
        empty_weight = product_manager._calculate_total_weight([])
        assert empty_weight == 50, "Без товаров должен возвращать 50г"
        
        print("\n✅ Тесты расчета веса пройдены")


async def run_all_tests():
    """Запускает все тесты доставки"""
    print("🧪 Запуск тестов системы доставки")
    print("=" * 60)
    
    try:
        test_suite = TestDeliverySystem()
        
        # Создаем фикстуры
        delivery_client = RussianPostClient()
        product_manager = ProductManager()
        
        # Синхронные тесты
        print("\n1. Тестирование валидации индексов...")
        test_suite.test_postcode_validation(delivery_client)
        
        print("\n2. Тестирование парсинга индексов...")
        test_suite.test_postcode_parsing(product_manager)
        
        print("\n3. Тестирование расчета веса...")
        test_suite.test_weight_calculation(product_manager)
        
        # Асинхронные тесты
        print("\n4. Тестирование расчета доставки...")
        await test_suite.test_delivery_calculation_mock(delivery_client)
        
        print("\n5. Тестирование доставки с товарами...")
        await test_suite.test_delivery_with_products(product_manager)
        
        print("\n6. Тестирование вариантов доставки...")
        await test_suite.test_delivery_options(product_manager)
        
        print("\n" + "=" * 60)
        print("🎉 Все тесты системы доставки завершены успешно!")
        print("\n📝 Примечание: Тесты используют заглушки API.")
        print("   При реальной интеграции потребуется:")
        print("   • API ключи Почты России")
        print("   • Настройка аутентификации")
        print("   • Обработка лимитов запросов")
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка тестирования: {e}")
        app_logger.error(f"Критическая ошибка тестов доставки: {e}")


if __name__ == "__main__":
    # Запускаем тесты
    asyncio.run(run_all_tests())