"""
ИИ консультант v2 с полной автоматизацией заказов
"""
import os
import openai
from typing import Dict, Optional, List
from utils.logger import app_logger
from .context_manager import DialogueContextManager
from .prompts import get_enhanced_system_prompt
from src.integrations.amocrm_client import AmoCRMClient
from src.catalog.product_manager import ProductManager
from .order_automation_manager import OrderAutomationManager


class AmberAIConsultantV2:
    """
    Обновленный ИИ консультант с полной автоматизацией заказов
    """
    
    def __init__(self):
        """Инициализация ИИ консультанта v2"""
        self.client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OpenAI_BASE_URL")
        )
        
        # Параметры генерации
        self.temperature = float(os.getenv("AI_TEMPERATURE", 0.7))
        self.max_tokens = int(os.getenv("AI_MAX_TOKENS", 500))
        self.presence_penalty = float(os.getenv("AI_PRESENCE_PENALTY", 0.6))
        self.frequency_penalty = float(os.getenv("AI_FREQUENCY_PENALTY", 0.5))
        
        # Менеджер контекста диалогов
        self.context_manager = DialogueContextManager(max_tokens_per_context=100000, session_timeout_minutes=60)
        
        # AmoCRM клиент
        self.amocrm_client = AmoCRMClient()
        
        # Менеджер каталога товаров
        self.product_manager = ProductManager()
        
        # Менеджер автоматизации заказов
        self.order_automation = OrderAutomationManager(self.product_manager)
        
        # Кэш активных сценариев заказов
        self.active_order_scenarios = {}
        
        app_logger.info("ИИ консультант v2 с автоматизацией заказов инициализирован")
    
    async def process_message(self, user_id: int, user_message: str) -> str:
        """
        Обработка сообщения пользователя с полным сценарием автоматизации
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение от пользователя
            
        Returns:
            Ответ ИИ консультанта
        """
        try:
            # Проверяем, есть ли активный сценарий заказа
            if user_id in self.active_order_scenarios:
                return await self._handle_active_order_scenario(user_id, user_message)
            
            # Проверяем намерение оформить заказ
            order_intent = self.order_automation.detect_order_intent(user_message)
            if order_intent.get("has_intent"):
                return await self._start_order_automation(user_id, order_intent, user_message)
            
            # Стандартная обработка ИИ консультанта
            return await self._process_standard_message(user_id, user_message)
            
        except Exception as e:
            app_logger.error(f"Ошибка обработки сообщения ИИ v2: {e}")
            return "Извините, произошла техническая ошибка. Пожалуйста, попробуйте еще раз или обратитесь к нашему менеджеру."
    
    async def _handle_active_order_scenario(self, user_id: int, user_message: str) -> str:
        """Обрабатывает сообщение в рамках активного сценария заказа"""
        scenario_state = self.active_order_scenarios[user_id]
        current_step = scenario_state.get("next_action")
        
        try:
            if current_step == "await_confirmation":
                result = await self.order_automation.process_confirmation_response(user_id, user_message, scenario_state)
            elif current_step in ["collect_product_type", "collect_budget"]:
                result = await self._handle_data_collection(user_id, user_message, scenario_state)
            elif current_step == "select_product":
                result = await self.order_automation.process_product_selection(user_id, user_message, scenario_state)
            elif current_step == "final_confirmation":
                result = await self.order_automation.process_final_confirmation(user_id, user_message, scenario_state)
            elif current_step == "collect_recipient_data":
                result = await self._handle_recipient_data_collection(user_id, user_message, scenario_state)
            else:
                # Неизвестный шаг - сбрасываем сценарий
                del self.active_order_scenarios[user_id]
                return await self._process_standard_message(user_id, user_message)
            
            # Обновляем или завершаем сценарий
            if result.get("scenario_completed"):
                if user_id in self.active_order_scenarios:
                    del self.active_order_scenarios[user_id]
            elif result.get("scenario_state"):
                self.active_order_scenarios[user_id] = result["scenario_state"]
            
            # Логируем в AmoCRM
            response_message = result.get("response_message", "Обработка заказа...")
            await self.amocrm_client.log_conversation(user_id, user_message, response_message)
            
            return response_message
            
        except Exception as e:
            app_logger.error(f"Ошибка обработки активного сценария заказа: {e}")
            # Сбрасываем сценарий при ошибке
            if user_id in self.active_order_scenarios:
                del self.active_order_scenarios[user_id]
            return "Произошла ошибка при обработке заказа. Давайте начнем сначала!"
    
    async def _start_order_automation(self, user_id: int, order_intent: Dict, user_message: str) -> str:
        """Запускает автоматизированный сценарий заказа"""
        try:
            # Получаем контекст пользователя
            user_context = self._get_user_context(user_id)
            
            # Запускаем сценарий автоматизации
            result = await self.order_automation.process_order_scenario(user_id, order_intent, user_context)
            
            if result.get("success"):
                # Сохраняем состояние сценария
                if result.get("scenario_state"):
                    self.active_order_scenarios[user_id] = result["scenario_state"]
                
                response_message = result.get("response_message")
                
                # Логируем в AmoCRM
                await self.amocrm_client.log_conversation(user_id, user_message, response_message)
                
                return response_message
            else:
                error_msg = result.get("response_message", "Не удалось обработать запрос на заказ.")
                await self.amocrm_client.log_conversation(user_id, user_message, error_msg)
                return error_msg
                
        except Exception as e:
            app_logger.error(f"Ошибка запуска автоматизации заказа: {e}")
            return "Произошла ошибка при обработке вашего запроса. Попробуйте еще раз!"
    
    async def _handle_data_collection(self, user_id: int, user_message: str, scenario_state: Dict) -> Dict:
        """Обрабатывает сбор данных для заказа"""
        missing_data = scenario_state.get("missing_data", [])
        if not missing_data:
            return await self.order_automation._search_and_show_products(scenario_state)
        
        current_data_type = missing_data[0]
        intent = scenario_state["intent"]
        
        # Обновляем данные на основе ответа пользователя
        if current_data_type == "product_type":
            extracted_type = self.order_automation._extract_order_parameters(user_message).get("product_type")
            if extracted_type:
                intent["product_type"] = extracted_type
                missing_data.remove("product_type")
        elif current_data_type == "budget":
            extracted_budget = self.order_automation._extract_order_parameters(user_message).get("budget")
            if extracted_budget:
                intent["budget"] = extracted_budget
                missing_data.remove("budget")
        
        # Продолжаем сбор данных или переходим к поиску товаров
        scenario_state["missing_data"] = missing_data
        
        if missing_data:
            # Еще есть данные для сбора
            question = await self.order_automation._generate_data_collection_question(missing_data[0], scenario_state)
            return {
                "success": True,
                "scenario_state": scenario_state,
                "response_message": question,
                "next_action": f"collect_{missing_data[0]}",
                "requires_user_input": True
            }
        else:
            # Все данные собраны - ищем товары
            return await self.order_automation._search_and_show_products(scenario_state)
    
    async def _handle_recipient_data_collection(self, user_id: int, user_message: str, scenario_state: Dict) -> Dict:
        """Обрабатывает сбор данных получателя"""
        # Парсим данные получателя из сообщения
        recipient_data = self._parse_recipient_data(user_message)
        
        if recipient_data.get("name") and recipient_data.get("phone"):
            # Данные собраны - обновляем контекст и создаем заказ
            scenario_state["context"].update(recipient_data)
            return await self.order_automation._create_final_order(user_id, scenario_state)
        else:
            # Данные неполные - переспрашиваем
            return {
                "success": True,
                "scenario_state": scenario_state,
                "response_message": (
                    "❌ Не удалось распознать данные получателя.\n\n"
                    "📋 Пожалуйста, укажите в формате:\n"
                    "**Имя Фамилия, +7 XXX XXX XX XX, ИНДЕКС**\n\n"
                    "Например: Анна Иванова, +7 900 123 45 67, 190000"
                ),
                "next_action": "collect_recipient_data",
                "requires_user_input": True
            }
    
    def _parse_recipient_data(self, message: str) -> Dict:
        """Парсит данные получателя из сообщения"""
        import re
        
        data = {}
        
        # Ищем телефон
        phone_pattern = r'\+?[78][\s\-]?\(?(\d{3})\)?[\s\-]?(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})'
        phone_match = re.search(phone_pattern, message)
        if phone_match:
            data["phone"] = f"+7 {phone_match.group(1)} {phone_match.group(2)} {phone_match.group(3)} {phone_match.group(4)}"
        
        # Ищем индекс
        postcode_match = re.search(r'\b(\d{6})\b', message)
        if postcode_match:
            data["postal_code"] = postcode_match.group(1)
        
        # Извлекаем имя (все что не телефон и не индекс)
        name_text = message
        if phone_match:
            name_text = name_text.replace(phone_match.group(0), "").strip()
        if postcode_match:
            name_text = name_text.replace(postcode_match.group(0), "").strip()
        
        # Очищаем от знаков препинания
        name_text = re.sub(r'[,;]', ' ', name_text).strip()
        
        if len(name_text.split()) >= 2:
            data["name"] = name_text
        
        return data
    
    async def _process_standard_message(self, user_id: int, user_message: str) -> str:
        """Стандартная обработка сообщения через ИИ"""
        # Проверяем первое ли это взаимодействие
        is_first_interaction = self.context_manager.is_first_interaction(user_id)
        
        # При первом взаимодействии создаем контакт и сделку в AmoCRM
        if is_first_interaction:
            await self.amocrm_client.get_or_create_contact_and_lead(user_id)
            app_logger.info(f"Создан контакт и сделка в AmoCRM для пользователя {user_id}")
        
        # Добавляем сообщение пользователя в контекст
        self.context_manager.add_message(user_id, user_message, is_bot=False)
        
        # Получаем контекст диалога
        context_history = self.context_manager.get_context(user_id)
        
        # Формируем расширенный системный промпт
        enhanced_system_prompt = get_enhanced_system_prompt(
            context_history=context_history,
            is_first_interaction=is_first_interaction
        )
        
        # Запрос к OpenAI
        messages = [
            {"role": "system", "content": enhanced_system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            presence_penalty=self.presence_penalty,
            frequency_penalty=self.frequency_penalty
        )
        
        ai_response = response.choices[0].message.content
        
        # Добавляем ответ ИИ в контекст
        self.context_manager.add_message(user_id, ai_response, is_bot=True)
        
        # Дополнительные обработчики (товары, доставка)
        additional_content = []
        
        products_message = await self._handle_product_requests(user_id, user_message, ai_response)
        if products_message:
            additional_content.append(products_message)
        
        delivery_message = await self._handle_delivery_requests(user_id, user_message, ai_response)
        if delivery_message:
            additional_content.append(delivery_message)
        
        if additional_content:
            ai_response += "\n\n" + "\n\n".join(additional_content)
        
        # Логируем переписку в AmoCRM
        await self.amocrm_client.log_conversation(user_id, user_message, ai_response)
        
        return ai_response
    
    def _get_user_context(self, user_id: int) -> Dict:
        """Получает контекст пользователя из истории диалогов"""
        context_history = self.context_manager.get_context(user_id)
        
        return {
            "name": f"Пользователь {user_id}",
            "telegram_id": user_id,
            "history": context_history
        }
    
    async def _handle_product_requests(self, user_id: int, user_message: str, ai_response: str) -> Optional[str]:
        """Обрабатывает запросы на показ товаров"""
        try:
            product_triggers = [
                'покажи', 'покажите', 'хочу посмотреть', 'какие есть',
                'что у вас есть', 'ассортимент', 'каталог', 'товары',
                'выбрать', 'подобрать', 'найти', 'ищу'
            ]
            
            message_lower = user_message.lower()
            should_show_products = any(trigger in message_lower for trigger in product_triggers)
            
            if not should_show_products:
                return None
            
            # Поиск товаров
            products = await self.product_manager.search_products(
                query=user_message
            )
            
            if products:
                products_text = self.product_manager.format_products_list(products, max_products=3)
                return f"🛍️ **Товары из нашего каталога:**\n\n{products_text}"
            else:
                return "😔 К сожалению, товары по вашим критериям не найдены."
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки запроса товаров: {e}")
            return None
    
    async def _handle_delivery_requests(self, user_id: int, user_message: str, ai_response: str) -> Optional[str]:
        """Обрабатывает запросы о доставке"""
        try:
            delivery_triggers = [
                'доставка', 'доставить', 'отправка', 'почта', 'курьер',
                'стоимость доставки', 'сроки доставки', 'индекс'
            ]
            
            message_lower = user_message.lower()
            should_handle_delivery = any(trigger in message_lower for trigger in delivery_triggers)
            
            if not should_handle_delivery:
                return None
            
            # Простая информация о доставке
            return """📦 **Доставка Почтой России:**

🎁 **Бесплатная доставка** от 15,000₽
💰 До 15,000₽ — по тарифам Почты России (оплата при получении)
⏰ Сроки: 3-7 рабочих дней
📍 Доставляем по всей России

Для точного расчета укажите ваш почтовый индекс!"""
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки запроса доставки: {e}")
            return None