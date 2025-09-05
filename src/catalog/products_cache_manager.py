"""
Менеджер локального кэша товаров для ускорения поиска
"""
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from utils.logger import app_logger
from src.integrations.moysklad_client import MoySkladClient
from src.search.embeddings_manager import EmbeddingsManager


class ProductsCacheManager:
    """
    Управляет локальным кэшем товаров для быстрого поиска
    
    Функции:
    - Синхронизация с МойСклад каждые 12 часов
    - Локальное хранение товаров в SQLite
    - Быстрый поиск без API вызовов
    - Fallback на МойСклад при сбоях
    """
    
    def __init__(self, db_path: str = "data/products_cache.db"):
        """
        Инициализация менеджера кэша товаров
        
        Args:
            db_path: Путь к локальной базе данных товаров
        """
        self.db_path = db_path
        self.moysklad_client = MoySkladClient()
        self.embeddings_manager = EmbeddingsManager()
        
        # Настройки синхронизации
        self.sync_interval_hours = 12
        self.max_cache_age_hours = 24  # Максимальный возраст кэша
        
        # Создаем директорию для данных
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Инициализируем базу данных
        self._init_database()
        
        app_logger.info("ProductsCacheManager инициализирован")
    
    def _init_database(self):
        """Создает таблицы для локального кэша товаров"""
        with sqlite3.connect(self.db_path) as conn:
            # Основная таблица товаров
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cached_products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    price REAL,
                    stock INTEGER DEFAULT 0,
                    article TEXT,
                    weight REAL DEFAULT 0,
                    volume REAL DEFAULT 0,
                    images TEXT,  -- JSON array of image URLs
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Индексы для быстрого поиска
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cached_products_name ON cached_products(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cached_products_category ON cached_products(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cached_products_price ON cached_products(price)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cached_products_stock ON cached_products(stock)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cached_products_updated ON cached_products(last_updated)")
            
            # Таблица метаданных кэша
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Вставляем начальные метаданные
            conn.execute("""
                INSERT OR IGNORE INTO cache_metadata (key, value) 
                VALUES ('last_full_sync', '1970-01-01 00:00:00')
            """)
            
            conn.commit()
        
        app_logger.info("База данных локального кэша товаров инициализирована")
    
    async def sync_from_moysklad(self, force: bool = False) -> Dict:
        """
        Синхронизирует товары из МойСклад в локальный кэш
        
        Args:
            force: Принудительная синхронизация независимо от времени
            
        Returns:
            Статистика синхронизации
        """
        try:
            # Проверяем, нужна ли синхронизация
            if not force and not self._should_sync():
                return {"status": "skipped", "reason": "sync not needed"}
            
            app_logger.info("Начинаем синхронизацию товаров из МойСклад")
            start_time = datetime.now()
            
            # Загружаем товары из МойСклад
            moysklad_products = await self.moysklad_client.get_products(limit=1000)
            
            if not moysklad_products:
                app_logger.warning("МойСклад вернул пустой список товаров")
                return {"status": "error", "reason": "no products from moysklad"}
            
            # Синхронизируем с локальной базой
            stats = await self._sync_products_to_cache(moysklad_products)
            
            # Обновляем метаданные
            self._update_sync_metadata(start_time)
            
            # Синхронизируем эмбеддинги
            await self._sync_embeddings()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            result = {
                "status": "success",
                "duration_seconds": duration,
                "products_processed": stats["processed"],
                "products_updated": stats["updated"],
                "products_added": stats["added"],
                "products_removed": stats["removed"]
            }
            
            app_logger.info(f"Синхронизация завершена: {result}")
            return result
            
        except Exception as e:
            app_logger.error(f"Ошибка синхронизации с МойСклад: {e}")
            return {"status": "error", "reason": str(e)}
    
    def _should_sync(self) -> bool:
        """Проверяет, нужна ли синхронизация на основе времени последней синхронизации"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value FROM cache_metadata WHERE key = 'last_full_sync'"
                )
                result = cursor.fetchone()
                
                if not result:
                    return True
                
                last_sync = datetime.fromisoformat(result[0])
                time_since_sync = datetime.now() - last_sync
                
                should_sync = time_since_sync.total_seconds() / 3600 >= self.sync_interval_hours
                
                if should_sync:
                    app_logger.info(f"Синхронизация нужна: прошло {time_since_sync} с последней")
                else:
                    app_logger.debug(f"Синхронизация не нужна: прошло {time_since_sync} с последней")
                
                return should_sync
                
        except Exception as e:
            app_logger.error(f"Ошибка проверки необходимости синхронизации: {e}")
            return True
    
    async def _sync_products_to_cache(self, moysklad_products: List[Dict]) -> Dict:
        """Синхронизирует список товаров с локальным кэшем"""
        stats = {"processed": 0, "updated": 0, "added": 0, "removed": 0}
        
        # Получаем существующие ID товаров
        existing_ids = set()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id FROM cached_products")
            existing_ids = {row[0] for row in cursor.fetchall()}
        
        moysklad_ids = set()
        
        # Обновляем/добавляем товары
        with sqlite3.connect(self.db_path) as conn:
            for product in moysklad_products:
                try:
                    product_id = product['id']
                    moysklad_ids.add(product_id)
                    
                    # Подготавливаем данные для вставки
                    images_json = json.dumps(product.get('images', []))
                    
                    # Проверяем, существует ли товар
                    cursor = conn.execute(
                        "SELECT id FROM cached_products WHERE id = ?", 
                        (product_id,)
                    )
                    exists = cursor.fetchone() is not None
                    
                    if exists:
                        # Обновляем существующий товар
                        conn.execute("""
                            UPDATE cached_products SET
                                name = ?, description = ?, category = ?, price = ?,
                                stock = ?, article = ?, weight = ?, volume = ?,
                                images = ?, last_updated = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (
                            product['name'], product.get('description', ''),
                            product.get('category', ''), product.get('price', 0),
                            product.get('stock', 0), product.get('article', ''),
                            product.get('weight', 0), product.get('volume', 0),
                            images_json, product_id
                        ))
                        stats["updated"] += 1
                    else:
                        # Добавляем новый товар
                        conn.execute("""
                            INSERT INTO cached_products 
                            (id, name, description, category, price, stock, article, weight, volume, images)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            product_id, product['name'], product.get('description', ''),
                            product.get('category', ''), product.get('price', 0),
                            product.get('stock', 0), product.get('article', ''),
                            product.get('weight', 0), product.get('volume', 0),
                            images_json
                        ))
                        stats["added"] += 1
                    
                    stats["processed"] += 1
                    
                except Exception as e:
                    app_logger.error(f"Ошибка обработки товара {product.get('id', 'unknown')}: {e}")
            
            # Удаляем товары, которых больше нет в МойСклад
            obsolete_ids = existing_ids - moysklad_ids
            if obsolete_ids:
                placeholders = ','.join(['?' for _ in obsolete_ids])
                conn.execute(
                    f"DELETE FROM cached_products WHERE id IN ({placeholders})",
                    list(obsolete_ids)
                )
                stats["removed"] = len(obsolete_ids)
            
            conn.commit()
        
        return stats
    
    def _update_sync_metadata(self, sync_time: datetime):
        """Обновляет метаданные о последней синхронизации"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache_metadata (key, value, updated_at)
                VALUES ('last_full_sync', ?, CURRENT_TIMESTAMP)
            """, (sync_time.isoformat(),))
            conn.commit()
    
    async def _sync_embeddings(self):
        """Синхронизирует эмбеддинги для новых товаров"""
        try:
            # Получаем товары из кэша
            cached_products = await self.get_all_cached_products()
            
            # Получаем существующие эмбеддинги
            existing_embedding_ids = self.embeddings_manager.get_existing_product_ids()
            
            # Находим товары без эмбеддингов
            products_without_embeddings = [
                product for product in cached_products
                if product['id'] not in existing_embedding_ids
            ]
            
            if products_without_embeddings:
                app_logger.info(f"Создаем эмбеддинги для {len(products_without_embeddings)} новых товаров")
                created = await self.embeddings_manager.batch_add_products(products_without_embeddings)
                app_logger.info(f"Создано {created} эмбеддингов")
            
            # Очищаем устаревшие эмбеддинги
            current_product_ids = {p['id'] for p in cached_products}
            removed = await self.embeddings_manager.cleanup_outdated_embeddings(current_product_ids)
            if removed:
                app_logger.info(f"Удалено {removed} устаревших эмбеддингов")
                
        except Exception as e:
            app_logger.error(f"Ошибка синхронизации эмбеддингов: {e}")
    
    async def get_all_cached_products(self) -> List[Dict]:
        """Получает все товары из локального кэша"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id, name, description, category, price, stock, 
                           article, weight, volume, images, last_updated
                    FROM cached_products
                    ORDER BY last_updated DESC
                """)
                
                products = []
                for row in cursor.fetchall():
                    images = json.loads(row[9]) if row[9] else []
                    products.append({
                        'id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'category': row[3],
                        'price': row[4],
                        'stock': row[5],
                        'article': row[6],
                        'weight': row[7],
                        'volume': row[8],
                        'images': images,
                        'last_updated': row[10]
                    })
                
                return products
                
        except Exception as e:
            app_logger.error(f"Ошибка получения товаров из кэша: {e}")
            return []
    
    def _normalize_search_query(self, query: str) -> str:
        """
        Нормализует поисковый запрос для лучшего поиска
        Приводит слова к корневой форме для поиска
        """
        if not query:
            return query
            
        # Простая нормализация для основных категорий товаров
        query_lower = query.lower().strip()
        
        # Убираем окончания для лучшего поиска
        word_mappings = {
            'кольца': 'кольц',
            'кольцо': 'кольц',
            'серьги': 'серьг',
            'сережки': 'серьг',
            'браслеты': 'браслет',
            'браслет': 'браслет',
            'кулоны': 'кулон',
            'подвески': 'подвеск',
            'подвеска': 'подвеск',
            'бусы': 'бус',
            'ожерелье': 'ожерель',
            'брошки': 'брош',
            'брошь': 'брош'
        }
        
        # Заменяем известные слова на корневые формы
        words = query_lower.split()
        normalized_words = []
        
        for word in words:
            # Убираем знаки препинания
            clean_word = word.strip('.,!?;:')
            # Заменяем на корневую форму если есть
            normalized_word = word_mappings.get(clean_word, clean_word)
            normalized_words.append(normalized_word)
        
        result = ' '.join(normalized_words)
        app_logger.debug(f"Нормализация запроса: '{query}' -> '{result}'")
        return result

    async def search_cached_products(
        self, 
        query: str = None,
        category: str = None,
        price_min: float = None,
        price_max: float = None,
        in_stock_only: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """
        Быстрый поиск товаров в локальном кэше
        
        Args:
            query: Поисковый запрос по названию/описанию
            category: Фильтр по категории
            price_min: Минимальная цена
            price_max: Максимальная цена
            in_stock_only: Только товары в наличии
            limit: Лимит результатов
            
        Returns:
            Список найденных товаров
        """
        try:
            # Строим SQL запрос
            sql_parts = ["SELECT * FROM cached_products WHERE 1=1"]
            params = []
            
            # Фильтр по тексту (поиск без SQLite LOWER для кириллицы)
            text_filter_needed = bool(query)
            
            # Фильтр по категории
            if category:
                sql_parts.append("AND category LIKE ?")
                params.append(f"%{category}%")
            
            # Фильтр по цене
            if price_min is not None:
                sql_parts.append("AND price >= ?")
                params.append(price_min)
            
            if price_max is not None:
                sql_parts.append("AND price <= ?")
                params.append(price_max)
            
            # Фильтр по наличию
            if in_stock_only:
                sql_parts.append("AND stock > 0")
            
            # Сортировка (лимит применяем в Python после фильтрации по тексту)
            sql_parts.append("ORDER BY last_updated DESC")
            
            sql_query = " ".join(sql_parts)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(sql_query, params)
                
                products = []
                for row in cursor.fetchall():
                    images = json.loads(row[9]) if row[9] else []
                    product = {
                        'id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'category': row[3],
                        'price': row[4],
                        'stock': row[5],
                        'article': row[6],
                        'weight': row[7],
                        'volume': row[8],
                        'images': images,
                        'last_updated': row[10]
                    }
                    
                    # Фильтрация по тексту в Python (для корректной работы с кириллицей)
                    if text_filter_needed:
                        normalized_query = self._normalize_search_query(query).lower()
                        product_name = product['name'].lower()
                        product_desc = (product['description'] or '').lower()
                        
                        # Проверяем содержат ли товары релевантные термины
                        # Если запрос общий (покажите, фотографии и т.д.) - не фильтруем
                        general_terms = ['покажите', 'фотографии', 'фото', 'картинки', 'изображения', 
                                       'варианты', 'примеры', 'что есть', 'ассортимент', 'товары']
                        
                        is_general_query = any(term in normalized_query for term in general_terms)
                        
                        if not is_general_query and normalized_query not in product_name and normalized_query not in product_desc:
                            continue
                    
                    products.append(product)
                
                # Ограничиваем результат
                if limit and len(products) > limit:
                    products = products[:limit]
                
                app_logger.info(f"Найдено {len(products)} товаров в локальном кэше")
                return products
                
        except Exception as e:
            app_logger.error(f"Ошибка поиска в локальном кэше: {e}")
            return []
    
    def is_cache_fresh(self) -> bool:
        """Проверяет свежесть кэша (не старше 24 часов)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value FROM cache_metadata WHERE key = 'last_full_sync'"
                )
                result = cursor.fetchone()
                
                if not result:
                    return False
                
                last_sync = datetime.fromisoformat(result[0])
                age_hours = (datetime.now() - last_sync).total_seconds() / 3600
                
                return age_hours < self.max_cache_age_hours
                
        except Exception as e:
            app_logger.error(f"Ошибка проверки свежести кэша: {e}")
            return False
    
    def get_cache_stats(self) -> Dict:
        """Получает статистику локального кэша"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Общее количество товаров
                cursor = conn.execute("SELECT COUNT(*) FROM cached_products")
                total_products = cursor.fetchone()[0]
                
                # Товары в наличии
                cursor = conn.execute("SELECT COUNT(*) FROM cached_products WHERE stock > 0")
                in_stock = cursor.fetchone()[0]
                
                # Последняя синхронизация
                cursor = conn.execute(
                    "SELECT value FROM cache_metadata WHERE key = 'last_full_sync'"
                )
                last_sync_result = cursor.fetchone()
                last_sync = last_sync_result[0] if last_sync_result else None
                
                # Средняя цена
                cursor = conn.execute("SELECT AVG(price) FROM cached_products WHERE price > 0")
                avg_price = cursor.fetchone()[0] or 0
                
                return {
                    'total_products': total_products,
                    'in_stock': in_stock,
                    'out_of_stock': total_products - in_stock,
                    'last_sync': last_sync,
                    'cache_fresh': self.is_cache_fresh(),
                    'average_price': round(avg_price, 2)
                }
                
        except Exception as e:
            app_logger.error(f"Ошибка получения статистики кэша: {e}")
            return {}