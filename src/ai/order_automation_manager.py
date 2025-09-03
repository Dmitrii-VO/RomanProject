"""
Менеджер автоматизации заказов - полный сценарий от запроса до оплаты
"""
import re
import asyncio
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime
from utils.logger import app_logger
from src.catalog.product_manager import ProductManager


class OrderAutomationManager:
    """
    Управляет полным сценарием автоматизации заказа:
    запрос → уточнение → подбор товара → заказ в МойСклад → доставка → счет → оплата → CRM
    """
    
    def __init__(self, product_manager: ProductManager):
        """Инициализация менеджера автоматизации"""
        self.product_manager = product_manager
        self.free_delivery_threshold = 15000.0  # Бесплатная доставка от 15000₽
        
        app_logger.info("OrderAutomationManager инициализирован")
    
    def detect_order_intent(self, message: str) -> Dict[str, Any]:
        """
        Определяет намерение оформить заказ и извлекает параметры
        
        Args:
            message: Сообщение пользователя
            
        Returns:
            Словарь с информацией о намерении
        """
        message_lower = message.lower()
        
        # Триггеры заказа (исключаем запросы на просмотр)
        order_triggers = [
            'хочу заказать', 'хочу купить', 'приобрести', 'оформить заказ',
            'заказать', 'оформляю', 'беру для покупки'
        ]
        
        # Триггеры просмотра каталога (НЕ заказа)
        view_triggers = [
            'покажи', 'покажите', 'посмотреть', 'какие есть', 'что у вас есть',
            'ассортимент', 'каталог', 'товары', 'выбрать из', 'подскажите что',
            'что можете предложить', 'варианты', 'предложите'
        ]
        
        # Если это запрос на просмотр каталога - НЕ запускаем автоматизацию
        has_view_intent = any(trigger in message_lower for trigger in view_triggers)
        if has_view_intent:
            return {"has_intent": False, "reason": "catalog_view_request"}
        
        # Проверяем наличие триггеров заказа
        has_order_intent = any(trigger in message_lower for trigger in order_triggers)
        
        if not has_order_intent:
            return {"has_intent": False}
        
        # Извлекаем параметры из сообщения
        extracted = self._extract_order_parameters(message)
        
        return {
            "has_intent": True,
            "confidence": 0.8 if any(trigger in message_lower for trigger in ['заказать', 'купить']) else 0.6,
            "original_message": message,
            **extracted
        }
    
    def _extract_order_parameters(self, message: str) -> Dict[str, Any]:
        """Извлекает параметры заказа из сообщения"""
        params = {
            "budget": None,
            "product_type": None,
            "postal_code": None,
            "specific_product": None
        }
        
        # Извлекаем бюджет
        budget_patterns = [
            r'за\s+(\d+(?:\s*\d+)*)\s*(?:руб|₽|рублей?)',
            r'(\d+(?:\s*\d+)*)\s*(?:руб|₽|рублей?)',
            r'до\s+(\d+(?:\s*\d+)*)',
            r'в пределах\s+(\d+(?:\s*\d+)*)',
            r'бюджет\s+(\d+(?:\s*\d+)*)'
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, message.lower())
            if match:
                budget_str = match.group(1).replace(' ', '')
                try:
                    params["budget"] = float(budget_str)
                    break
                except ValueError:
                    continue
        
        # Извлекаем тип товара
        product_types = {
            'кольцо': ['кольцо', 'кольца', 'колечко'],
            'браслет': ['браслет', 'браслеты'],
            'серьги': ['серьги', 'сережки', 'серёжки'],
            'бусы': ['бусы', 'бусики'],
            'подвеска': ['подвеска', 'подвески', 'кулон', 'кулоны'],
            'ожерелье': ['ожерелье', 'ожерелья']
        }
        
        message_lower = message.lower()
        for product_type, keywords in product_types.items():
            if any(keyword in message_lower for keyword in keywords):
                params["product_type"] = product_type
                break
        
        # Извлекаем почтовый индекс
        postal_match = re.search(r'\b(\d{6})\b', message)
        if postal_match:
            params["postal_code"] = postal_match.group(1)
        
        return params
    
    async def process_order_scenario(self, user_id: int, intent_data: Dict[str, Any], user_context: Dict = None) -> Dict[str, Any]:
        """
        Обрабатывает полный сценарий заказа
        
        Args:
            user_id: ID пользователя
            intent_data: Данные о намерении заказа
            user_context: Контекст пользователя (имя, телефон и т.д.)
            
        Returns:
            Результат обработки сценария
        """
        try:
            scenario_state = {
                "step": "confirmation",
                "user_id": user_id,
                "intent": intent_data,
                "context": user_context or {},
                "products": [],
                "missing_data": [],
                "total_amount": 0,
                "delivery_info": {},
                "confirmation_message": "",
                "next_action": "await_confirmation"
            }
            
            # Шаг 1: Подтверждение намерения
            confirmation_response = await self._generate_order_confirmation(scenario_state)
            
            return {
                "success": True,
                "scenario_state": scenario_state,
                "response_message": confirmation_response,
                "next_action": "await_confirmation",
                "requires_user_input": True
            }
            
        except Exception as e:
            app_logger.error(f"Ошибка обработки сценария заказа: {e}")
            return {
                "success": False,
                "error": str(e),
                "response_message": "Извините, произошла ошибка при обработке вашего запроса. Попробуйте еще раз."
            }
    
    async def _generate_order_confirmation(self, scenario_state: Dict[str, Any]) -> str:
        """Генерирует сообщение подтверждения намерения заказа"""
        intent = scenario_state["intent"]
        
        # Базовое сообщение подтверждения
        message = "🛍️ Вижу, что вы хотите оформить заказ! "
        
        # Добавляем информацию о том, что уже известно
        known_info = []
        if intent.get("product_type"):
            known_info.append(f"товар: {intent['product_type']}")
        if intent.get("budget"):
            known_info.append(f"бюджет: {int(intent['budget'])}₽")
        if intent.get("postal_code"):
            known_info.append(f"доставка: {intent['postal_code']}")
        
        if known_info:
            message += f"Я понял: {', '.join(known_info)}.\n\n"
        else:
            message += "Давайте подберем для вас идеальное украшение!\n\n"
        
        message += "✅ **Начать оформление заказа?**\n"
        message += "📋 Сначала посмотреть каталог\n"
        message += "❌ Отменить"
        
        return message
    
    async def process_confirmation_response(self, user_id: int, response: str, scenario_state: Dict[str, Any]) -> Dict[str, Any]:
        """Обрабатывает ответ пользователя на подтверждение"""
        response_lower = response.lower()
        
        if any(word in response_lower for word in ['да', 'давайте', 'начать', 'оформить', 'заказ', '✅', 'начинаем']):
            # Пользователь подтвердил - переходим к сбору данных
            return await self._start_data_collection(user_id, scenario_state)
        
        elif any(word in response_lower for word in ['каталог', 'посмотреть', 'показать', '📋']):
            # Пользователь хочет сначала посмотреть каталог
            return await self._show_catalog_for_selection(scenario_state)
        
        elif any(word in response_lower for word in ['нет', 'отменить', 'отмена', '❌']):
            # Пользователь отменил
            return {
                "success": True,
                "scenario_completed": True,
                "response_message": "Хорошо, если захотите что-то заказать - просто напишите! Я всегда готов помочь 😊",
                "next_action": "none"
            }
        
        else:
            # Неопределенный ответ - переспрашиваем
            return {
                "success": True,
                "scenario_state": scenario_state,
                "response_message": "Пожалуйста, выберите один из вариантов:\n✅ Начать оформление заказа\n📋 Сначала посмотреть каталог\n❌ Отменить",
                "next_action": "await_confirmation",
                "requires_user_input": True
            }
    
    async def _show_catalog_for_selection(self, scenario_state: Dict[str, Any]) -> Dict[str, Any]:
        """Показывает каталог товаров для выбора"""
        intent = scenario_state["intent"]
        
        try:
            # Формируем поисковый запрос на основе намерения
            search_query = ""
            if intent.get("product_type"):
                search_query = intent["product_type"]
            else:
                search_query = "все товары"
            
            # Ищем товары через ProductManager
            products = await self.product_manager.search_products(
                query=search_query,
                budget_min=None,
                budget_max=intent.get("budget") if intent.get("budget") else None
            )
            
            if products:
                # Форматируем список товаров
                products_text = self.product_manager.format_products_list(products, max_products=5)
                
                response = f"🛍️ **Товары из нашего каталога:**\n\n{products_text}\n\n"
                response += "💡 **Выберите товар для заказа:**\n"
                response += "• Напишите номер товара (например: \"1\")\n"
                response += "• Или скажите \"заказать [название]\""
                
                # Сохраняем список товаров в контексте для дальнейшего выбора
                scenario_state["available_products"] = products
                
                return {
                    "success": True,
                    "scenario_state": scenario_state,
                    "response_message": response,
                    "next_action": "select_product",
                    "requires_user_input": True
                }
            else:
                return {
                    "success": True,
                    "scenario_completed": True,
                    "response_message": "😔 К сожалению, по вашим критериям товары не найдены. Попробуйте изменить запрос или свяжитесь с менеджером.",
                    "next_action": "none"
                }
                
        except Exception as e:
            app_logger.error(f"Ошибка показа каталога: {e}")
            return {
                "success": True,
                "scenario_completed": True,
                "response_message": "Извините, произошла ошибка при загрузке каталога. Попробуйте позже!",
                "next_action": "none"
            }

    async def _start_data_collection(self, user_id: int, scenario_state: Dict[str, Any]) -> Dict[str, Any]:
        """Начинает сбор необходимых данных для заказа"""
        intent = scenario_state["intent"]
        missing_data = []
        
        # Определяем что нужно уточнить (адаптивная логика)
        if not intent.get("product_type") and not intent.get("specific_product"):
            missing_data.append("product_type")
        
        if not intent.get("budget"):
            missing_data.append("budget")
        
        # Адрес нужен не сразу, запросим после подбора товаров
        
        scenario_state["missing_data"] = missing_data
        scenario_state["step"] = "data_collection"
        
        if missing_data:
            question = await self._generate_data_collection_question(missing_data[0], scenario_state)
            return {
                "success": True,
                "scenario_state": scenario_state,
                "response_message": question,
                "next_action": f"collect_{missing_data[0]}",
                "requires_user_input": True
            }
        else:
            # Все данные есть - сразу подбираем товары
            return await self._search_and_show_products(scenario_state)
    
    async def _generate_data_collection_question(self, data_type: str, scenario_state: Dict[str, Any]) -> str:
        """Генерирует вопрос для сбора данных"""
        if data_type == "product_type":
            return ("🎨 **Какой тип украшений вас интересует?**\n\n"
                   "💍 Кольца\n"
                   "📿 Браслеты\n" 
                   "👂 Серьги\n"
                   "📿 Бусы и ожерелья\n"
                   "🔸 Подвески и кулоны\n\n"
                   "Или просто напишите что ищете!")
        
        elif data_type == "budget":
            return ("💰 **Какой у вас бюджет?**\n\n"
                   "Укажите примерную сумму, которую готовы потратить на украшение.\n"
                   "Например: 'до 5000 рублей' или 'около 10000'")
        
        return "Пожалуйста, уточните детали вашего заказа."
    
    async def _search_and_show_products(self, scenario_state: Dict[str, Any]) -> Dict[str, Any]:
        """Ищет и показывает подходящие товары"""
        intent = scenario_state["intent"]
        
        # Формируем поисковый запрос
        search_query = ""
        if intent.get("product_type"):
            search_query = intent["product_type"]
        
        # Ищем товары
        try:
            products = await self.product_manager.search_products(
                query=search_query,
                budget_max=intent.get("budget"),
                limit=5
            )
            
            if not products:
                return {
                    "success": True,
                    "scenario_state": scenario_state,
                    "response_message": (
                        f"К сожалению, не нашел подходящих товаров по вашим критериям "
                        f"({search_query}, до {intent.get('budget', 'любой')}₽).\n\n"
                        f"Попробуйте изменить параметры поиска или напишите что именно ищете."
                    ),
                    "next_action": "restart_search",
                    "requires_user_input": True
                }
            
            # Показываем найденные товары
            products_message = self._format_products_for_selection(products, intent.get("budget"))
            
            scenario_state["found_products"] = products
            scenario_state["step"] = "product_selection"
            
            return {
                "success": True,
                "scenario_state": scenario_state,
                "response_message": products_message,
                "next_action": "select_product",
                "requires_user_input": True
            }
            
        except Exception as e:
            app_logger.error(f"Ошибка поиска товаров: {e}")
            return {
                "success": False,
                "error": str(e),
                "response_message": "Извините, произошла ошибка при поиске товаров. Попробуйте еще раз."
            }
    
    def _format_products_for_selection(self, products: List[Dict], budget: Optional[float] = None) -> str:
        """Форматирует список товаров для выбора"""
        message = "🎁 **Подобрал для вас украшения:**\n\n"
        
        for i, product in enumerate(products[:3], 1):  # Показываем максимум 3 товара
            name = product.get('name', 'Без названия')
            price = product.get('price', 0)
            description = product.get('description', '')
            
            message += f"**{i}. {name}** — {int(price):,}₽\n"
            if description and len(description) > 5:
                # Берем первые 100 символов описания
                short_desc = description[:100] + "..." if len(description) > 100 else description
                message += f"   _{short_desc}_\n"
            message += "\n"
        
        message += "Выберите номер товара (1, 2, 3) или напишите 'показать еще' для других вариантов."
        
        return message
    
    async def process_product_selection(self, user_id: int, selection: str, scenario_state: Dict[str, Any]) -> Dict[str, Any]:
        """Обрабатывает выбор товара пользователем"""
        selection_lower = selection.lower()
        found_products = scenario_state.get("found_products", [])
        
        # Проверяем выбор по номеру
        if selection_lower in ['1', '2', '3']:
            try:
                index = int(selection_lower) - 1
                if 0 <= index < len(found_products):
                    selected_product = found_products[index]
                    return await self._process_selected_product(user_id, selected_product, scenario_state)
            except (ValueError, IndexError):
                pass
        
        # Проверяем запрос на показ других вариантов
        if any(word in selection_lower for word in ['еще', 'другие', 'больше', 'показать']):
            # TODO: Показать больше товаров
            return {
                "success": True,
                "scenario_state": scenario_state,
                "response_message": "Извините, функция показа дополнительных товаров пока в разработке. Выберите из предложенных вариантов (1, 2, 3).",
                "next_action": "select_product",
                "requires_user_input": True
            }
        
        # Неопределенный выбор
        return {
            "success": True,
            "scenario_state": scenario_state,
            "response_message": "Пожалуйста, выберите номер товара (1, 2 или 3) или напишите 'показать еще'.",
            "next_action": "select_product",
            "requires_user_input": True
        }
    
    async def _process_selected_product(self, user_id: int, product: Dict, scenario_state: Dict[str, Any]) -> Dict[str, Any]:
        """Обрабатывает выбранный товар и переходит к оформлению"""
        scenario_state["selected_product"] = product
        scenario_state["step"] = "order_confirmation"
        
        # Рассчитываем доставку
        product_price = product.get('price', 0)
        delivery_info = self._calculate_delivery(product_price)
        
        scenario_state["delivery_info"] = delivery_info
        scenario_state["total_amount"] = product_price
        
        # Генерируем итоговое подтверждение заказа
        confirmation_message = self._generate_final_confirmation(product, delivery_info)
        
        return {
            "success": True,
            "scenario_state": scenario_state,
            "response_message": confirmation_message,
            "next_action": "final_confirmation",
            "requires_user_input": True
        }
    
    def _calculate_delivery(self, product_price: float) -> Dict[str, Any]:
        """Рассчитывает информацию о доставке"""
        is_free = product_price >= self.free_delivery_threshold
        
        return {
            "is_free": is_free,
            "cost": 0 if is_free else None,  # None означает "по тарифам"
            "description": (
                "бесплатная 🎁" if is_free 
                else "рассчитывается по тарифам и оплачивается отдельно при получении"
            )
        }
    
    def _generate_final_confirmation(self, product: Dict, delivery_info: Dict) -> str:
        """Генерирует итоговое подтверждение заказа"""
        name = product.get('name', 'Товар')
        price = product.get('price', 0)
        
        message = f"🛍️ **Ваш заказ:**\n"
        message += f"• {name} — {int(price):,}₽\n\n"
        
        message += f"📦 Доставка Почтой России — {delivery_info['description']}\n"
        message += f"👤 Получатель: [уточнить имя и телефон]\n\n"
        
        message += "✅ **Подтвердить заказ**\n"
        message += "📝 Указать данные получателя\n" 
        message += "❌ Отменить"
        
        return message
    
    async def process_final_confirmation(self, user_id: int, response: str, scenario_state: Dict[str, Any]) -> Dict[str, Any]:
        """Обрабатывает финальное подтверждение заказа"""
        response_lower = response.lower()
        
        if any(word in response_lower for word in ['подтвердить', 'да', 'заказ', 'оформить', '✅']):
            # Пользователь подтвердил - создаем заказ
            return await self._create_final_order(user_id, scenario_state)
        
        elif any(word in response_lower for word in ['данные', 'получатель', 'указать', '📝']):
            # Запрашиваем данные получателя
            return {
                "success": True,
                "scenario_state": scenario_state,
                "response_message": (
                    "📋 **Укажите данные получателя:**\n\n"
                    "👤 Имя и фамилия\n"
                    "📞 Телефон для связи\n"
                    "📍 Почтовый индекс (6 цифр)\n\n"
                    "Например: Анна Иванова, +7 900 123 45 67, 190000"
                ),
                "next_action": "collect_recipient_data",
                "requires_user_input": True
            }
        
        elif any(word in response_lower for word in ['отменить', 'отмена', 'нет', '❌']):
            # Отмена заказа
            return {
                "success": True,
                "scenario_completed": True,
                "response_message": "Заказ отменен. Если захотите что-то заказать - обращайтесь! 😊",
                "next_action": "none"
            }
        
        else:
            # Неопределенный ответ
            return {
                "success": True,
                "scenario_state": scenario_state,
                "response_message": "Пожалуйста, выберите:\n✅ Подтвердить заказ\n📝 Указать данные получателя\n❌ Отменить",
                "next_action": "final_confirmation",
                "requires_user_input": True
            }
    
    async def _create_final_order(self, user_id: int, scenario_state: Dict[str, Any]) -> Dict[str, Any]:
        """Создает финальный заказ со всеми интеграциями"""
        try:
            selected_product = scenario_state["selected_product"]
            delivery_info = scenario_state["delivery_info"]
            
            # Подготавливаем данные для заказа
            customer_data = {
                "name": scenario_state.get("context", {}).get("name", "Клиент из Telegram"),
                "phone": scenario_state.get("context", {}).get("phone", "+7 900 000 00 00"),
                "email": scenario_state.get("context", {}).get("email"),
                "telegram_id": user_id
            }
            
            products = [{
                "name": selected_product.get("name"),
                "price": selected_product.get("price"),
                "quantity": 1,
                "moysklad_id": selected_product.get("id")
            }]
            
            # Создаем заказ с платежом через ProductManager
            order_result = await self.product_manager.create_order_with_payment(
                customer_data=customer_data,
                products=products,
                telegram_user_id=user_id,
                delivery_info=delivery_info if not delivery_info["is_free"] else None
            )
            
            if order_result.get("success"):
                payment_url = order_result.get("payment_url")
                order_id = order_result.get("order_id")
                
                success_message = (
                    f"🎉 **Заказ успешно оформлен!**\n\n"
                    f"📋 Номер заказа: {order_id}\n"
                    f"💰 К оплате: {int(selected_product.get('price', 0)):,}₽\n\n"
                )
                
                if payment_url:
                    success_message += f"💳 **Ссылка для оплаты:**\n{payment_url}\n\n"
                    success_message += "После оплаты заказ будет автоматически передан в работу! 🚀"
                else:
                    success_message += "⏳ Ссылка для оплаты будет отправлена отдельным сообщением."
                
                return {
                    "success": True,
                    "scenario_completed": True,
                    "order_created": True,
                    "order_id": order_id,
                    "payment_url": payment_url,
                    "response_message": success_message,
                    "next_action": "none"
                }
            else:
                error_msg = order_result.get("error", "Неизвестная ошибка")
                return {
                    "success": False,
                    "error": error_msg,
                    "response_message": f"❌ Ошибка создания заказа: {error_msg}\n\nПопробуйте еще раз или обратитесь к менеджеру."
                }
                
        except Exception as e:
            app_logger.error(f"Ошибка создания финального заказа: {e}")
            return {
                "success": False,
                "error": str(e),
                "response_message": "❌ Произошла техническая ошибка. Попробуйте еще раз или обратитесь к менеджеру."
            }