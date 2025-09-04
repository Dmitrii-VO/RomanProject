"""
Основной менеджер RAG системы для переписок
"""
import os
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from utils.logger import app_logger
from .conversation_store import ConversationStore
from .conversation_indexer import ConversationIndexer
from .conversation_retriever import ConversationRetriever


class ConversationRAGManager:
    """
    Основной менеджер RAG системы для переписок
    Объединяет все компоненты: хранилище, индексацию, извлечение
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Инициализация RAG менеджера
        
        Args:
            config: Конфигурация системы (опционально)
        """
        # Конфигурация по умолчанию
        self.config = {
            'db_path': "data/conversations_rag.db",
            'similarity_threshold': float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.6")),
            'max_context_length': int(os.getenv("RAG_MAX_CONTEXT_LENGTH", "2000")),
            'chunk_size': int(os.getenv("RAG_CHUNK_SIZE", "500")),
            'chunk_overlap': int(os.getenv("RAG_CHUNK_OVERLAP", "50")),
            'cleanup_days': int(os.getenv("RAG_CLEANUP_DAYS", "90")),
            'auto_cleanup_enabled': os.getenv("RAG_AUTO_CLEANUP", "true").lower() == "true",
            'batch_reindex_hour': int(os.getenv("RAG_BATCH_REINDEX_HOUR", "2")),  # 2:00 AM
        }
        
        # Обновляем конфигурацию если передана
        if config:
            self.config.update(config)
        
        # Инициализируем компоненты
        self.store = ConversationStore(self.config['db_path'])
        self.indexer = ConversationIndexer(self.store)
        self.retriever = ConversationRetriever(self.store)
        
        # Планировщик задач
        self.scheduler_task = None
        self.is_scheduler_running = False
        
        # Метрики
        self.metrics = {
            'messages_indexed_today': 0,
            'searches_performed_today': 0,
            'last_cleanup': None,
            'last_batch_reindex': None,
            'errors_today': 0
        }
        
        app_logger.info("ConversationRAGManager инициализирован")
    
    async def start_scheduler(self):
        """Запускает планировщик фоновых задач"""
        if self.is_scheduler_running:
            app_logger.warning("Планировщик RAG уже запущен")
            return
        
        self.is_scheduler_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        app_logger.info("Планировщик RAG запущен")
    
    async def stop_scheduler(self):
        """Останавливает планировщик фоновых задач"""
        if not self.is_scheduler_running:
            return
        
        self.is_scheduler_running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        app_logger.info("Планировщик RAG остановлен")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        try:
            while self.is_scheduler_running:
                current_hour = datetime.now().hour
                
                # Ежедневная очистка в 1:00
                if current_hour == 1 and self.config['auto_cleanup_enabled']:
                    if not self.metrics.get('last_cleanup') or \
                       datetime.now().date() > datetime.fromisoformat(self.metrics['last_cleanup']).date():
                        await self._daily_cleanup()
                        self.metrics['last_cleanup'] = datetime.now().isoformat()
                
                # Ежедневная переиндексация в заданный час
                if current_hour == self.config['batch_reindex_hour']:
                    if not self.metrics.get('last_batch_reindex') or \
                       datetime.now().date() > datetime.fromisoformat(self.metrics['last_batch_reindex']).date():
                        await self._daily_reindex()
                        self.metrics['last_batch_reindex'] = datetime.now().isoformat()
                
                # Сброс метрик в полночь
                if current_hour == 0:
                    self._reset_daily_metrics()
                
                # Ждем час до следующей проверки
                await asyncio.sleep(3600)
                
        except asyncio.CancelledError:
            app_logger.info("Планировщик RAG отменен")
        except Exception as e:
            app_logger.error(f"Ошибка в планировщике RAG: {e}")
    
    async def _daily_cleanup(self):
        """Ежедневная очистка старых данных"""
        try:
            app_logger.info("Начинаем ежедневную очистку RAG")
            deleted = self.store.cleanup_old_messages(self.config['cleanup_days'])
            app_logger.info(f"Очистка RAG завершена: удалено {deleted} сообщений")
        except Exception as e:
            app_logger.error(f"Ошибка ежедневной очистки RAG: {e}")
            self.metrics['errors_today'] += 1
    
    async def _daily_reindex(self):
        """Ежедневная переиндексация"""
        try:
            app_logger.info("Начинаем ежедневную переиндексацию RAG")
            stats = await self.indexer.batch_reindex(days_back=1)
            app_logger.info(f"Переиндексация RAG завершена: {stats}")
        except Exception as e:
            app_logger.error(f"Ошибка ежедневной переиндексации RAG: {e}")
            self.metrics['errors_today'] += 1
    
    def _reset_daily_metrics(self):
        """Сбрасывает ежедневные метрики"""
        self.metrics.update({
            'messages_indexed_today': 0,
            'searches_performed_today': 0,
            'errors_today': 0
        })
        app_logger.info("Ежедневные метрики RAG сброшены")
    
    # Публичные методы для работы с RAG
    
    async def index_message(self,
                          customer_id: str,
                          sender_type: str,
                          content: str,
                          deal_id: Optional[str] = None,
                          message_id: Optional[str] = None,
                          sync: bool = False) -> str:
        """
        Индексирует сообщение в RAG системе
        
        Args:
            customer_id: ID клиента
            sender_type: Тип отправителя ('customer', 'bot', 'manager')
            content: Содержимое сообщения
            deal_id: ID сделки (опционально)
            message_id: ID сообщения (генерируется если не указан)
            sync: Синхронная индексация (по умолчанию асинхронная)
            
        Returns:
            ID сообщения
        """
        try:
            if sync:
                message_id = await self.indexer.index_message_sync(
                    customer_id=customer_id,
                    sender_type=sender_type,
                    content=content,
                    deal_id=deal_id,
                    message_id=message_id
                )
            else:
                message_id = await self.indexer.index_message_async(
                    customer_id=customer_id,
                    sender_type=sender_type,
                    content=content,
                    deal_id=deal_id,
                    message_id=message_id
                )
            
            self.metrics['messages_indexed_today'] += 1
            return message_id
            
        except Exception as e:
            app_logger.error(f"Ошибка индексации сообщения: {e}")
            self.metrics['errors_today'] += 1
            return message_id or "error"
    
    async def get_relevant_context(self,
                                 query: str,
                                 customer_id: str,
                                 deal_id: Optional[str] = None,
                                 context_type: str = "general") -> Dict[str, Any]:
        """
        Получает релевантный контекст для ответа на запрос
        
        Args:
            query: Запрос пользователя
            customer_id: ID клиента
            deal_id: ID сделки (опционально)
            context_type: Тип контекста
            
        Returns:
            Контекст с метаданными
        """
        try:
            context = await self.retriever.get_relevant_context(
                query=query,
                customer_id=customer_id,
                deal_id=deal_id,
                context_type=context_type
            )
            
            self.metrics['searches_performed_today'] += 1
            return context
            
        except Exception as e:
            app_logger.error(f"Ошибка получения контекста: {e}")
            self.metrics['errors_today'] += 1
            return {
                'context_summary': "",
                'raw_fragments': [],
                'metadata': {'error': str(e)},
                'total_relevant_fragments': 0
            }
    
    async def get_customer_summary(self, customer_id: str, days_back: int = 7) -> Dict[str, Any]:
        """
        Получает сводку по клиенту
        
        Args:
            customer_id: ID клиента
            days_back: Количество дней для анализа
            
        Returns:
            Сводка по клиенту
        """
        try:
            return await self.retriever.get_customer_conversation_summary(customer_id, days_back)
        except Exception as e:
            app_logger.error(f"Ошибка получения сводки по клиенту: {e}")
            self.metrics['errors_today'] += 1
            return {
                'summary': "Ошибка анализа истории клиента",
                'total_messages': 0,
                'intents': [],
                'categories': []
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Получает статус всей RAG системы
        
        Returns:
            Полный статус системы
        """
        try:
            store_stats = self.store.get_stats()
            queue_status = self.indexer.get_queue_status()
            
            return {
                'scheduler_running': self.is_scheduler_running,
                'config': self.config,
                'metrics': self.metrics,
                'store_stats': store_stats,
                'indexer_queue': {
                    'size': queue_status['queue_size'],
                    'processing': queue_status['is_processing']
                },
                'system_health': self._calculate_health_score()
            }
        except Exception as e:
            app_logger.error(f"Ошибка получения статуса RAG системы: {e}")
            return {'error': str(e)}
    
    def _calculate_health_score(self) -> float:
        """
        Вычисляет оценку здоровья системы (0.0 - 1.0)
        
        Returns:
            Оценка здоровья
        """
        try:
            score = 1.0
            
            # Снижаем оценку за ошибки
            if self.metrics['errors_today'] > 0:
                score -= min(0.3, self.metrics['errors_today'] * 0.1)
            
            # Снижаем оценку если планировщик не работает
            if not self.is_scheduler_running:
                score -= 0.2
            
            # Снижаем оценку за большую очередь индексации
            queue_size = self.indexer.indexing_queue.qsize()
            if queue_size > 100:
                score -= min(0.2, queue_size * 0.001)
            
            return max(0.0, score)
            
        except Exception:
            return 0.5  # средняя оценка при ошибке расчета
    
    # Административные методы
    
    async def force_reindex_customer(self, customer_id: str, days_back: int = 30) -> int:
        """
        Принудительная переиндексация клиента
        
        Args:
            customer_id: ID клиента
            days_back: Количество дней для переиндексации
            
        Returns:
            Количество переиндексированных сообщений
        """
        try:
            return await self.indexer.reindex_customer_history(customer_id, days_back)
        except Exception as e:
            app_logger.error(f"Ошибка принудительной переиндексации клиента: {e}")
            return 0
    
    async def manual_cleanup(self, days_to_keep: int = None) -> int:
        """
        Ручная очистка старых данных
        
        Args:
            days_to_keep: Количество дней для сохранения (или используется конфиг)
            
        Returns:
            Количество удаленных сообщений
        """
        try:
            days = days_to_keep or self.config['cleanup_days']
            return self.store.cleanup_old_messages(days)
        except Exception as e:
            app_logger.error(f"Ошибка ручной очистки: {e}")
            return 0
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        Обновляет конфигурацию системы
        
        Args:
            new_config: Новые параметры конфигурации
        """
        try:
            self.config.update(new_config)
            
            # Обновляем параметры в компонентах
            if 'similarity_threshold' in new_config:
                self.retriever.default_similarity_threshold = new_config['similarity_threshold']
            
            app_logger.info(f"Конфигурация RAG обновлена: {new_config}")
            
        except Exception as e:
            app_logger.error(f"Ошибка обновления конфигурации RAG: {e}")