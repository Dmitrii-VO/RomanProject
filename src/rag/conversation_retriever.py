"""
Компонент извлечения релевантных фрагментов переписок
"""
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from utils.logger import app_logger
from .conversation_store import ConversationStore


class ConversationRetriever:
    """
    Извлекает релевантные фрагменты переписок для RAG
    """
    
    def __init__(self, store: ConversationStore):
        """
        Инициализация компонента извлечения
        
        Args:
            store: Хранилище переписок
        """
        self.store = store
        
        # Конфигурация поиска
        self.default_similarity_threshold = 0.6
        self.high_similarity_threshold = 0.75
        self.low_similarity_threshold = 0.4
        self.max_context_length = 2000  # максимальная длина контекста в символах
        self.max_results_per_search = 15
        
        app_logger.info("ConversationRetriever инициализирован")
    
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
            context_type: Тип контекста ('general', 'product_search', 'order_process', 'support')
            
        Returns:
            Словарь с контекстом и метаданными
        """
        try:
            context_fragments = []
            search_metadata = {
                'searches_performed': 0,
                'total_fragments_found': 0,
                'similarity_thresholds_used': [],
                'search_strategy': context_type
            }
            
            # 1. Поиск по конкретному клиенту и сделке (высокий приоритет)
            if deal_id:
                deal_context = await self._search_by_deal(query, customer_id, deal_id)
                if deal_context:
                    context_fragments.extend(deal_context)
                    search_metadata['searches_performed'] += 1
                    search_metadata['total_fragments_found'] += len(deal_context)
                    search_metadata['similarity_thresholds_used'].append(self.high_similarity_threshold)
            
            # 2. Поиск по клиенту (средний приоритет)
            customer_context = await self._search_by_customer(query, customer_id, exclude_deal_id=deal_id)
            if customer_context:
                context_fragments.extend(customer_context)
                search_metadata['searches_performed'] += 1
                search_metadata['total_fragments_found'] += len(customer_context)
                search_metadata['similarity_thresholds_used'].append(self.default_similarity_threshold)
            
            # 3. Fallback поиск по интенту/категории (низкий приоритет)
            if len(context_fragments) < 5:  # если мало контекста
                intent = self._extract_intent(query)
                category = self._extract_category(query, context_type)
                
                fallback_context = await self._search_by_intent_category(query, intent, category)
                if fallback_context:
                    context_fragments.extend(fallback_context)
                    search_metadata['searches_performed'] += 1
                    search_metadata['total_fragments_found'] += len(fallback_context)
                    search_metadata['similarity_thresholds_used'].append(self.low_similarity_threshold)
            
            # Убираем дубликаты и сортируем по релевантности
            unique_fragments = self._deduplicate_fragments(context_fragments)
            sorted_fragments = sorted(unique_fragments, key=lambda x: x['similarity'], reverse=True)
            
            # Формируем компактный контекст
            summary = self._build_context_summary(sorted_fragments, query, context_type)
            
            return {
                'context_summary': summary,
                'raw_fragments': sorted_fragments[:10],  # ограничиваем для экономии токенов
                'metadata': search_metadata,
                'total_relevant_fragments': len(sorted_fragments)
            }
            
        except Exception as e:
            app_logger.error(f"Ошибка получения релевантного контекста: {e}")
            return {
                'context_summary': "",
                'raw_fragments': [],
                'metadata': {'error': str(e)},
                'total_relevant_fragments': 0
            }
    
    async def _search_by_deal(self, query: str, customer_id: str, deal_id: str) -> List[Dict]:
        """Поиск по конкретной сделке"""
        try:
            results = await self.store.search_similar_messages(
                query=query,
                customer_id=customer_id,
                deal_id=deal_id,
                similarity_threshold=self.high_similarity_threshold,
                max_results=self.max_results_per_search,
                days_back=30  # только за последний месяц для сделки
            )
            
            app_logger.info(f"Найдено {len(results)} фрагментов по сделке {deal_id}")
            return results
            
        except Exception as e:
            app_logger.error(f"Ошибка поиска по сделке: {e}")
            return []
    
    async def _search_by_customer(self, query: str, customer_id: str, exclude_deal_id: Optional[str] = None) -> List[Dict]:
        """Поиск по всем сообщениям клиента"""
        try:
            results = await self.store.search_similar_messages(
                query=query,
                customer_id=customer_id,
                similarity_threshold=self.default_similarity_threshold,
                max_results=self.max_results_per_search,
                days_back=60  # последние 2 месяца для клиента
            )
            
            # Исключаем сообщения из конкретной сделки если нужно
            if exclude_deal_id:
                results = [r for r in results if r.get('deal_id') != exclude_deal_id]
            
            app_logger.info(f"Найдено {len(results)} фрагментов по клиенту {customer_id}")
            return results
            
        except Exception as e:
            app_logger.error(f"Ошибка поиска по клиенту: {e}")
            return []
    
    async def _search_by_intent_category(self, query: str, intent: Optional[str], category: Optional[str]) -> List[Dict]:
        """Fallback поиск по интенту и категории"""
        try:
            results = []
            
            # Поиск по интенту
            if intent:
                intent_results = await self.store.search_similar_messages(
                    query=query,
                    intent=intent,
                    similarity_threshold=self.low_similarity_threshold,
                    max_results=self.max_results_per_search // 2,
                    days_back=90  # последние 3 месяца для общего поиска
                )
                results.extend(intent_results)
            
            # Поиск по категории
            if category and category != intent:
                category_results = await self.store.search_similar_messages(
                    query=query,
                    category=category,
                    similarity_threshold=self.low_similarity_threshold,
                    max_results=self.max_results_per_search // 2,
                    days_back=90
                )
                results.extend(category_results)
            
            # Общий поиск если ничего не нашли
            if not results:
                results = await self.store.search_similar_messages(
                    query=query,
                    similarity_threshold=self.low_similarity_threshold,
                    max_results=5,  # минимальный fallback
                    days_back=30
                )
            
            app_logger.info(f"Найдено {len(results)} фрагментов по интенту/категории")
            return results
            
        except Exception as e:
            app_logger.error(f"Ошибка fallback поиска: {e}")
            return []
    
    def _extract_intent(self, query: str) -> Optional[str]:
        """Извлекает интент из запроса"""
        query_lower = query.lower()
        
        # Определяем основные интенты
        if any(word in query_lower for word in ['купить', 'заказать', 'приобрести', 'оформить']):
            return 'purchase_intent'
        elif any(word in query_lower for word in ['цена', 'стоимость', 'сколько', 'стоит']):
            return 'price_inquiry'
        elif any(word in query_lower for word in ['доставка', 'доставить', 'получить']):
            return 'delivery_inquiry'
        elif any(word in query_lower for word in ['размер', 'размеры', 'какой размер']):
            return 'size_inquiry'
        elif any(word in query_lower for word in ['наличие', 'есть ли', 'в наличии']):
            return 'availability_inquiry'
        elif any(word in query_lower for word in ['возврат', 'обмен', 'вернуть']):
            return 'return_inquiry'
        elif any(word in query_lower for word in ['рекомендуй', 'посоветуй', 'подбери']):
            return 'recommendation_request'
        else:
            return 'general_inquiry'
    
    def _extract_category(self, query: str, context_type: str) -> Optional[str]:
        """Извлекает категорию из запроса"""
        query_lower = query.lower()
        
        # Категории товаров
        if any(word in query_lower for word in ['кольцо', 'кольца']):
            return 'rings'
        elif any(word in query_lower for word in ['серьги', 'серёжки']):
            return 'earrings'
        elif any(word in query_lower for word in ['браслет', 'браслеты']):
            return 'bracelets'
        elif any(word in query_lower for word in ['кулон', 'кулоны', 'подвеска']):
            return 'pendants'
        elif any(word in query_lower for word in ['бусы', 'ожерелье']):
            return 'necklaces'
        elif any(word in query_lower for word in ['брошь', 'броши']):
            return 'brooches'
        
        # Категории по контексту
        return {
            'product_search': 'product_inquiry',
            'order_process': 'order_management', 
            'support': 'customer_support',
            'general': 'general_conversation'
        }.get(context_type, 'general_conversation')
    
    def _deduplicate_fragments(self, fragments: List[Dict]) -> List[Dict]:
        """Удаляет дубликаты фрагментов"""
        seen = set()
        unique = []
        
        for fragment in fragments:
            # Используем комбинацию message_id и chunk_index как ключ уникальности
            key = (fragment['message_id'], fragment['chunk_index'])
            if key not in seen:
                seen.add(key)
                unique.append(fragment)
        
        return unique
    
    def _build_context_summary(self, fragments: List[Dict], query: str, context_type: str) -> str:
        """Строит компактную сводку контекста"""
        if not fragments:
            return ""
        
        try:
            # Группируем по типу отправителя и времени
            customer_messages = []
            bot_messages = []
            manager_messages = []
            
            for fragment in fragments:
                content = fragment['content'][:200] + "..." if len(fragment['content']) > 200 else fragment['content']
                
                if fragment['sender_type'] == 'customer':
                    customer_messages.append(content)
                elif fragment['sender_type'] == 'bot':
                    bot_messages.append(content)
                elif fragment['sender_type'] == 'manager':
                    manager_messages.append(content)
            
            summary_parts = []
            
            # Ограничиваем количество фрагментов для экономии токенов
            max_per_type = 3
            
            if customer_messages:
                summary_parts.append(f"Предыдущие вопросы клиента: {'; '.join(customer_messages[:max_per_type])}")
            
            if bot_messages:
                summary_parts.append(f"Предыдущие ответы консультанта: {'; '.join(bot_messages[:max_per_type])}")
            
            if manager_messages:
                summary_parts.append(f"Комментарии менеджера: {'; '.join(manager_messages[:max_per_type])}")
            
            full_summary = "\n".join(summary_parts)
            
            # Обрезаем если слишком длинно
            if len(full_summary) > self.max_context_length:
                full_summary = full_summary[:self.max_context_length] + "..."
            
            return full_summary
            
        except Exception as e:
            app_logger.error(f"Ошибка построения сводки контекста: {e}")
            return ""
    
    async def get_customer_conversation_summary(self, customer_id: str, days_back: int = 7) -> Dict[str, Any]:
        """
        Получает сводку по всем разговорам с клиентом за период
        
        Args:
            customer_id: ID клиента
            days_back: Количество дней назад
            
        Returns:
            Сводка разговоров с клиентом
        """
        try:
            # Получаем все сообщения клиента за период
            results = await self.store.search_similar_messages(
                query="",  # пустой запрос для получения всех
                customer_id=customer_id,
                similarity_threshold=0.0,  # минимальный порог
                max_results=100,
                days_back=days_back
            )
            
            if not results:
                return {
                    'summary': "Нет предыдущих разговоров с клиентом",
                    'total_messages': 0,
                    'intents': [],
                    'categories': []
                }
            
            # Анализируем интенты и категории
            intents = [r.get('intent') for r in results if r.get('intent')]
            categories = [r.get('category') for r in results if r.get('category')]
            
            # Считаем частотность
            intent_counts = {}
            category_counts = {}
            
            for intent in intents:
                intent_counts[intent] = intent_counts.get(intent, 0) + 1
            
            for category in categories:
                category_counts[category] = category_counts.get(category, 0) + 1
            
            # Строим краткую сводку
            summary = f"За последние {days_back} дней с клиентом было {len(results)} сообщений."
            if intent_counts:
                top_intent = max(intent_counts.items(), key=lambda x: x[1])
                summary += f" Основной интерес: {top_intent[0]}."
            if category_counts:
                top_category = max(category_counts.items(), key=lambda x: x[1])
                summary += f" Чаще всего интересовался: {top_category[0]}."
            
            return {
                'summary': summary,
                'total_messages': len(results),
                'intents': list(intent_counts.keys()),
                'categories': list(category_counts.keys()),
                'intent_distribution': intent_counts,
                'category_distribution': category_counts
            }
            
        except Exception as e:
            app_logger.error(f"Ошибка получения сводки по клиенту: {e}")
            return {
                'summary': "Ошибка анализа истории клиента",
                'total_messages': 0,
                'intents': [],
                'categories': []
            }