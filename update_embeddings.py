#!/usr/bin/env python3
"""
Админ-команда для обновления эмбеддингов товаров
"""
import asyncio
import argparse
import sys
from datetime import datetime
from src.search.embeddings_manager import EmbeddingsManager
from src.catalog.product_manager import ProductManager
from utils.logger import app_logger


async def full_update(embeddings_manager: EmbeddingsManager, product_manager: ProductManager):
    """Полное обновление всех эмбеддингов"""
    print("🔄 Начинаем полное обновление эмбеддингов...")
    
    # Получаем все товары из МойСклад
    print("📦 Загружаем товары из МойСклад...")
    all_products = await product_manager.search_products("", budget_min=None, budget_max=None, category=None)
    
    if not all_products:
        print("❌ Товары не найдены в МойСклад")
        return False
    
    print(f"✅ Загружено {len(all_products)} товаров")
    
    # Получаем существующие ID товаров
    current_product_ids = {product['id'] for product in all_products}
    
    # Очищаем устаревшие эмбеддинги
    print("🧹 Удаляем устаревшие эмбеддинги...")
    deleted_count = await embeddings_manager.cleanup_outdated_embeddings(current_product_ids)
    if deleted_count > 0:
        print(f"🗑️ Удалено {deleted_count} устаревших эмбеддингов")
    
    # Массово добавляем/обновляем эмбеддинги
    print("🤖 Генерируем эмбеддинги...")
    success_count = await embeddings_manager.batch_add_products(all_products)
    
    print(f"✅ Успешно обработано {success_count}/{len(all_products)} товаров")
    
    # Показываем статистику
    stats = embeddings_manager.get_stats()
    print(f"\n📊 Статистика эмбеддингов:")
    print(f"   • Всего товаров: {stats.get('total_products', 0)}")
    print(f"   • Модель: {stats.get('embedding_model', 'N/A')}")
    print(f"   • Размерность: {stats.get('embedding_dimension', 'N/A')}")
    print(f"   • Последнее обновление: {stats.get('last_update', 'N/A')}")
    
    categories = stats.get('categories_distribution', {})
    if categories:
        print(f"   • Категории:")
        for category, count in categories.items():
            print(f"     - {category or 'Без категории'}: {count}")
    
    return True


async def incremental_update(embeddings_manager: EmbeddingsManager, product_manager: ProductManager):
    """Инкрементальное обновление только новых товаров"""
    print("🔄 Начинаем инкрементальное обновление...")
    
    # Получаем все товары из МойСклад
    print("📦 Загружаем товары из МойСклад...")
    all_products = await product_manager.search_products("", budget_min=None, budget_max=None, category=None)
    
    if not all_products:
        print("❌ Товары не найдены в МойСклад")
        return False
    
    # Получаем ID товаров с существующими эмбеддингами
    existing_ids = embeddings_manager.get_existing_product_ids()
    
    # Фильтруем только новые товары
    new_products = [product for product in all_products if product['id'] not in existing_ids]
    
    if not new_products:
        print("✅ Новых товаров не найдено, обновление не требуется")
        return True
    
    print(f"🆕 Найдено {len(new_products)} новых товаров")
    
    # Обрабатываем только новые товары
    success_count = await embeddings_manager.batch_add_products(new_products)
    
    print(f"✅ Успешно добавлено {success_count}/{len(new_products)} новых товаров")
    
    return True


async def test_search(embeddings_manager: EmbeddingsManager, query: str):
    """Тестирует семантический поиск"""
    print(f"🔍 Тестируем семантический поиск: '{query}'")
    
    results = await embeddings_manager.semantic_search(query, limit=5, threshold=0.3)
    
    if not results:
        print("❌ Результатов не найдено")
        return
    
    print(f"✅ Найдено {len(results)} результатов:")
    
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result['name']} (сходство: {result['similarity_score']:.3f})")
        print(f"     💰 {result['price']:.0f}₽ | 📂 {result.get('category', 'Без категории')}")
        if result.get('description'):
            desc = result['description'][:80]
            print(f"     📝 {desc}{'...' if len(result['description']) > 80 else ''}")
        print()


async def show_stats(embeddings_manager: EmbeddingsManager):
    """Показывает статистику эмбеддингов"""
    print("📊 Статистика эмбеддингов:")
    
    stats = embeddings_manager.get_stats()
    
    if not stats:
        print("❌ Нет данных для отображения")
        return
    
    print(f"   • Всего товаров: {stats.get('total_products', 0)}")
    print(f"   • Модель: {stats.get('embedding_model', 'N/A')}")
    print(f"   • Размерность векторов: {stats.get('embedding_dimension', 'N/A')}")
    print(f"   • Последнее обновление: {stats.get('last_update', 'N/A')}")
    
    categories = stats.get('categories_distribution', {})
    if categories:
        print(f"   • Распределение по категориям:")
        for category, count in categories.items():
            print(f"     - {category or 'Без категории'}: {count} товаров")


async def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Управление эмбеддингами товаров")
    
    parser.add_argument("--full", action="store_true", 
                       help="Полное обновление всех эмбеддингов")
    parser.add_argument("--incremental", action="store_true", 
                       help="Обновление только новых товаров")
    parser.add_argument("--test", type=str, metavar="QUERY",
                       help="Тестировать поиск с заданным запросом")
    parser.add_argument("--stats", action="store_true",
                       help="Показать статистику эмбеддингов")
    
    args = parser.parse_args()
    
    if not any([args.full, args.incremental, args.test, args.stats]):
        parser.print_help()
        return
    
    try:
        # Инициализируем менеджеры
        embeddings_manager = EmbeddingsManager()
        product_manager = ProductManager()
        
        print(f"🚀 Запуск обновления эмбеддингов: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        if args.stats:
            await show_stats(embeddings_manager)
        
        if args.full:
            success = await full_update(embeddings_manager, product_manager)
            if not success:
                sys.exit(1)
        
        if args.incremental:
            success = await incremental_update(embeddings_manager, product_manager)
            if not success:
                sys.exit(1)
        
        if args.test:
            await test_search(embeddings_manager, args.test)
        
        print("=" * 60)
        print("🎉 Операция завершена успешно!")
        
    except KeyboardInterrupt:
        print("\n⏹️ Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        app_logger.error(f"Критическая ошибка обновления эмбеддингов: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())