"""
Тесты для RAG системы переписок
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, patch

from src.rag.conversation_store import ConversationStore
from src.rag.conversation_indexer import ConversationIndexer
from src.rag.conversation_retriever import ConversationRetriever
from src.rag.conversation_rag_manager import ConversationRAGManager


@pytest.fixture
def temp_db():
    """Создает временную базу данных для тестов"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
        yield tmp_file.name
    os.unlink(tmp_file.name)


@pytest.fixture
def conversation_store(temp_db):
    """Создает ConversationStore с временной БД"""
    return ConversationStore(temp_db)


@pytest.fixture
def conversation_indexer(conversation_store):
    """Создает ConversationIndexer"""
    return ConversationIndexer(conversation_store)


@pytest.fixture
def conversation_retriever(conversation_store):
    """Создает ConversationRetriever"""
    return ConversationRetriever(conversation_store)


@pytest.fixture
def rag_manager(temp_db):
    """Создает ConversationRAGManager"""
    config = {'db_path': temp_db}
    return ConversationRAGManager(config)


class TestConversationStore:
    """Тесты для ConversationStore"""
    
    def test_init_database(self, conversation_store):
        """Тест инициализации базы данных"""
        stats = conversation_store.get_stats()
        assert stats['total_messages'] == 0
        assert stats['total_chunks'] == 0
    
    def test_clean_content(self, conversation_store):
        """Тест очистки контента от PII"""
        content = "Меня зовут Иван, мой телефон +7 900 123 45 67, email test@example.com"
        cleaned = conversation_store._clean_content(content)
        
        assert "[NAME]" in cleaned
        assert "[PHONE]" in cleaned
        assert "[EMAIL]" in cleaned
        assert "Иван" not in cleaned
        assert "+7 900 123 45 67" not in cleaned
        assert "test@example.com" not in cleaned
    
    def test_split_into_chunks(self, conversation_store):
        """Тест разделения на чанки"""
        long_content = "Это длинное сообщение. " * 100
        chunks = conversation_store._split_into_chunks(long_content, max_chunk_size=200)
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 250 for chunk in chunks)  # с учетом overlap
    
    @pytest.mark.asyncio
    async def test_store_message(self, conversation_store):
        """Тест сохранения сообщения"""
        with patch.object(conversation_store, '_get_embedding', return_value=[0.1] * 1536):
            result = await conversation_store.store_message(
                message_id="test_001",
                customer_id="123",
                sender_type="customer",
                content="Хочу купить кольцо с янтарем"
            )
            
            assert result is True
            
            stats = conversation_store.get_stats()
            assert stats['total_messages'] == 1
            assert stats['total_chunks'] >= 1


class TestConversationIndexer:
    """Тесты для ConversationIndexer"""
    
    def test_detect_intent(self, conversation_indexer):
        """Тест определения интента"""
        # Тест intent для покупки
        purchase_intent = conversation_indexer._detect_intent("Хочу купить кольцо", "customer")
        assert purchase_intent == "purchase_intent"
        
        # Тест intent для цены
        price_intent = conversation_indexer._detect_intent("Сколько стоит браслет?", "customer")
        assert price_intent == "price_inquiry"
        
        # Тест intent для приветствия
        greeting_intent = conversation_indexer._detect_intent("Здравствуйте!", "customer")
        assert greeting_intent == "greeting"
    
    def test_detect_category(self, conversation_indexer):
        """Тест определения категории"""
        # Тест категории товара
        rings_category = conversation_indexer._detect_category("Показать кольца", "customer")
        assert rings_category == "rings"
        
        # Тест категории процесса
        delivery_category = conversation_indexer._detect_category("Как доставка работает?", "customer")
        assert delivery_category == "delivery"
    
    @pytest.mark.asyncio
    async def test_index_message_async(self, conversation_indexer):
        """Тест асинхронной индексации"""
        with patch.object(conversation_indexer.store, 'store_message', return_value=True):
            message_id = await conversation_indexer.index_message_async(
                customer_id="123",
                sender_type="customer",
                content="Тестовое сообщение"
            )
            
            assert message_id.startswith("123_")
            assert conversation_indexer.indexing_queue.qsize() == 1


class TestConversationRetriever:
    """Тесты для ConversationRetriever"""
    
    def test_extract_intent(self, conversation_retriever):
        """Тест извлечения интента"""
        intent = conversation_retriever._extract_intent("Хочу купить серьги")
        assert intent == "purchase_intent"
    
    def test_extract_category(self, conversation_retriever):
        """Тест извлечения категории"""
        category = conversation_retriever._extract_category("Серьги с янтарем", "product_search")
        assert category == "earrings"
    
    def test_deduplicate_fragments(self, conversation_retriever):
        """Тест удаления дубликатов"""
        fragments = [
            {"message_id": "1", "chunk_index": 0, "content": "test1"},
            {"message_id": "1", "chunk_index": 0, "content": "test1"},  # дубликат
            {"message_id": "2", "chunk_index": 0, "content": "test2"},
        ]
        
        unique = conversation_retriever._deduplicate_fragments(fragments)
        assert len(unique) == 2
    
    @pytest.mark.asyncio
    async def test_get_relevant_context(self, conversation_retriever):
        """Тест получения релевантного контекста"""
        with patch.object(conversation_retriever.store, 'search_similar_messages', return_value=[]):
            context = await conversation_retriever.get_relevant_context(
                query="Какие кольца у вас есть?",
                customer_id="123"
            )
            
            assert "context_summary" in context
            assert "raw_fragments" in context
            assert "metadata" in context


class TestConversationRAGManager:
    """Тесты для ConversationRAGManager"""
    
    def test_init(self, rag_manager):
        """Тест инициализации RAG менеджера"""
        assert rag_manager.store is not None
        assert rag_manager.indexer is not None
        assert rag_manager.retriever is not None
        assert rag_manager.config is not None
    
    @pytest.mark.asyncio
    async def test_index_message(self, rag_manager):
        """Тест индексации сообщения через менеджер"""
        with patch.object(rag_manager.indexer, 'index_message_async', return_value="test_id"):
            message_id = await rag_manager.index_message(
                customer_id="123",
                sender_type="customer",
                content="Тестовое сообщение"
            )
            
            assert message_id == "test_id"
            assert rag_manager.metrics['messages_indexed_today'] == 1
    
    @pytest.mark.asyncio
    async def test_get_relevant_context(self, rag_manager):
        """Тест получения контекста через менеджер"""
        mock_context = {
            "context_summary": "Тестовый контекст",
            "raw_fragments": [],
            "metadata": {},
            "total_relevant_fragments": 0
        }
        
        with patch.object(rag_manager.retriever, 'get_relevant_context', return_value=mock_context):
            context = await rag_manager.get_relevant_context(
                query="Тестовый запрос",
                customer_id="123"
            )
            
            assert context['context_summary'] == "Тестовый контекст"
            assert rag_manager.metrics['searches_performed_today'] == 1
    
    def test_get_system_status(self, rag_manager):
        """Тест получения статуса системы"""
        with patch.object(rag_manager.store, 'get_stats', return_value={}):
            status = rag_manager.get_system_status()
            
            assert 'scheduler_running' in status
            assert 'config' in status
            assert 'metrics' in status
            assert 'store_stats' in status
            assert 'system_health' in status
    
    def test_calculate_health_score(self, rag_manager):
        """Тест расчета оценки здоровья системы"""
        # Здоровая система
        rag_manager.metrics['errors_today'] = 0
        rag_manager.is_scheduler_running = True
        health = rag_manager._calculate_health_score()
        assert health == 1.0
        
        # Система с ошибками
        rag_manager.metrics['errors_today'] = 5
        health = rag_manager._calculate_health_score()
        assert health < 1.0
    
    @pytest.mark.asyncio
    async def test_scheduler_lifecycle(self, rag_manager):
        """Тест жизненного цикла планировщика"""
        assert not rag_manager.is_scheduler_running
        
        await rag_manager.start_scheduler()
        assert rag_manager.is_scheduler_running
        
        await rag_manager.stop_scheduler()
        assert not rag_manager.is_scheduler_running


class TestPIISecurity:
    """Тесты для безопасности и маскирования PII"""
    
    def test_phone_masking(self, conversation_store):
        """Тест маскирования телефонов"""
        test_cases = [
            "+7 900 123 45 67",
            "8-900-123-45-67", 
            "7 (900) 123-45-67",
            "89001234567"
        ]
        
        for phone in test_cases:
            content = f"Мой телефон {phone}"
            cleaned = conversation_store._clean_content(content)
            assert "[PHONE]" in cleaned
            assert phone not in cleaned
    
    def test_email_masking(self, conversation_store):
        """Тест маскирования email"""
        test_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "contact@янтарь.рф"
        ]
        
        for email in test_emails:
            content = f"Пишите мне на {email}"
            cleaned = conversation_store._clean_content(content)
            assert "[EMAIL]" in cleaned
            assert email not in cleaned
    
    def test_name_masking(self, conversation_store):
        """Тест маскирования имен"""
        content = "Меня зовут Анна, я хочу кольцо"
        cleaned = conversation_store._clean_content(content)
        
        # Имя должно быть замаскировано только если есть явные указатели
        if "меня зовут" in content.lower():
            assert "[NAME]" in cleaned


if __name__ == "__main__":
    pytest.main([__file__, "-v"])