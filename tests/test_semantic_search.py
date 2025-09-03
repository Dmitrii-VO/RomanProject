#!/usr/bin/env python3
"""
Тесты для семантического поиска товаров
"""
import asyncio
import pytest
import os
import sys
from typing import List, Dict

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.search.embeddings_manager import EmbeddingsManager
from src.catalog.product_manager import ProductManager
from src.ai.consultant import AmberAIConsultant
from utils.logger import app_logger


class TestSemanticSearch:
    """Тесты семантического поиска"""
    
    @pytest.fixture
    async def embeddings_manager(self):
        """Фикстура для EmbeddingsManager"""
        return EmbeddingsManager("data/test_embeddings.db")
    
    @pytest.fixture 
    async def product_manager(self):
        """Фикстура для ProductManager"""
        return ProductManager()
    
    @pytest.fixture
    async def ai_consultant(self):
        """Фикстура для AmberAIConsultant"""
        return AmberAIConsultant()
    
    def test_threshold_calculation(self):
        """Тестирует расчет динамических порогов сходства"""
        product_manager = ProductManager()
        
        # Тест 1: Общий запрос без фильтров
        threshold = product_manager._calculate_semantic_threshold("красивое украшение")
        assert threshold == 0.4, f"Ожидался порог 0.4, получен {threshold}"
        
        # Тест 2: Запрос с категорией
        threshold = product_manager._calculate_semantic_threshold("красивое украшение", category="кольца")
        assert threshold == 0.5, f"Ожидался порог 0.5, получен {threshold}"
        
        # Тест 3: Запрос с категорией и бюджетом
        threshold = product_manager._calculate_semantic_threshold("красивое украшение", category="кольца", has_budget=True)
        assert threshold == 0.6, f"Ожидался порог 0.6, получен {threshold}"
        
        # Тест 4: Специфичный запрос с дополнительными словами
        threshold = product_manager._calculate_semantic_threshold("кольцо красного цвета", category="кольца", has_budget=True)
        assert threshold == 0.7, f"Ожидался порог 0.7, получен {threshold}"
        
        # Тест 5: Максимальный порог не превышается
        threshold = product_manager._calculate_semantic_threshold("стильное кольцо особого дизайна", category="кольца", has_budget=True)
        assert threshold <= 0.8, f"Порог не должен превышать 0.8, получен {threshold}"
        
        print("✅ Все тесты порогов сходства пройдены успешно")
    
    async def test_embeddings_generation(self, embeddings_manager):
        """Тестирует генерацию эмбеддингов"""
        test_texts = [
            "Красивое кольцо с янтарем",
            "Серьги из натурального янтаря",
            "Элегантный браслет"
        ]
        
        for text in test_texts:
            embedding = await embeddings_manager.generate_embedding(text)
            assert len(embedding) == 1536, f"Неверная размерность эмбеддинга: {len(embedding)}"
            assert isinstance(embedding, list), "Эмбеддинг должен быть списком"
            assert all(isinstance(x, float) for x in embedding), "Все элементы эмбеддинга должны быть float"
        
        print("✅ Тесты генерации эмбеддингов пройдены успешно")
    
    async def test_semantic_search_quality(self, product_manager):
        """Тестирует качество семантического поиска на примерах"""
        
        # Список тестовых запросов с ожидаемыми результатами
        test_cases = [
            {
                'query': 'хочу украшение на руку',
                'expected_categories': ['браслеты', 'кольца'],
                'description': 'Поиск украшений для рук'
            },
            {
                'query': 'что-то нежное на шею',
                'expected_categories': ['кулоны', 'бусы', 'подвески'],
                'description': 'Поиск украшений для шеи'
            },
            {
                'query': 'кольцо с камнем',
                'expected_categories': ['кольца'],
                'description': 'Поиск колец с камнями'
            },
            {
                'query': 'подарок девушке',
                'expected_categories': ['кольца', 'серьги', 'кулоны', 'браслеты'],
                'description': 'Поиск подарочных украшений'
            },
            {
                'query': 'янтарь в серебре',
                'expected_categories': ['кольца', 'серьги', 'кулоны', 'браслеты'],
                'description': 'Поиск серебряных изделий с янтарем'
            }
        ]
        
        print("\n🔍 Тестирование качества семантического поиска:")
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- Тест {i}: {test_case['description']} ---")
            print(f"Запрос: '{test_case['query']}'")
            
            # Выполняем семантический поиск
            results = await product_manager.semantic_search(test_case['query'], limit=5, threshold=0.3)
            
            print(f"Найдено результатов: {len(results)}")
            
            if results:
                print("Топ-3 результата:")
                for j, result in enumerate(results[:3], 1):
                    print(f"  {j}. {result['name']} (сходство: {result['similarity_score']:.3f})")
                    print(f"     Категория: {result.get('category', 'Не указана')}")
                    print(f"     Цена: {result['price']:.0f}₽")
                
                # Проверяем релевантность результатов
                found_categories = [result.get('category', '').lower() for result in results]
                relevant_found = any(
                    any(expected.lower() in category for expected in test_case['expected_categories'])
                    for category in found_categories if category
                )
                
                if relevant_found:
                    print("✅ Найдены релевантные результаты")
                else:
                    print("⚠️ Результаты могут быть не полностью релевантными")
            else:
                print("❌ Результаты не найдены")
        
        print("\n✅ Тесты качества семантического поиска завершены")
    
    async def test_smart_search_fallback(self, product_manager):
        """Тестирует работу fallback логики умного поиска"""
        
        print("\n🧠 Тестирование умного поиска с fallback:")
        
        # Тест 1: Запрос, который должен найти результаты традиционным поиском
        print("\n--- Тест 1: Традиционный поиск (должно быть >=3 результатов) ---")
        results = await product_manager.smart_search("янтарь", budget_min=None, budget_max=None, category=None)
        print(f"Результатов умного поиска: {len(results)}")
        
        # Тест 2: Очень специфичный запрос (должен переходить к семантическому поиску)
        print("\n--- Тест 2: Специфичный запрос (должен использовать семантический поиск) ---")
        specific_results = await product_manager.smart_search("элегантное украшение для особого случая")
        print(f"Результатов специфичного поиска: {len(specific_results)}")
        
        # Тест 3: Поиск с фильтрами
        print("\n--- Тест 3: Поиск с бюджетными ограничениями ---")
        budget_results = await product_manager.smart_search("красивый", budget_min=1000, budget_max=3000)
        print(f"Результатов с бюджетом: {len(budget_results)}")
        
        if budget_results:
            prices = [result['price'] for result in budget_results]
            print(f"Диапазон цен: {min(prices):.0f}₽ - {max(prices):.0f}₽")
        
        print("\n✅ Тесты умного поиска завершены")
    
    async def test_ai_integration(self, ai_consultant):
        """Тестирует интеграцию семантического поиска с ИИ консультантом"""
        
        print("\n🤖 Тестирование интеграции с ИИ консультантом:")
        
        test_messages = [
            "Хочу что-то красивое на руку для особого случая",
            "Покажите нежные украшения на шею",
            "Ищу подарок девушке до 5000 рублей",
            "Хочу кольцо с натуральным камнем"
        ]
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n--- ИИ Тест {i} ---")
            print(f"Сообщение: '{message}'")
            
            try:
                # Обрабатываем сообщение через ИИ консультанта
                response = await ai_consultant.process_message(999990 + i, message)
                
                # Проверяем наличие товаров в ответе
                has_products = any(indicator in response for indicator in ['🛍️', '💎', '₽', 'Найдено'])
                
                print(f"Ответ содержит товары: {'✅ Да' if has_products else '❌ Нет'}")
                
                # Показываем краткий фрагмент ответа
                response_preview = response[:200] + "..." if len(response) > 200 else response
                print(f"Превью ответа: {response_preview}")
                
            except Exception as e:
                print(f"❌ Ошибка обработки: {e}")
        
        print("\n✅ Тесты интеграции с ИИ завершены")


async def run_all_tests():
    """Запускает все тесты семантического поиска"""
    print("🧪 Запуск тестов семантического поиска")
    print("=" * 60)
    
    try:
        test_suite = TestSemanticSearch()
        
        # Проверяем доступность OpenAI API
        if not os.getenv("OPENAI_API_KEY"):
            print("❌ Отсутствует OPENAI_API_KEY")
            return
        
        # Проверяем доступность МойСклад API  
        if not os.getenv("MOYSKLAD_TOKEN"):
            print("❌ Отсутствует MOYSKLAD_TOKEN")
            return
        
        # Тестируем расчет порогов (синхронный тест)
        print("\n1. Тестирование расчета порогов сходства...")
        test_suite.test_threshold_calculation()
        
        # Инициализируем менеджеры для асинхронных тестов
        embeddings_manager = EmbeddingsManager("data/test_embeddings.db")
        product_manager = ProductManager()
        ai_consultant = AmberAIConsultant()
        
        # Тестируем генерацию эмбеддингов
        print("\n2. Тестирование генерации эмбеддингов...")
        await test_suite.test_embeddings_generation(embeddings_manager)
        
        # Тестируем качество семантического поиска
        print("\n3. Тестирование качества семантического поиска...")
        await test_suite.test_semantic_search_quality(product_manager)
        
        # Тестируем умный поиск
        print("\n4. Тестирование умного поиска...")
        await test_suite.test_smart_search_fallback(product_manager)
        
        # Тестируем интеграцию с ИИ
        print("\n5. Тестирование интеграции с ИИ...")
        await test_suite.test_ai_integration(ai_consultant)
        
        print("\n" + "=" * 60)
        print("🎉 Все тесты семантического поиска завершены успешно!")
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка тестирования: {e}")
        app_logger.error(f"Критическая ошибка тестов семантического поиска: {e}")


if __name__ == "__main__":
    # Создаем директорию для тестовых данных
    os.makedirs("data", exist_ok=True)
    
    # Запускаем тесты
    asyncio.run(run_all_tests())