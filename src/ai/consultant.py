"""
ИИ консультант для обработки запросов клиентов
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
        
        # Менеджер контекста диалогов (100К токенов ≈ 400К символов ≈ длинный диалог)
        self.context_manager = DialogueContextManager(max_tokens_per_context=100000, session_timeout_minutes=60)
        
        # AmoCRM клиент
        self.amocrm_client = AmoCRMClient()
        
        # Менеджер каталога товаров
        self.product_manager = ProductManager()
        
        # Менеджер автоматизации заказов
        self.order_automation = OrderAutomationManager(self.product_manager)
        
        # Кэш активных сценариев заказов
        self.active_order_scenarios = {}
        
        app_logger.info("ИИ консультант инициализирован")
    
    
    async def process_message(self, user_id: int, user_message: str) -> str:
        """
        Обработка сообщения пользователя с учетом контекста диалога
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение от пользователя
            
        Returns:
            Ответ ИИ консультанта
        """
        try:
            # Проверяем первое ли это взаимодействие перед добавлением сообщения
            is_first_interaction = self.context_manager.is_first_interaction(user_id)
            
            # При первом взаимодействии создаем контакт и сделку в AmoCRM
            if is_first_interaction:
                await self.amocrm_client.get_or_create_contact_and_lead(user_id)
                app_logger.info(f"Создан контакт и сделка в AmoCRM для пользователя {user_id}")
            
            # Добавляем сообщение пользователя в контекст
            self.context_manager.add_message(user_id, user_message, is_bot=False)
            
            # Получаем контекст диалога
            context_history = self.context_manager.get_context(user_id)
            
            # Формируем расширенный системный промпт с контекстом
            enhanced_system_prompt = get_enhanced_system_prompt(
                context_history=context_history,
                is_first_interaction=is_first_interaction
            )
            
            # Формируем историю диалога для OpenAI
            messages = [
                {"role": "system", "content": enhanced_system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Запрос к OpenAI
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
            
            # Проверяем, нужно ли показать товары
            products_message = await self._handle_product_requests(user_id, user_message, ai_response)
            if products_message:
                ai_response += "\n\n" + products_message
            
            # Проверяем запросы о доставке
            delivery_message = await self._handle_delivery_requests(user_id, user_message, ai_response)
            if delivery_message:
                ai_response += "\n\n" + delivery_message
            
            # Проверяем запросы на оформление заказа
            order_message = await self._handle_order_requests(user_id, user_message, ai_response)
            if order_message:
                ai_response += "\n\n" + order_message
            
            # Логируем переписку в AmoCRM
            await self.amocrm_client.log_conversation(user_id, user_message, ai_response)
            
            # Проверяем логическое завершение диалога
            if self.context_manager.detect_conversation_end(user_id):
                app_logger.info(f"Обнаружено логическое завершение диалога для пользователя {user_id}")
                # Не очищаем сразу, но помечаем в логах для анализа
            
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
    
    async def escalate_to_manager(self, user_id: int, user_message: str, reason: str = "Клиент требует менеджера"):
        """
        Эскалирует диалог к живому менеджеру
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение пользователя
            reason: Причина эскалации
        """
        try:
            await self.amocrm_client.escalate_to_manager(user_id, f"{reason}. Последнее сообщение: {user_message}")
            app_logger.info(f"Эскалация к менеджеру для пользователя {user_id}: {reason}")
        except Exception as e:
            app_logger.error(f"Ошибка эскалации для пользователя {user_id}: {e}")
    
    async def _handle_product_requests(self, user_id: int, user_message: str, ai_response: str) -> Optional[str]:
        """
        Обрабатывает запросы на показ товаров
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение пользователя
            ai_response: Ответ ИИ
            
        Returns:
            Дополнительное сообщение с товарами или None
        """
        try:
            # Ключевые фразы для показа товаров
            product_triggers = [
                'покажи', 'покажите', 'хочу посмотреть', 'какие есть',
                'что у вас есть', 'ассортимент', 'каталог', 'товары',
                'выбрать', 'подобрать', 'найти', 'ищу'
            ]
            
            message_lower = user_message.lower()
            should_show_products = any(trigger in message_lower for trigger in product_triggers)
            
            if not should_show_products:
                return None
            
            # Извлекаем параметры поиска
            budget = self.product_manager.parse_budget_from_text(user_message)
            category = self.product_manager.extract_category_from_text(user_message)
            
            app_logger.info(f"Поиск товаров для пользователя {user_id}: бюджет={budget}, категория={category}")
            
            # Ищем товары с использованием умного поиска
            if category and budget:
                # Есть и категория, и бюджет - ищем рекомендации
                products = await self.product_manager.get_product_recommendations(budget, category)
            elif category:
                # Только категория - используем умный поиск
                products = await self.product_manager.smart_search("", category=category)
            elif budget:
                # Только бюджет - используем умный поиск с ограничением по цене
                products = await self.product_manager.smart_search("янтарь", budget_min=budget*0.8, budget_max=budget*1.2)
            else:
                # Общий поиск - используем семантический поиск для лучшего понимания запроса
                search_query = user_message.lower()
                # Удаляем триггерные слова из запроса для чистого семантического поиска
                for trigger in product_triggers:
                    search_query = search_query.replace(trigger, "").strip()
                
                if search_query:
                    # Если есть содержательный запрос, используем семантический поиск с динамическим порогом
                    threshold = self.product_manager._calculate_semantic_threshold(search_query, category=None, has_budget=False)
                    products = await self.product_manager.semantic_search(search_query, limit=5, threshold=threshold)
                else:
                    # Иначе показываем популярные товары
                    products = await self.product_manager.smart_search("янтарь")
            
            # Автоматически добавляем эмбеддинги для новых товаров
            if products:
                await self.product_manager.auto_update_embeddings_for_new_products(products)
            
            if products:
                # Форматируем список товаров
                products_text = self.product_manager.format_products_list(products, max_products=5)
                return f"🛍️ **Товары из нашего каталога:**\n\n{products_text}"
            else:
                return "😔 К сожалению, товары по вашим критериям не найдены. Попробуйте изменить параметры поиска."
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки запроса товаров: {e}")
            return None
    
    async def create_order_from_chat(self, user_id: int, product_ids: List[str], customer_data: Dict) -> Optional[str]:
        """
        Создает заказ на основе выбранных в чате товаров
        
        Args:
            user_id: ID пользователя
            product_ids: Список ID выбранных товаров  
            customer_data: Данные клиента
            
        Returns:
            ID созданного заказа или None
        """
        try:
            # Подготавливаем список товаров для заказа
            products_for_order = []
            for product_id in product_ids:
                products_for_order.append({
                    'product_id': product_id,
                    'quantity': 1  # По умолчанию 1 штука
                })
            
            # Создаем заказ
            order_id = await self.product_manager.create_order(customer_data, products_for_order, user_id)
            
            if order_id:
                app_logger.info(f"Создан заказ {order_id} для пользователя {user_id}")
                
                # Добавляем информацию о заказе в AmoCRM
                await self.amocrm_client.add_note_to_lead(
                    user_id,  # Используем как lead_id (нужно будет получить реальный)
                    f"📦 Создан заказ в МойСклад: {order_id}\n💰 Товаров в заказе: {len(product_ids)}"
                )
                
                return order_id
            else:
                app_logger.error(f"Ошибка создания заказа для пользователя {user_id}")
                return None
                
        except Exception as e:
            app_logger.error(f"Ошибка создания заказа из чата: {e}")
            return None
    
    async def _handle_delivery_requests(self, user_id: int, user_message: str, ai_response: str) -> Optional[str]:
        """
        Обрабатывает запросы о доставке
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение пользователя
            ai_response: Ответ ИИ
            
        Returns:
            Дополнительное сообщение с информацией о доставке или None
        """
        try:
            # Ключевые фразы для запросов о доставке
            delivery_triggers = [
                'доставка', 'доставить', 'доставляете', 'доставим',
                'отправка', 'отправить', 'отправляете', 'отправим',
                'почта', 'курьер', 'стоимость доставки', 'сроки доставки',
                'индекс', 'адрес', 'во сколько обойдется доставка',
                'сколько стоит доставка', 'когда получу', 'через сколько дней',
                'поставка', 'получение'
            ]
            
            message_lower = user_message.lower()
            should_handle_delivery = any(trigger in message_lower for trigger in delivery_triggers)
            
            if not should_handle_delivery:
                return None
            
            # Пытаемся извлечь почтовый индекс из сообщения
            postcode = self.product_manager.parse_postcode_from_text(user_message)
            
            if postcode:
                app_logger.info(f"Найден индекс {postcode} в запросе о доставке от пользователя {user_id}")
                
                # Рассчитываем доставку
                delivery_info = await self.product_manager.calculate_delivery_cost(postcode)
                
                if delivery_info["success"]:
                    # Получаем варианты доставки
                    delivery_options = await self.product_manager.get_delivery_options(postcode)
                    
                    # Форматируем информацию
                    delivery_text = self.product_manager.format_delivery_info_with_products(delivery_info)
                    
                    # Добавляем дополнительные варианты если есть
                    if len(delivery_options) > 1:
                        delivery_text += "\n\n🚚 **Другие варианты доставки:**\n"
                        for option in delivery_options[1:]:  # Пропускаем первый (уже показан)
                            delivery_text += f"• {option['name']}: {option['cost']}₽ за {option['delivery_time']} дней\n"
                    
                    delivery_text += "\n\n💡 *Точный расчет доставки зависит от веса и количества товаров в заказе*"
                    
                    return f"📦 **Информация о доставке:**\n\n{delivery_text}"
                else:
                    return f"❌ {delivery_info.get('error', 'Ошибка расчета доставки')}"
            else:
                # Индекс не найден, предлагаем его указать
                return """📮 **Для расчета доставки укажите ваш почтовый индекс**

Пример: "Рассчитайте доставку на 101000"

📍 После получения индекса я смогу показать:
• Точную стоимость доставки
• Сроки доставки 
• Дату получения
• Варианты отправки (обычная почта, EMS)

🚚 Доставляем по всей России через Почту России с полным трекингом и страхованием!"""
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки запроса доставки: {e}")
            return None
    
    async def _handle_order_requests(self, user_id: int, user_message: str, ai_response: str) -> Optional[str]:
        """
        Обрабатывает запросы на оформление заказа
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение пользователя
            ai_response: Ответ ИИ
            
        Returns:
            Дополнительное сообщение с информацией о заказе или None
        """
        try:
            # Ключевые фразы для оформления заказа
            order_triggers = [
                'заказать', 'заказываю', 'хочу заказать', 'оформить заказ',
                'купить', 'покупаю', 'хочу купить', 'приобрести',
                'оплатить', 'оплачу', 'к оплате', 'счет',
                'оформление', 'корзина', 'чекаут', 'checkout'
            ]
            
            message_lower = user_message.lower()
            should_handle_order = any(trigger in message_lower for trigger in order_triggers)
            
            if not should_handle_order:
                return None
            
            app_logger.info(f"Обнаружен запрос на оформление заказа от пользователя {user_id}")
            
            # Для простого демо создаем заказ с фиктивными товарами
            # В реальной системе товары должны браться из корзины пользователя
            demo_products = [
                {
                    "id": "demo_product_1",
                    "name": "Кольцо с янтарем",
                    "price": 2500,
                    "quantity": 1
                }
            ]
            
            # Данные клиента (в реальной системе собираются через форму)
            customer_data = {
                "name": "Клиент из Telegram",
                "phone": "+7 900 000 00 00", 
                "email": "customer@example.com",
                "telegram_user_id": str(user_id)
            }
            
            # Проверяем, есть ли информация о доставке в контексте
            context_history = self.context_manager.get_context(user_id)
            delivery_info = self._extract_delivery_from_context(context_history, user_message)
            
            # Создаем заказ с оплатой
            order_result = await self.product_manager.create_order_with_payment(
                customer_data=customer_data,
                products=demo_products,
                telegram_user_id=user_id,
                delivery_info=delivery_info
            )
            
            if order_result.get("success"):
                # Форматируем успешное сообщение о заказе
                order_message = self.product_manager.format_payment_info(order_result)
                
                # Добавляем инструкции по оплате
                order_message += "\n\n📱 **Как оплатить:**\n"
                order_message += "1. Перейдите по ссылке выше\n"
                order_message += "2. Выберите удобный способ оплаты\n"
                order_message += "3. Следуйте инструкциям на странице\n"
                order_message += "4. После оплаты вы получите подтверждение\n\n"
                order_message += "💬 Если возникнут вопросы, напишите нам!"
                
                return f"🛒 **Заказ оформлен!**\n\n{order_message}"
            else:
                error_message = order_result.get("error", "Неизвестная ошибка")
                return f"❌ **Не удалось оформить заказ**\n\n{error_message}\n\nПожалуйста, попробуйте еще раз или обратитесь к нашему менеджеру."
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки запроса заказа: {e}")
            return None
    
    def _extract_delivery_from_context(self, context_history: str, current_message: str) -> Optional[Dict]:
        """
        Извлекает информацию о доставке из контекста диалога
        
        Args:
            context_history: История диалога
            current_message: Текущее сообщение
            
        Returns:
            Информация о доставке или None
        """
        try:
            # Ищем почтовый индекс в текущем сообщении или истории
            postcode = self.product_manager.parse_postcode_from_text(current_message)
            if not postcode:
                postcode = self.product_manager.parse_postcode_from_text(context_history)
            
            if postcode:
                # Если есть индекс, возвращаем базовую информацию о доставке
                return {
                    "cost": 200,  # Примерная стоимость
                    "service_name": "Почта России",
                    "delivery_time": 3,
                    "postcode": postcode
                }
            
            return None
            
        except Exception as e:
            app_logger.error(f"Ошибка извлечения информации о доставке: {e}")
            return None