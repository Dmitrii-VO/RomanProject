"""
Компонент индексации сообщений для RAG (write-path)
"""
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
from utils.logger import app_logger
from .conversation_store import ConversationStore


class ConversationIndexer:
    """
    Асинхронная индексация сообщений в векторное хранилище
    """
    
    def __init__(self, store: ConversationStore):
        """
        Инициализация компонента индексации
        
        Args:
            store: Хранилище переписок
        """
        self.store = store
        self.indexing_queue = asyncio.Queue()
        self.is_processing = False
        
        app_logger.info("ConversationIndexer инициализирован")
    
    async def index_message_async(self,
                                customer_id: str,
                                sender_type: str,
                                content: str,
                                deal_id: Optional[str] = None,
                                message_id: Optional[str] = None) -> str:
        """
        Асинхронно добавляет сообщение в очередь индексации
        
        Args:
            customer_id: ID клиента
            sender_type: Тип отправителя ('customer', 'bot', 'manager')
            content: Содержимое сообщения
            deal_id: ID сделки (опционально)
            message_id: ID сообщения (генерируется если не указан)
            
        Returns:
            ID сообщения
        """
        if not message_id:
            message_id = f"{customer_id}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Определяем интент и категорию
        intent = self._detect_intent(content, sender_type)
        category = self._detect_category(content, sender_type)
        
        # Добавляем в очередь индексации
        await self.indexing_queue.put({
            'message_id': message_id,
            'customer_id': customer_id,
            'sender_type': sender_type,
            'content': content,
            'deal_id': deal_id,
            'intent': intent,
            'category': category,
            'timestamp': datetime.now()
        })
        
        app_logger.info(f"Сообщение {message_id} добавлено в очередь индексации")
        
        # Запускаем обработку если не запущена
        if not self.is_processing:
            asyncio.create_task(self._process_indexing_queue())
        
        return message_id
    
    async def index_message_sync(self,
                               customer_id: str,
                               sender_type: str,
                               content: str,
                               deal_id: Optional[str] = None,
                               message_id: Optional[str] = None) -> str:
        """
        Синхронно индексирует сообщение (для критических случаев)
        
        Args:
            customer_id: ID клиента
            sender_type: Тип отправителя
            content: Содержимое сообщения
            deal_id: ID сделки (опционально)
            message_id: ID сообщения (генерируется если не указан)
            
        Returns:
            ID сообщения
        """
        if not message_id:
            message_id = f"{customer_id}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        intent = self._detect_intent(content, sender_type)
        category = self._detect_category(content, sender_type)
        
        success = await self.store.store_message(
            message_id=message_id,
            customer_id=customer_id,
            sender_type=sender_type,
            content=content,
            deal_id=deal_id,
            intent=intent,
            category=category
        )
        
        if success:
            app_logger.info(f"Сообщение {message_id} синхронно проиндексировано")
        else:
            app_logger.error(f"Ошибка синхронной индексации сообщения {message_id}")
        
        return message_id
    
    async def _process_indexing_queue(self):
        """Обрабатывает очередь индексации в фоновом режиме"""
        if self.is_processing:
            return
        
        self.is_processing = True
        
        try:
            while True:
                try:
                    # Ждем сообщение из очереди с таймаутом
                    message_data = await asyncio.wait_for(self.indexing_queue.get(), timeout=5.0)
                    
                    # Индексируем сообщение
                    success = await self.store.store_message(
                        message_id=message_data['message_id'],
                        customer_id=message_data['customer_id'],
                        sender_type=message_data['sender_type'],
                        content=message_data['content'],
                        deal_id=message_data['deal_id'],
                        intent=message_data['intent'],
                        category=message_data['category']
                    )
                    
                    if not success:
                        app_logger.warning(f"Не удалось проиндексировать сообщение {message_data['message_id']}")
                    
                    # Отмечаем задачу как выполненную
                    self.indexing_queue.task_done()
                    
                except asyncio.TimeoutError:
                    # Таймаут - очередь пуста, останавливаем обработку
                    break
                except Exception as e:
                    app_logger.error(f"Ошибка обработки очереди индексации: {e}")
                    break
                
        finally:
            self.is_processing = False
            app_logger.info("Обработка очереди индексации завершена")
    
    def _detect_intent(self, content: str, sender_type: str) -> Optional[str]:
        """
        Определяет интент сообщения на основе содержимого
        
        Args:
            content: Содержимое сообщения
            sender_type: Тип отправителя
            
        Returns:
            Интент или None
        """
        if not content:
            return None
        
        content_lower = content.lower()
        
        # Интенты для сообщений клиентов
        if sender_type == 'customer':
            if any(word in content_lower for word in ['купить', 'заказать', 'приобрести', 'оформить заказ']):
                return 'purchase_intent'
            elif any(word in content_lower for word in ['цена', 'стоимость', 'сколько стоит', 'стоит']):
                return 'price_inquiry'
            elif any(word in content_lower for word in ['доставка', 'доставить', 'получить', 'привезти']):
                return 'delivery_inquiry'
            elif any(word in content_lower for word in ['размер', 'размеры', 'какой размер', 'подойдет ли']):
                return 'size_inquiry'
            elif any(word in content_lower for word in ['наличие', 'есть ли', 'в наличии', 'имеется']):
                return 'availability_inquiry'
            elif any(word in content_lower for word in ['возврат', 'обмен', 'вернуть', 'поменять']):
                return 'return_inquiry'
            elif any(word in content_lower for word in ['рекомендуй', 'посоветуй', 'подбери', 'что лучше']):
                return 'recommendation_request'
            elif any(word in content_lower for word in ['спасибо', 'благодарю', 'отлично', 'хорошо']):
                return 'gratitude'
            elif any(word in content_lower for word in ['здравствуй', 'привет', 'добрый день', 'добро']):
                return 'greeting'
        
        # Интенты для ответов бота
        elif sender_type == 'bot':
            if any(word in content_lower for word in ['рекомендую', 'советую', 'подойдет', 'предлагаю']):
                return 'recommendation_given'
            elif any(word in content_lower for word in ['цена', 'стоимость', 'руб', '₽']):
                return 'price_provided'
            elif any(word in content_lower for word in ['доставка', 'доставим', 'получите']):
                return 'delivery_info'
            elif any(word in content_lower for word in ['в наличии', 'есть', 'доступен']):
                return 'availability_confirmed'
            elif any(word in content_lower for word in ['оформить', 'заказать', 'контакты']):
                return 'order_assistance'
        
        # Интенты для менеджера
        elif sender_type == 'manager':
            if any(word in content_lower for word in ['заказ оформлен', 'заказ принят', 'обработан']):
                return 'order_processed'
            elif any(word in content_lower for word in ['отправлен', 'доставлен', 'получен']):
                return 'delivery_update'
            elif any(word in content_lower for word in ['проблема', 'вопрос', 'уточнить']):
                return 'clarification_needed'
        
        return 'general_inquiry'
    
    def _detect_category(self, content: str, sender_type: str) -> Optional[str]:
        """
        Определяет категорию сообщения
        
        Args:
            content: Содержимое сообщения
            sender_type: Тип отправителя
            
        Returns:
            Категория или None
        """
        if not content:
            return None
        
        content_lower = content.lower()
        
        # Категории товаров
        if any(word in content_lower for word in ['кольцо', 'кольца']):
            return 'rings'
        elif any(word in content_lower for word in ['серьги', 'серёжки']):
            return 'earrings'
        elif any(word in content_lower for word in ['браслет', 'браслеты']):
            return 'bracelets'
        elif any(word in content_lower for word in ['кулон', 'кулоны', 'подвеска', 'подвески']):
            return 'pendants'
        elif any(word in content_lower for word in ['бусы', 'ожерелье', 'ожерелья']):
            return 'necklaces'
        elif any(word in content_lower for word in ['брошь', 'броши', 'брошка']):
            return 'brooches'
        elif any(word in content_lower for word in ['янтарь', 'янтарные', 'янтарный']):
            return 'amber_products'
        
        # Процессные категории
        elif any(word in content_lower for word in ['доставка', 'курьер', 'почта']):
            return 'delivery'
        elif any(word in content_lower for word in ['оплата', 'платеж', 'карта', 'наличные']):
            return 'payment'
        elif any(word in content_lower for word in ['размер', 'размеры', 'обхват']):
            return 'sizing'
        elif any(word in content_lower for word in ['возврат', 'обмен', 'гарантия']):
            return 'returns'
        
        # Типы взаимодействия
        elif sender_type == 'customer':
            return 'customer_inquiry'
        elif sender_type == 'bot':
            return 'bot_response'
        elif sender_type == 'manager':
            return 'manager_communication'
        
        return 'general'
    
    async def reindex_customer_history(self, customer_id: str, days_back: int = 30) -> int:
        """
        Переиндексирует всю историю сообщений клиента
        
        Args:
            customer_id: ID клиента
            days_back: Количество дней истории для переиндексации
            
        Returns:
            Количество переиндексированных сообщений
        """
        try:
            app_logger.info(f"Начинаем переиндексацию истории клиента {customer_id}")
            
            # Здесь должна быть логика получения истории сообщений из основного хранилища
            # (например, из AmoCRM или базы логов переписок)
            # Пока что возвращаем 0 как заглушку
            
            app_logger.info(f"Переиндексация истории клиента {customer_id} завершена")
            return 0
            
        except Exception as e:
            app_logger.error(f"Ошибка переиндексации истории клиента {customer_id}: {e}")
            return 0
    
    async def batch_reindex(self, days_back: int = 7) -> Dict[str, int]:
        """
        Массовая переиндексация всех сообщений за период
        
        Args:
            days_back: Количество дней для переиндексации
            
        Returns:
            Статистика переиндексации
        """
        try:
            app_logger.info(f"Начинаем массовую переиндексацию за последние {days_back} дней")
            
            # Здесь должна быть логика получения всех сообщений за период
            # и их переиндексация
            # Пока что возвращаем нулевую статистику
            
            stats = {
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'customers_affected': 0
            }
            
            app_logger.info(f"Массовая переиндексация завершена: {stats}")
            return stats
            
        except Exception as e:
            app_logger.error(f"Ошибка массовой переиндексации: {e}")
            return {'error': str(e)}
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Получает статус очереди индексации
        
        Returns:
            Статус очереди
        """
        return {
            'queue_size': self.indexing_queue.qsize(),
            'is_processing': self.is_processing,
            'store_stats': self.store.get_stats()
        }