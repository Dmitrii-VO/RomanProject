"""
Хранилище и векторная база данных для переписок RAG
"""
import os
import json
import sqlite3
import re
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import openai
from utils.logger import app_logger


class ConversationStore:
    """
    Векторное хранилище для переписок с эмбеддингами
    """
    
    def __init__(self, db_path: str = "data/conversations_rag.db"):
        """
        Инициализация хранилища переписок
        
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
        
        app_logger.info("ConversationStore инициализирован")
    
    def _init_database(self):
        """Инициализирует таблицы в SQLite базе данных"""
        with sqlite3.connect(self.db_path) as conn:
            # Основная таблица с сообщениями
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE,
                    customer_id TEXT NOT NULL,
                    deal_id TEXT,
                    sender_type TEXT NOT NULL, -- 'customer', 'bot', 'manager'
                    content TEXT NOT NULL,
                    cleaned_content TEXT NOT NULL, -- без PII
                    timestamp DATETIME NOT NULL,
                    intent TEXT,
                    category TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создаем индексы отдельно
            conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_id ON conversation_messages(customer_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_deal_id ON conversation_messages(deal_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sender_type ON conversation_messages(sender_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON conversation_messages(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_intent ON conversation_messages(intent)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON conversation_messages(category)")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL, -- JSON эмбеддинг
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES conversation_messages (message_id)
                )
            """)
            
            # Индекс для чанков
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_message_id ON conversation_chunks(message_id)")
            
            # Метаданные для статистики и конфигурации
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rag_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
        app_logger.info("База данных RAG переписок инициализирована")
    
    def _clean_content(self, content: str) -> str:
        """
        Очищает содержимое от персональных данных (PII)
        
        Args:
            content: Исходное содержимое
            
        Returns:
            Очищенное содержимое
        """
        if not content:
            return content
        
        cleaned = content
        
        # Маскируем номера телефонов
        phone_pattern = r'(\+7|8|7)?[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{2})[\s\-\(\)]?(\d{2})'
        cleaned = re.sub(phone_pattern, '[PHONE]', cleaned)
        
        # Маскируем email адреса  
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        cleaned = re.sub(email_pattern, '[EMAIL]', cleaned)
        
        # Маскируем адреса (простое определение по ключевым словам)
        address_keywords = ['улица', 'ул.', 'проспект', 'пр.', 'переулок', 'пер.', 'дом', 'д.', 'квартира', 'кв.']
        for keyword in address_keywords:
            if keyword in cleaned.lower():
                # Заменяем следующие за ключевым словом числа и названия
                pattern = rf'{keyword}[\s]*[А-Яа-я0-9\s\-,.]{{1,50}}'
                cleaned = re.sub(pattern, f'{keyword} [ADDRESS]', cleaned, flags=re.IGNORECASE)
        
        # Маскируем имена (простое определение - слова с заглавной буквы длиной 3+ символа)
        # Применяем осторожно чтобы не затронуть названия товаров
        if any(word in cleaned.lower() for word in ['меня зовут', 'мое имя', 'я ', ' я ']):
            name_pattern = r'\b[А-ЯЁ][а-яё]{2,}\b'
            potential_names = re.findall(name_pattern, cleaned)
            for name in potential_names:
                if name not in ['Янтарь', 'Браслет', 'Серьги', 'Кольцо']:  # исключаем товары
                    cleaned = cleaned.replace(name, '[NAME]')
        
        return cleaned.strip()
    
    def _split_into_chunks(self, content: str, max_chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Разбивает длинное сообщение на чанки
        
        Args:
            content: Содержимое сообщения
            max_chunk_size: Максимальный размер чанка в символах
            overlap: Перекрытие между чанками в символах
            
        Returns:
            Список чанков
        """
        if len(content) <= max_chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            # Определяем конец чанка
            end = start + max_chunk_size
            
            if end >= len(content):
                # Последний чанк
                chunks.append(content[start:])
                break
            
            # Ищем хорошее место для разрыва (точка, восклицательный знак, вопрос)
            good_break = -1
            for i in range(end, start + overlap, -1):
                if content[i] in '.!?':
                    good_break = i + 1
                    break
            
            if good_break != -1:
                chunks.append(content[start:good_break])
                start = good_break - overlap
            else:
                # Разрываем по пробелу
                space_break = content.rfind(' ', start + overlap, end)
                if space_break != -1:
                    chunks.append(content[start:space_break])
                    start = space_break - overlap + 1
                else:
                    # Принудительный разрыв
                    chunks.append(content[start:end])
                    start = end - overlap
        
        return [chunk.strip() for chunk in chunks if chunk.strip()]
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Получает эмбеддинг для текста
        
        Args:
            text: Текст для эмбеддинга
            
        Returns:
            Вектор эмбеддинга
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text.replace("\n", " ")
            )
            return response.data[0].embedding
        except Exception as e:
            app_logger.error(f"Ошибка получения эмбеддинга: {e}")
            return [0.0] * self.embedding_dimension
    
    async def store_message(self, 
                          message_id: str,
                          customer_id: str,
                          sender_type: str,
                          content: str,
                          deal_id: Optional[str] = None,
                          intent: Optional[str] = None,
                          category: Optional[str] = None) -> bool:
        """
        Сохраняет сообщение в хранилище с индексацией
        
        Args:
            message_id: Уникальный ID сообщения
            customer_id: ID клиента
            sender_type: Тип отправителя ('customer', 'bot', 'manager')
            content: Содержимое сообщения
            deal_id: ID сделки (опционально)
            intent: Намерение/интент (опционально) 
            category: Категория сообщения (опционально)
            
        Returns:
            True если успешно сохранено
        """
        try:
            # Очищаем от PII
            cleaned_content = self._clean_content(content)
            
            # Сохраняем основное сообщение
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO conversation_messages 
                    (message_id, customer_id, deal_id, sender_type, content, cleaned_content, timestamp, intent, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (message_id, customer_id, deal_id, sender_type, content, cleaned_content, 
                      datetime.now(), intent, category))
                
                # Удаляем старые чанки если есть
                conn.execute("DELETE FROM conversation_chunks WHERE message_id = ?", (message_id,))
            
            # Разбиваем на чанки и создаем эмбеддинги
            chunks = self._split_into_chunks(cleaned_content)
            
            for chunk_index, chunk_content in enumerate(chunks):
                if not chunk_content.strip():
                    continue
                
                # Получаем эмбеддинг для чанка
                embedding = self._get_embedding(chunk_content)
                
                # Сохраняем чанк с эмбеддингом
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO conversation_chunks 
                        (message_id, chunk_index, content, embedding)
                        VALUES (?, ?, ?, ?)
                    """, (message_id, chunk_index, chunk_content, json.dumps(embedding)))
            
            app_logger.info(f"Сообщение {message_id} от {customer_id} сохранено в RAG ({len(chunks)} чанков)")
            return True
            
        except Exception as e:
            app_logger.error(f"Ошибка сохранения сообщения в RAG: {e}")
            return False
    
    async def search_similar_messages(self,
                                    query: str,
                                    customer_id: Optional[str] = None,
                                    deal_id: Optional[str] = None,
                                    intent: Optional[str] = None,
                                    category: Optional[str] = None,
                                    days_back: Optional[int] = None,
                                    similarity_threshold: float = 0.6,
                                    max_results: int = 10) -> List[Dict]:
        """
        Ищет похожие сообщения в векторной базе
        
        Args:
            query: Поисковый запрос
            customer_id: Фильтр по клиенту (опционально)
            deal_id: Фильтр по сделке (опционально) 
            intent: Фильтр по интенту (опционально)
            category: Фильтр по категории (опционально)
            days_back: Количество дней назад для поиска (опционально)
            similarity_threshold: Порог схожести (0.0-1.0)
            max_results: Максимальное количество результатов
            
        Returns:
            Список похожих сообщений с метриками схожести
        """
        try:
            # Получаем эмбеддинг для запроса
            query_embedding = self._get_embedding(query)
            query_vector = np.array(query_embedding).reshape(1, -1)
            
            # Формируем SQL запрос с фильтрами
            sql_conditions = []
            sql_params = []
            
            if customer_id:
                sql_conditions.append("cm.customer_id = ?")
                sql_params.append(customer_id)
            
            if deal_id:
                sql_conditions.append("cm.deal_id = ?")
                sql_params.append(deal_id)
            
            if intent:
                sql_conditions.append("cm.intent = ?")
                sql_params.append(intent)
            
            if category:
                sql_conditions.append("cm.category = ?")
                sql_params.append(category)
            
            if days_back:
                cutoff_date = datetime.now() - timedelta(days=days_back)
                sql_conditions.append("cm.timestamp >= ?")
                sql_params.append(cutoff_date)
            
            where_clause = "WHERE " + " AND ".join(sql_conditions) if sql_conditions else ""
            
            # Получаем все чанки с метаданными
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(f"""
                    SELECT 
                        cc.message_id,
                        cc.chunk_index,
                        cc.content,
                        cc.embedding,
                        cm.customer_id,
                        cm.deal_id,
                        cm.sender_type,
                        cm.timestamp,
                        cm.intent,
                        cm.category
                    FROM conversation_chunks cc
                    JOIN conversation_messages cm ON cc.message_id = cm.message_id
                    {where_clause}
                    ORDER BY cm.timestamp DESC
                """, sql_params)
                
                results = []
                
                for row in cursor.fetchall():
                    try:
                        chunk_embedding = np.array(json.loads(row[3])).reshape(1, -1)
                        similarity = cosine_similarity(query_vector, chunk_embedding)[0][0]
                        
                        if similarity >= similarity_threshold:
                            results.append({
                                'message_id': row[0],
                                'chunk_index': row[1], 
                                'content': row[2],
                                'customer_id': row[4],
                                'deal_id': row[5],
                                'sender_type': row[6],
                                'timestamp': row[7],
                                'intent': row[8],
                                'category': row[9],
                                'similarity': similarity
                            })
                    except Exception as e:
                        app_logger.warning(f"Ошибка обработки эмбеддинга для {row[0]}: {e}")
                        continue
                
                # Сортируем по схожести и ограничиваем количество
                results.sort(key=lambda x: x['similarity'], reverse=True)
                results = results[:max_results]
                
                app_logger.info(f"Найдено {len(results)} похожих фрагментов для запроса: {query[:50]}...")
                return results
                
        except Exception as e:
            app_logger.error(f"Ошибка поиска похожих сообщений: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получает статистику хранилища переписок
        
        Returns:
            Словарь со статистикой
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Общая статистика сообщений
                cursor = conn.execute("SELECT COUNT(*) FROM conversation_messages")
                total_messages = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM conversation_chunks")
                total_chunks = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(DISTINCT customer_id) FROM conversation_messages")
                unique_customers = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(DISTINCT deal_id) FROM conversation_messages WHERE deal_id IS NOT NULL")
                unique_deals = cursor.fetchone()[0]
                
                # Статистика по типам отправителей
                cursor = conn.execute("""
                    SELECT sender_type, COUNT(*) 
                    FROM conversation_messages 
                    GROUP BY sender_type
                """)
                sender_stats = dict(cursor.fetchall())
                
                # Статистика за последние 24 часа
                cursor = conn.execute("""
                    SELECT COUNT(*) 
                    FROM conversation_messages 
                    WHERE timestamp >= datetime('now', '-1 day')
                """)
                messages_last_24h = cursor.fetchone()[0]
                
                return {
                    'total_messages': total_messages,
                    'total_chunks': total_chunks,
                    'unique_customers': unique_customers,
                    'unique_deals': unique_deals,
                    'sender_stats': sender_stats,
                    'messages_last_24h': messages_last_24h,
                    'db_path': self.db_path
                }
                
        except Exception as e:
            app_logger.error(f"Ошибка получения статистики RAG: {e}")
            return {}
    
    def cleanup_old_messages(self, days_to_keep: int = 90) -> int:
        """
        Очищает старые сообщения для экономии места
        
        Args:
            days_to_keep: Количество дней для хранения
            
        Returns:
            Количество удаленных сообщений
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with sqlite3.connect(self.db_path) as conn:
                # Удаляем чанки старых сообщений
                cursor = conn.execute("""
                    DELETE FROM conversation_chunks 
                    WHERE message_id IN (
                        SELECT message_id FROM conversation_messages 
                        WHERE timestamp < ?
                    )
                """, (cutoff_date,))
                chunks_deleted = cursor.rowcount
                
                # Удаляем старые сообщения
                cursor = conn.execute("""
                    DELETE FROM conversation_messages 
                    WHERE timestamp < ?
                """, (cutoff_date,))
                messages_deleted = cursor.rowcount
                
                app_logger.info(f"Удалено {messages_deleted} старых сообщений и {chunks_deleted} чанков")
                return messages_deleted
                
        except Exception as e:
            app_logger.error(f"Ошибка очистки старых сообщений: {e}")
            return 0