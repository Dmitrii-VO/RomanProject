"""
Менеджер эмбеддингов для семантического поиска товаров
"""
import os
import json
import sqlite3
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import openai
from utils.logger import app_logger


class EmbeddingsManager:
    """
    Управляет созданием, хранением и поиском по эмбеддингам товаров
    """
    
    def __init__(self, db_path: str = "data/embeddings.db"):
        """
        Инициализация менеджера эмбеддингов
        
        Args:
            db_path: Путь к базе данных SQLite
        """
        self.db_path = db_path
        self.client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OpenAI_BASE_URL")
        )
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimension = 1536
        
        # Создаем директорию для данных если не существует
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Инициализируем базу данных
        self._init_database()
        
        app_logger.info("EmbeddingsManager инициализирован")
    
    def _init_database(self):
        """Инициализирует таблицы в SQLite базе данных"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_embeddings (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    price REAL,
                    text_for_embedding TEXT NOT NULL,
                    embedding_vector TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_product_embeddings_updated_at 
                ON product_embeddings(updated_at)
            """)
            
            conn.commit()
        
        app_logger.info("База данных эмбеддингов инициализирована")
    
    def _format_product_text(self, product: Dict) -> str:
        """
        Форматирует данные товара в текст для векторизации
        
        Args:
            product: Данные товара
            
        Returns:
            Отформатированный текст
        """
        name = product.get('name', '').strip()
        description = product.get('description', '').strip()
        
        # Используем простой формат: "Название. Описание"
        if description:
            return f"{name}. {description}"
        else:
            return name
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Генерирует эмбеддинг для текста через OpenAI API
        
        Args:
            text: Текст для векторизации
            
        Returns:
            Вектор эмбеддинга
        """
        try:
            # Для Python 3.8 используем run_in_executor вместо to_thread
            import concurrent.futures
            loop = asyncio.get_event_loop()
            
            response = await loop.run_in_executor(
                None,
                lambda: self.client.embeddings.create(
                    model=self.embedding_model,
                    input=text.replace('\n', ' ')
                )
            )
            
            embedding = response.data[0].embedding
            app_logger.debug(f"Сгенерирован эмбеддинг для текста: {text[:50]}...")
            
            return embedding
            
        except Exception as e:
            app_logger.error(f"Ошибка генерации эмбеддинга: {e}")
            return []
    
    async def add_product_embedding(self, product: Dict) -> bool:
        """
        Добавляет или обновляет эмбеддинг товара
        
        Args:
            product: Данные товара
            
        Returns:
            True если успешно добавлено
        """
        try:
            product_id = product.get('id')
            if not product_id:
                app_logger.error("Отсутствует ID товара")
                return False
            
            # Форматируем текст для векторизации
            text_for_embedding = self._format_product_text(product)
            
            if not text_for_embedding.strip():
                app_logger.warning(f"Пустой текст для товара {product_id}")
                return False
            
            # Генерируем эмбеддинг
            embedding = await self.generate_embedding(text_for_embedding)
            if not embedding:
                return False
            
            # Сохраняем в базу данных
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO product_embeddings 
                    (product_id, name, description, category, price, text_for_embedding, embedding_vector, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    product_id,
                    product.get('name', ''),
                    product.get('description', ''),
                    product.get('category', ''),
                    product.get('price', 0),
                    text_for_embedding,
                    json.dumps(embedding),
                    datetime.now().isoformat()
                ))
                conn.commit()
            
            app_logger.info(f"Добавлен эмбеддинг для товара {product_id}: {product.get('name', '')}")
            return True
            
        except Exception as e:
            app_logger.error(f"Ошибка добавления эмбеддинга товара {product.get('id', 'unknown')}: {e}")
            return False
    
    async def batch_add_products(self, products: List[Dict]) -> int:
        """
        Массово добавляет эмбеддинги для списка товаров
        
        Args:
            products: Список товаров
            
        Returns:
            Количество успешно обработанных товаров
        """
        success_count = 0
        
        for product in products:
            if await self.add_product_embedding(product):
                success_count += 1
            
            # Небольшая пауза между запросами к OpenAI
            await asyncio.sleep(0.1)
        
        app_logger.info(f"Массово обработано {success_count}/{len(products)} товаров")
        return success_count
    
    def get_existing_product_ids(self) -> set:
        """
        Получает список ID товаров, для которых уже есть эмбеддинги
        
        Returns:
            Множество ID товаров
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT product_id FROM product_embeddings")
                product_ids = {row[0] for row in cursor.fetchall()}
            
            app_logger.debug(f"В базе найдено {len(product_ids)} товаров с эмбеддингами")
            return product_ids
            
        except Exception as e:
            app_logger.error(f"Ошибка получения существующих товаров: {e}")
            return set()
    
    async def semantic_search(self, query: str, limit: int = 10, threshold: float = 0.5) -> List[Dict]:
        """
        Выполняет семантический поиск товаров
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            threshold: Минимальный порог сходства (0.0-1.0)
            
        Returns:
            Список похожих товаров с оценками релевантности
        """
        try:
            # Генерируем эмбеддинг для запроса
            query_embedding = await self.generate_embedding(query)
            if not query_embedding:
                return []
            
            # Получаем все товары с эмбеддингами
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT product_id, name, description, category, price, 
                           text_for_embedding, embedding_vector 
                    FROM product_embeddings
                """)
                
                results = []
                query_vector = np.array(query_embedding).reshape(1, -1)
                
                for row in cursor.fetchall():
                    product_id, name, description, category, price, text, embedding_json = row
                    
                    # Парсим эмбеддинг товара
                    product_embedding = json.loads(embedding_json)
                    product_vector = np.array(product_embedding).reshape(1, -1)
                    
                    # Вычисляем косинусное сходство
                    similarity = cosine_similarity(query_vector, product_vector)[0][0]
                    
                    # Фильтруем по порогу релевантности
                    if similarity >= threshold:
                        results.append({
                            'id': product_id,
                            'name': name,
                            'description': description,
                            'category': category,
                            'price': price,
                            'similarity_score': float(similarity),
                            'text_used': text
                        })
                
                # Сортируем по убыванию релевантности
                results.sort(key=lambda x: x['similarity_score'], reverse=True)
                
                # Ограничиваем количество результатов
                results = results[:limit]
                
                app_logger.info(f"Семантический поиск '{query}': найдено {len(results)} товаров")
                
                return results
                
        except Exception as e:
            app_logger.error(f"Ошибка семантического поиска: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """
        Получает статистику по эмбеддингам
        
        Returns:
            Словарь со статистикой
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Общее количество товаров
                cursor = conn.execute("SELECT COUNT(*) FROM product_embeddings")
                total_count = cursor.fetchone()[0]
                
                # Последнее обновление
                cursor = conn.execute(
                    "SELECT MAX(updated_at) FROM product_embeddings"
                )
                last_update = cursor.fetchone()[0]
                
                # Распределение по категориям
                cursor = conn.execute("""
                    SELECT category, COUNT(*) 
                    FROM product_embeddings 
                    GROUP BY category
                    ORDER BY COUNT(*) DESC
                """)
                categories = dict(cursor.fetchall())
            
            return {
                'total_products': total_count,
                'last_update': last_update,
                'categories_distribution': categories,
                'embedding_model': self.embedding_model,
                'embedding_dimension': self.embedding_dimension
            }
            
        except Exception as e:
            app_logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    async def cleanup_outdated_embeddings(self, existing_product_ids: set) -> int:
        """
        Удаляет эмбеддинги для товаров, которые больше не существуют
        
        Args:
            existing_product_ids: Множество ID существующих товаров
            
        Returns:
            Количество удаленных записей
        """
        try:
            # Получаем ID товаров в базе эмбеддингов
            stored_ids = self.get_existing_product_ids()
            
            # Находим устаревшие ID
            outdated_ids = stored_ids - existing_product_ids
            
            if not outdated_ids:
                app_logger.info("Устаревших эмбеддингов не найдено")
                return 0
            
            # Удаляем устаревшие записи
            with sqlite3.connect(self.db_path) as conn:
                placeholders = ','.join(['?' for _ in outdated_ids])
                conn.execute(
                    f"DELETE FROM product_embeddings WHERE product_id IN ({placeholders})",
                    list(outdated_ids)
                )
                conn.commit()
            
            app_logger.info(f"Удалено {len(outdated_ids)} устаревших эмбеддингов")
            return len(outdated_ids)
            
        except Exception as e:
            app_logger.error(f"Ошибка очистки устаревших эмбеддингов: {e}")
            return 0