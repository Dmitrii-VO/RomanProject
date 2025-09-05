"""
ИИ консультант v2 с полной автоматизацией заказов и поведенческой моделью
"""
import os
import openai
from typing import Dict, Optional, List
from utils.logger import app_logger
from .context_manager import DialogueContextManager
from .prompts import get_enhanced_system_prompt
from src.integrations.amocrm_client import AmoCRMClient
from src.catalog.product_manager import ProductManager
from src.catalog.sync_scheduler import ProductSyncScheduler
from .order_automation_manager import OrderAutomationManager
from src.rag.conversation_rag_manager import ConversationRAGManager

# Новые компоненты поведенческой модели
from .intent_classifier import IntentClassifier
from .entity_extractor import EntityExtractor
from .dialogue_state_manager import DialogueStateManager
from .delivery_manager import DeliveryManager
from .guardrails import ConsultantGuardrails, SelfAssessment


class AmberAIConsultantV2:
    """
    Обновленный ИИ консультант с полной автоматизацией заказов
    """
    
    def __init__(self):
        """Инициализация ИИ консультанта v2 с поведенческой моделью"""
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
        
        # Менеджер каталога товаров с локальным индексом
        self.product_manager = ProductManager()
        
        # Планировщик синхронизации товаров
        self.sync_scheduler = ProductSyncScheduler()
        
        # Менеджер автоматизации заказов
        self.order_automation = OrderAutomationManager(self.product_manager)
        
        # RAG система для переписок
        self.rag_manager = ConversationRAGManager()
        
        # Компоненты поведенческой модели
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.dialogue_state_manager = DialogueStateManager()
        self.delivery_manager = DeliveryManager()
        self.guardrails = ConsultantGuardrails()
        self.self_assessment = SelfAssessment()
        
        # Кэш активных сценариев заказов
        self.active_order_scenarios = {}
        
        app_logger.info("ИИ консультант v2 с поведенческой моделью инициализирован")
    
    async def start_sync_scheduler(self):
        """Запускает планировщик синхронизации товаров и RAG систему"""
        try:
            await self.sync_scheduler.start(initial_sync=True)
            app_logger.info("Планировщик синхронизации товаров запущен")
            
            await self.rag_manager.start_scheduler()
            app_logger.info("RAG система запущена")
        except Exception as e:
            app_logger.error(f"Ошибка запуска планировщиков: {e}")
    
    async def stop_sync_scheduler(self):
        """Останавливает планировщик синхронизации товаров и RAG систему"""
        try:
            await self.sync_scheduler.stop()
            app_logger.info("Планировщик синхронизации товаров остановлен")
            
            await self.rag_manager.stop_scheduler()
            app_logger.info("RAG система остановлена")
        except Exception as e:
            app_logger.error(f"Ошибка остановки планировщиков: {e}")
    
    def get_system_status(self) -> Dict:
        """Получает статус всех систем консультанта"""
        search_status = self.product_manager.get_search_status()
        scheduler_status = self.sync_scheduler.get_status()
        rag_status = self.rag_manager.get_system_status()
        
        return {
            "consultant_version": "v2_with_rag_and_cache",
            "search_system": search_status,
            "sync_scheduler": scheduler_status,
            "rag_system": rag_status,
            "active_scenarios": len(self.active_order_scenarios),
            "fallback_warning": search_status.get("fallback_critical", False)
        }
    
    async def process_message(self, user_id: int, user_message: str) -> str:
        """
        Обработка сообщения пользователя с поведенческой моделью и полным сценарием автоматизации
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение от пользователя
            
        Returns:
            Ответ ИИ консультанта
        """
        try:
            # === Этап 1: Анализ входящего сообщения ===
            # Классификация намерения
            intent, intent_confidence = self.intent_classifier.classify_intent(user_message)
            app_logger.info(f"Классифицированное намерение: {intent} (уверенность: {intent_confidence:.2f})")
            
            # Извлечение сущностей
            entities = self.entity_extractor.extract_entities(user_message)
            app_logger.info(f"Извлеченные сущности: {entities}")
            
            # === Этап 2: Управление состоянием диалога ===
            # Получаем или создаем состояние диалога
            if user_id not in self.active_order_scenarios:
                # Инициализируем новое состояние диалога
                dialogue_state = self.dialogue_state_manager.initialize_dialogue(user_id, intent, entities)
            else:
                # Обновляем существующее состояние
                dialogue_state = self.active_order_scenarios[user_id].get("dialogue_state", {})
                dialogue_state = self.dialogue_state_manager.update_state(dialogue_state, intent, entities, user_message)
            
            # === Этап 3: Определение следующих действий ===
            # Проверяем, нужно ли передать менеджеру
            if self.dialogue_state_manager.should_escalate_to_manager(dialogue_state):
                return await self._handle_escalation_to_manager(user_id, dialogue_state, user_message)
            
            # Проверяем старый механизм активных сценариев заказов (только если уже начат процесс заказа)
            if user_id in self.active_order_scenarios and "next_action" in self.active_order_scenarios[user_id]:
                return await self._handle_active_order_scenario(user_id, user_message)
            
            # === ПРИОРИТЕТ: Поведенческая модель обрабатывает намерения ПЕРВОЙ ===
            # Обрабатываем по типу намерения
            if intent == "buy":
                # Для намерения покупки - сначала показываем товары, потом предлагаем заказ
                return await self._handle_purchase_intent(user_id, dialogue_state, user_message, entities)
            elif intent == "browse_catalog":
                return await self._handle_catalog_browsing(user_id, dialogue_state, user_message, entities)
            elif intent == "delivery":
                return await self._handle_delivery_inquiry(user_id, dialogue_state, user_message, entities)
            elif intent == "handover_request":
                return await self._handle_escalation_to_manager(user_id, dialogue_state, user_message)
            elif intent == "product_question" and dialogue_state.get("current_stage") in ["selection", "ordering"]:
                return await self._handle_purchase_intent(user_id, dialogue_state, user_message, entities)
            else:
                # === FALLBACK: Старая логика только если поведенческая модель не обработала ===
                
                # Проверяем намерение оформить заказ (только если поведенческая модель не сработала)
                order_intent = self.order_automation.detect_order_intent(user_message)
                if order_intent.get("has_intent"):
                    app_logger.info("Поведенческая модель не обработала, используем старую автоматизацию заказов")
                    return await self._start_order_automation(user_id, order_intent, user_message)
                
                # Стандартная обработка для остальных интентов
                return await self._process_standard_message_with_behavior(user_id, user_message, intent, entities, dialogue_state)
            
        except Exception as e:
            app_logger.error(f"Ошибка обработки сообщения с поведенческой моделью: {e}")
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
    
    async def _handle_purchase_intent(self, user_id: int, dialogue_state: Dict, user_message: str, entities: Dict) -> str:
        """Обработка намерения покупки с поведенческой моделью"""
        try:
            # Проверяем, достаточно ли данных для поиска товаров
            missing_slots = self.dialogue_state_manager.get_missing_slots_for_search(dialogue_state)
            
            if missing_slots:
                # Генерируем вопрос для сбора недостающих данных
                question = self._generate_slot_collection_question(missing_slots[0], dialogue_state)
                # Обновляем состояние диалога
                dialogue_state["current_stage"] = "slot_filling"
                dialogue_state["awaiting_slot"] = missing_slots[0]
                self.active_order_scenarios[user_id] = {"dialogue_state": dialogue_state}
                return question
            
            # Если данных достаточно - ищем товары
            search_params = self._build_search_params_from_entities(entities, dialogue_state)
            all_products = await self.product_manager.search_products(query=user_message, **search_params)
            
            # Фильтруем только товары в наличии
            products = self._filter_products_in_stock(all_products)
            
            if products:
                dialogue_state["current_stage"] = "selection"
                dialogue_state["found_products"] = products[:5]  # Ограничиваем до 5 товаров
                self.active_order_scenarios[user_id] = {"dialogue_state": dialogue_state}
                
                products_text = self.product_manager.format_products_list(products, max_products=5)
                return f"🛍️ **Подобрал товары по вашим критериям (в наличии):**\n\n{products_text}\n\nКакой товар вас заинтересовал?"
            else:
                # Если в наличии нет товаров, предлагаем связаться с менеджером
                out_of_stock_count = len(all_products) - len(products)
                if out_of_stock_count > 0:
                    return f"😔 К сожалению, товары по вашим критериям сейчас не в наличии (найдено {out_of_stock_count} товаров, но они закончились). Свяжитесь с нашим менеджером - возможно, товары поступят в ближайшее время!"
                else:
                    return "😔 К сожалению, товары по вашим критериям не найдены. Попробуйте изменить запрос или свяжитесь с нашим менеджером."
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки намерения покупки: {e}")
            return "Произошла ошибка при поиске товаров. Попробуйте еще раз!"
    
    async def _handle_catalog_browsing(self, user_id: int, dialogue_state: Dict, user_message: str, entities: Dict) -> str:
        """Обработка просмотра каталога"""
        try:
            # Поиск товаров для просмотра
            search_params = self._build_search_params_from_entities(entities, dialogue_state)
            all_products = await self.product_manager.search_products(query=user_message, **search_params)
            
            # Фильтруем только товары в наличии
            products = self._filter_products_in_stock(all_products)
            
            if products:
                products_text = self.product_manager.format_products_list(products, max_products=3)
                return f"🛍️ **Товары из нашего каталога (в наличии):**\n\n{products_text}"
            else:
                out_of_stock_count = len(all_products) - len(products)
                if out_of_stock_count > 0:
                    return f"😔 К сожалению, товары по вашим критериям сейчас не в наличии (найдено {out_of_stock_count} товаров, но они закончились)."
                else:
                    return "😔 К сожалению, товары по вашим критериям не найдены."
                
        except Exception as e:
            app_logger.error(f"Ошибка просмотра каталога: {e}")
            return None
    
    async def _handle_delivery_inquiry(self, user_id: int, dialogue_state: Dict, user_message: str, entities: Dict) -> str:
        """Обработка вопросов о доставке с использованием DeliveryManager"""
        try:
            # Извлекаем информацию о заказе из состояния диалога
            order_total = dialogue_state.get("order_total", 0)
            city = entities.get("city") or dialogue_state.get("city")
            postcode = entities.get("postcode") or dialogue_state.get("postcode")
            
            if order_total > 0:
                # Есть информация о заказе - рассчитываем точную стоимость доставки
                delivery_info = self.delivery_manager.calculate_delivery_cost(order_total, city)
                return f"📦 **Информация о доставке:**\n\n{delivery_info['message']}"
            else:
                # Общая информация о доставке
                return self.delivery_manager.get_delivery_info()
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки запроса доставки: {e}")
            return self.delivery_manager.get_delivery_info()
    
    async def _handle_escalation_to_manager(self, user_id: int, dialogue_state: Dict, user_message: str) -> str:
        """Обработка передачи менеджеру"""
        # Сохраняем контекст для менеджера
        dialogue_state["escalated_to_manager"] = True
        dialogue_state["escalation_reason"] = user_message
        self.active_order_scenarios[user_id] = {"dialogue_state": dialogue_state}
        
        return """👨‍💼 **Передаю вас менеджеру**
        
Ваш запрос передан нашему менеджеру. Он свяжется с вами в ближайшее время для персональной консультации.
        
⏰ Время работы менеджера: Пн-Пт 9:00-18:00
📱 Контакты: +7 (XXX) XXX-XX-XX"""
    
    def _generate_slot_collection_question(self, slot_name: str, dialogue_state: Dict) -> str:
        """Генерирует вопрос для сбора недостающих данных"""
        questions = {
            "category": "Какой тип украшения вас интересует? (кольцо, серьги, кулон, браслет, колье)",
            "budget": "Какой у вас бюджет на покупку?",
            "style": "Какой стиль вам больше нравится? (классический, современный, винтажный)",
            "city": "В какой город нужна доставка?",
            "postcode": "Укажите почтовый индекс для точного расчета доставки",
            "name": "Как к вам обращаться?",
            "phone": "Укажите ваш номер телефона для связи"
        }
        return questions.get(slot_name, "Уточните, пожалуйста, дополнительную информацию")
    
    def _build_search_params_from_entities(self, entities: Dict, dialogue_state: Dict) -> Dict:
        """Строит параметры поиска на основе извлеченных сущностей"""
        search_params = {}
        
        # Используем сущности из текущего сообщения и состояния диалога
        all_entities = {**dialogue_state.get("entities", {}), **entities}
        
        if all_entities.get("category"):
            search_params["category"] = all_entities["category"]
        if all_entities.get("budget"):
            budget_info = all_entities["budget"]
            if isinstance(budget_info, dict):
                if "value" in budget_info:
                    # Если указана конкретная сумма
                    search_params["max_price"] = budget_info["value"]
                elif "max" in budget_info:
                    search_params["max_price"] = budget_info["max"]
                if "min" in budget_info:
                    search_params["min_price"] = budget_info["min"]
        
        return search_params
    
    def _filter_products_in_stock(self, products: List[Dict]) -> List[Dict]:
        """Фильтрует товары, оставляя только те, что в наличии"""
        if not products:
            return []
        
        in_stock_products = []
        for product in products:
            # Проверяем наличие товара по полям quantity, stock или in_stock
            quantity = product.get('quantity', 0)
            stock = product.get('stock', 0)
            in_stock = product.get('in_stock', True)  # По умолчанию считаем что в наличии
            
            # Товар в наличии если:
            # 1. quantity > 0, или
            # 2. stock > 0, или  
            # 3. in_stock = True и нет информации о количестве
            if (quantity and quantity > 0) or (stock and stock > 0) or (in_stock and not quantity and not stock):
                in_stock_products.append(product)
        
        app_logger.info(f"Отфильтровано товаров в наличии: {len(in_stock_products)} из {len(products)}")
        return in_stock_products
    
    async def _process_standard_message_with_behavior(self, user_id: int, user_message: str, intent: str, entities: Dict, dialogue_state: Dict) -> str:
        """Стандартная обработка сообщения с поведенческой моделью"""
        # Сохраняем состояние диалога
        if dialogue_state:
            self.active_order_scenarios[user_id] = {"dialogue_state": dialogue_state}
        
        # Вызываем стандартную обработку
        response = await self._process_standard_message(user_id, user_message)
        
        # Применяем гарантии качества
        quality_check_results = self.guardrails.check_response(response, {"user_message": user_message})
        critical_issues = [r for r in quality_check_results if r.severity == "critical" and not r.passed]
        if critical_issues:
            app_logger.warning(f"Обнаружены критические проблемы качества: {[issue.message for issue in critical_issues]}")
            # При критических проблемах переписываем ответ
            response = "Извините, я не могу предоставить точную информацию по вашему вопросу. Обратитесь к нашему менеджеру для получения подробной консультации."
        
        # Самооценка качества ответа
        assessment = self.self_assessment.assess_response(user_message, response, intent, entities)
        app_logger.info(f"Оценка качества ответа: {assessment['overall_score']:.2f}")
        
        return response
    
    async def _process_standard_message(self, user_id: int, user_message: str) -> str:
        """Стандартная обработка сообщения через ИИ с RAG"""
        # Проверяем первое ли это взаимодействие
        is_first_interaction = self.context_manager.is_first_interaction(user_id)
        
        # При первом взаимодействии создаем контакт и сделку в AmoCRM
        deal_id = None
        if is_first_interaction:
            contact_id, lead_id = await self.amocrm_client.get_or_create_contact_and_lead(user_id)
            deal_id = lead_id
            app_logger.info(f"Создан контакт и сделка в AmoCRM для пользователя {user_id}")
        
        # Индексируем сообщение пользователя в RAG (асинхронно)
        await self.rag_manager.index_message(
            customer_id=str(user_id),
            sender_type="customer",
            content=user_message,
            deal_id=str(deal_id) if deal_id else None
        )
        
        # Получаем релевантный контекст из RAG
        rag_context = await self.rag_manager.get_relevant_context(
            query=user_message,
            customer_id=str(user_id),
            deal_id=str(deal_id) if deal_id else None,
            context_type="general"
        )
        
        # Добавляем сообщение пользователя в контекст
        self.context_manager.add_message(user_id, user_message, is_bot=False)
        
        # Получаем контекст диалога
        context_history = self.context_manager.get_context(user_id)
        
        # Формируем расширенный системный промпт с RAG контекстом
        enhanced_system_prompt = get_enhanced_system_prompt(
            context_history=context_history,
            is_first_interaction=is_first_interaction,
            rag_context=rag_context.get('context_summary', '')
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
        
        # Индексируем ответ бота в RAG (асинхронно)
        await self.rag_manager.index_message(
            customer_id=str(user_id),
            sender_type="bot",
            content=ai_response,
            deal_id=str(deal_id) if deal_id else None
        )
        
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
        """Обрабатывает запросы о доставке с использованием DeliveryManager"""
        try:
            delivery_triggers = [
                'доставка', 'доставить', 'отправка', 'почта', 'курьер',
                'стоимость доставки', 'сроки доставки', 'индекс'
            ]
            
            message_lower = user_message.lower()
            should_handle_delivery = any(trigger in message_lower for trigger in delivery_triggers)
            
            if not should_handle_delivery:
                return None
            
            # Извлекаем сущности для более точного расчета доставки
            entities = self.entity_extractor.extract_entities(user_message)
            
            # Получаем информацию о заказе из состояния диалога, если есть
            order_total = 0
            if user_id in self.active_order_scenarios:
                dialogue_state = self.active_order_scenarios[user_id].get("dialogue_state", {})
                order_total = dialogue_state.get("order_total", 0)
            
            city = entities.get("city")
            postcode = entities.get("postcode")
            
            if order_total > 0:
                # Есть информация о заказе - рассчитываем точную стоимость доставки
                delivery_info = self.delivery_manager.calculate_delivery_cost(order_total, city)
                return f"📦 **Информация о доставке для вашего заказа:**\n\n{delivery_info['message']}"
            else:
                # Общая информация о доставке
                return f"📦 **Информация о доставке:**\n\n{self.delivery_manager.get_delivery_info()}"
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки запроса доставки: {e}")
            return f"📦 **Информация о доставке:**\n\n{self.delivery_manager.get_delivery_info()}"