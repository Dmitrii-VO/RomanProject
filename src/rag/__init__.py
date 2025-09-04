"""
RAG модуль для переписок - Retrieval-Augmented Generation

Компоненты:
- ConversationStore: Векторное хранилище переписок
- ConversationIndexer: Индексация сообщений (write-path) 
- ConversationRetriever: Извлечение релевантных фрагментов (read-path)
- ConversationRAGManager: Основной менеджер всей системы
"""

from .conversation_store import ConversationStore
from .conversation_indexer import ConversationIndexer  
from .conversation_retriever import ConversationRetriever
from .conversation_rag_manager import ConversationRAGManager

__all__ = [
    'ConversationStore',
    'ConversationIndexer',
    'ConversationRetriever', 
    'ConversationRAGManager'
]