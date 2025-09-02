"""
ИИ консультант для обработки запросов клиентов
"""
import os
import openai
from typing import Dict, Optional
from utils.logger import app_logger


class AmberAIConsultant:
    """
    Основной класс ИИ консультанта янтарного магазина
    """
    
    def __init__(self):
        """Инициализация ИИ консультанта"""
        self.client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OpenAI_BASE_URL")
        )
        
        # Параметры генерации
        self.temperature = float(os.getenv("AI_TEMPERATURE", 0.7))
        self.max_tokens = int(os.getenv("AI_MAX_TOKENS", 500))
        self.presence_penalty = float(os.getenv("AI_PRESENCE_PENALTY", 0.6))
        self.frequency_penalty = float(os.getenv("AI_FREQUENCY_PENALTY", 0.5))
        
        # Системный промпт
        self.system_prompt = self._load_system_prompt()
        
        app_logger.info("ИИ консультант инициализирован")
    
    def _load_system_prompt(self) -> str:
        """Загрузка системного промпта для ИИ"""
        return """
        Ты — опытный продавец-консультант интернет-магазина ювелирных украшений из янтаря.
        
        Твоя роль:
        - Помогаешь клиентам выбрать идеальные янтарные украшения
        - Рассказываешь о свойствах и происхождении янтаря
        - Учитываешь бюджет и предпочтения клиента
        - Оформляешь заказы и консультируешь по доставке
        - В сложных случаях передаешь клиента живому менеджеру
        
        Стиль общения:
        - Дружелюбный и профессиональный
        - Используй эмодзи умеренно
        - Пиши понятно и структурированно
        - Задавай уточняющие вопросы
        
        Помни: янтарь — это окаменевшая смола древних деревьев, обладающая целебными свойствами и красотой.
        """
    
    async def process_message(self, user_message: str, user_context: Optional[Dict] = None) -> str:
        """
        Обработка сообщения пользователя
        
        Args:
            user_message: Сообщение от пользователя
            user_context: Контекст пользователя (история, предпочтения и т.д.)
            
        Returns:
            Ответ ИИ консультанта
        """
        try:
            # Формируем историю диалога
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Если есть контекст, добавляем его
            if user_context and user_context.get("chat_history"):
                # TODO: Добавить историю диалога из контекста
                pass
            
            # Запрос к OpenAI
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                presence_penalty=self.presence_penalty,
                frequency_penalty=self.frequency_penalty
            )
            
            ai_response = response.choices[0].message.content
            app_logger.info(f"ИИ сгенерировал ответ: {len(ai_response)} символов")
            
            return ai_response
            
        except Exception as e:
            app_logger.error(f"Ошибка обработки сообщения ИИ: {e}")
            return "Извините, произошла техническая ошибка. Пожалуйста, попробуйте еще раз или обратитесь к нашему менеджеру."
    
    def should_escalate(self, user_message: str, ai_response: str) -> bool:
        """
        Определение необходимости эскалации к живому менеджеру
        
        Args:
            user_message: Сообщение пользователя
            ai_response: Ответ ИИ
            
        Returns:
            True если нужна эскалация
        """
        # Ключевые слова для эскалации
        escalation_keywords = [
            "жалоба", "недовольство", "возврат", "претензия",
            "некачественный", "брак", "не работает",
            "менеджер", "руководство", "начальник"
        ]
        
        user_lower = user_message.lower()
        for keyword in escalation_keywords:
            if keyword in user_lower:
                app_logger.info(f"Обнаружена необходимость эскалации по ключевому слову: {keyword}")
                return True
                
        return False