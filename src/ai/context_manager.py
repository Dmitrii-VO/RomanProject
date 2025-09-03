"""
Менеджер контекста диалогов для ИИ консультанта
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class Message:
    """Структура сообщения в диалоге"""
    user_id: int
    content: str
    timestamp: datetime
    is_bot: bool = False


class DialogueContextManager:
    """
    Управляет контекстом диалогов пользователей
    """
    
    def __init__(self, max_tokens_per_context: int = 100000, session_timeout_minutes: int = 60):
        """
        Инициализация менеджера контекста
        
        Args:
            max_tokens_per_context: Максимальное количество токенов в контексте (примерно 4 символа = 1 токен)
            session_timeout_minutes: Таймаут сессии в минутах
        """
        self.conversations: Dict[int, List[Message]] = {}
        self.max_context_tokens = max_tokens_per_context
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        
    def add_message(self, user_id: int, content: str, is_bot: bool = False):
        """
        Добавляет сообщение в контекст диалога
        
        Args:
            user_id: ID пользователя
            content: Текст сообщения
            is_bot: True если это сообщение от бота
        """
        message = Message(
            user_id=user_id,
            content=content,
            timestamp=datetime.now(),
            is_bot=is_bot
        )
        
        if user_id not in self.conversations:
            self.conversations[user_id] = []
            
        self.conversations[user_id].append(message)
        
        # Ограничиваем контекст по количеству токенов
        self._trim_context_by_tokens(user_id)
    
    def get_context(self, user_id: int) -> str:
        """
        Получает контекст диалога для пользователя в виде строки
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Строка с историей диалога
        """
        if user_id not in self.conversations:
            return ""
            
        # Очищаем устаревшие сообщения
        self._cleanup_old_messages(user_id)
        
        messages = self.conversations[user_id]
        if not messages:
            return ""
        
        context_lines = []
        for msg in messages:
            role = "Консультант" if msg.is_bot else "Клиент"
            context_lines.append(f"{role}: {msg.content}")
            
        return "\n".join(context_lines)
    
    def is_first_interaction(self, user_id: int) -> bool:
        """
        Проверяет, первое ли это взаимодействие с пользователем
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если это первое сообщение от пользователя
        """
        if user_id not in self.conversations:
            return True
            
        # Очищаем устаревшие сообщения
        self._cleanup_old_messages(user_id)
        
        # Если после очистки сообщений не осталось, считаем что это первое взаимодействие
        return len(self.conversations[user_id]) == 0
    
    def get_last_user_message(self, user_id: int) -> Optional[str]:
        """
        Получает последнее сообщение пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Текст последнего сообщения пользователя или None
        """
        if user_id not in self.conversations:
            return None
            
        messages = self.conversations[user_id]
        user_messages = [msg for msg in messages if not msg.is_bot]
        
        return user_messages[-1].content if user_messages else None
    
    def _cleanup_old_messages(self, user_id: int):
        """
        Удаляет устаревшие сообщения из контекста
        
        Args:
            user_id: ID пользователя
        """
        if user_id not in self.conversations:
            return
            
        current_time = datetime.now()
        valid_messages = []
        
        for msg in self.conversations[user_id]:
            if current_time - msg.timestamp <= self.session_timeout:
                valid_messages.append(msg)
                
        self.conversations[user_id] = valid_messages
    
    def clear_user_context(self, user_id: int):
        """
        Очищает контекст диалога для пользователя
        
        Args:
            user_id: ID пользователя
        """
        if user_id in self.conversations:
            del self.conversations[user_id]
    
    def get_session_stats(self, user_id: int) -> Dict:
        """
        Получает статистику сессии пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь со статистикой сессии
        """
        if user_id not in self.conversations:
            return {"message_count": 0, "session_duration": 0, "is_active": False}
            
        messages = self.conversations[user_id]
        if not messages:
            return {"message_count": 0, "session_duration": 0, "is_active": False}
            
        first_message = messages[0]
        last_message = messages[-1]
        duration = (last_message.timestamp - first_message.timestamp).total_seconds()
        
        return {
            "message_count": len(messages),
            "session_duration": duration,
            "is_active": datetime.now() - last_message.timestamp <= self.session_timeout,
            "first_interaction": first_message.timestamp.isoformat(),
            "last_interaction": last_message.timestamp.isoformat()
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Приблизительная оценка количества токенов в тексте
        Для русского языка: ~4 символа = 1 токен
        
        Args:
            text: Текст для анализа
            
        Returns:
            Приблизительное количество токенов
        """
        return len(text) // 4 + 1
    
    def _trim_context_by_tokens(self, user_id: int):
        """
        Обрезает контекст диалога по лимиту токенов, оставляя наиболее важные части
        
        Args:
            user_id: ID пользователя
        """
        if user_id not in self.conversations:
            return
            
        messages = self.conversations[user_id]
        if not messages:
            return
            
        # Подсчитываем общее количество токенов
        total_tokens = 0
        for msg in messages:
            role = "Консультант" if msg.is_bot else "Клиент"
            text = f"{role}: {msg.content}"
            total_tokens += self._estimate_tokens(text)
        
        # Если не превышаем лимит, оставляем все
        if total_tokens <= self.max_context_tokens:
            return
            
        # Стратегия обрезки: сохраняем последние сообщения + логически важные
        trimmed_messages = []
        current_tokens = 0
        
        # Начинаем с конца (последние сообщения важнее)
        for msg in reversed(messages):
            role = "Консультант" if msg.is_bot else "Клиент" 
            text = f"{role}: {msg.content}"
            msg_tokens = self._estimate_tokens(text)
            
            # Проверяем, поместится ли сообщение
            if current_tokens + msg_tokens <= self.max_context_tokens:
                trimmed_messages.insert(0, msg)  # Вставляем в начало для сохранения порядка
                current_tokens += msg_tokens
            else:
                # Если сообщение критически важно (содержит ключевые слова), пытаемся его сохранить
                important_keywords = ["заказ", "покупка", "цена", "размер", "доставка", "оплата"]
                if any(keyword in msg.content.lower() for keyword in important_keywords):
                    # Удаляем более старые сообщения, чтобы поместить важное
                    while trimmed_messages and current_tokens + msg_tokens > self.max_context_tokens:
                        removed_msg = trimmed_messages.pop(0)
                        removed_role = "Консультант" if removed_msg.is_bot else "Клиент"
                        removed_text = f"{removed_role}: {removed_msg.content}"
                        current_tokens -= self._estimate_tokens(removed_text)
                    
                    if current_tokens + msg_tokens <= self.max_context_tokens:
                        trimmed_messages.insert(0, msg)
                        current_tokens += msg_tokens
                break
        
        self.conversations[user_id] = trimmed_messages
    
    def detect_conversation_end(self, user_id: int) -> bool:
        """
        Определяет логическое завершение диалога
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если диалог логически завершен
        """
        if user_id not in self.conversations or not self.conversations[user_id]:
            return False
            
        # Берем последние несколько сообщений для анализа
        recent_messages = self.conversations[user_id][-4:]
        
        conversation_text = ""
        for msg in recent_messages:
            conversation_text += f" {msg.content.lower()}"
        
        # Ключевые фразы завершения диалога
        end_phrases = [
            "спасибо за помощь", "до свидания", "всего доброго", "пока",
            "заказ оформлен", "спасибо, это все", "больше ничего не нужно",
            "разберусь сам", "передам менеджеру", "свяжется менеджер"
        ]
        
        return any(phrase in conversation_text for phrase in end_phrases)