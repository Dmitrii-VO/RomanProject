"""
Менеджер каталога товаров с интеграцией МойСклад
"""
import asyncio
from typing import Dict, List, Optional, Any
from src.integrations.moysklad_client import MoySkladClient
from src.search.embeddings_manager import EmbeddingsManager
from src.delivery.russian_post_client import RussianPostClient
from src.payments.yukassa_client import YuKassaClient
from utils.logger import app_logger


class ProductManager:
    """
    Управляет каталогом товаров и поиском
    """
    
    def __init__(self):
        """Инициализация менеджера товаров"""
        self.moysklad = MoySkladClient()
        self.embeddings_manager = EmbeddingsManager()
        self.delivery_client = RussianPostClient()
        self.payment_client = YuKassaClient()
        self._catalog_cache = {}  # Кэш каталога
        self._cache_timestamp = None
        self._cache_ttl = 3600  # TTL кэша в секундах (1 час)
        
        app_logger.info("ProductManager инициализирован")
    
    async def search_products(self, query: str, budget_min: Optional[float] = None, 
                            budget_max: Optional[float] = None, category: Optional[str] = None) -> List[Dict]:
        """
        Поиск товаров по параметрам
        
        Args:
            query: Поисковый запрос
            budget_min: Минимальный бюджет
            budget_max: Максимальный бюджет
            category: Категория товаров
            
        Returns:
            Список подходящих товаров
        """
        try:
            # Если указана категория, ищем по категории
            if category:
                products = await self.moysklad.search_products_by_category(category, limit=20)
            else:
                # Иначе поиск по общему запросу
                products = await self.moysklad.get_products(limit=50, search=query, 
                                                          price_min=budget_min, price_max=budget_max)
            
            # Дополнительная фильтрация по бюджету если нужно
            if budget_min is not None or budget_max is not None:
                filtered_products = []
                for product in products:
                    price = product.get('price', 0)
                    if budget_min is not None and price < budget_min:
                        continue
                    if budget_max is not None and price > budget_max:
                        continue
                    filtered_products.append(product)
                products = filtered_products
            
            # Сортируем по наличию и цене
            products.sort(key=lambda p: (-p.get('stock', 0), p.get('price', 0)))
            
            app_logger.info(f"Найдено {len(products)} товаров по запросу: {query}")
            return products
            
        except Exception as e:
            app_logger.error(f"Ошибка поиска товаров: {e}")
            return []
    
    async def get_product_recommendations(self, budget: float, category: str) -> List[Dict]:
        """
        Получает рекомендации товаров по бюджету и категории
        
        Args:
            budget: Бюджет пользователя
            category: Категория товаров
            
        Returns:
            Список рекомендованных товаров
        """
        # Расширяем диапазон бюджета на ±20% для лучших рекомендаций
        budget_min = budget * 0.8
        budget_max = budget * 1.2
        
        products = await self.search_products("", budget_min, budget_max, category)
        
        # Отбираем топ-5 товаров
        recommendations = products[:5]
        
        app_logger.info(f"Сформированы рекомендации: {len(recommendations)} товаров для категории {category} и бюджета {budget}")
        
        return recommendations
    
    def format_product_for_chat(self, product: Dict) -> str:
        """
        Форматирует информацию о товаре для отправки в чат
        
        Args:
            product: Данные товара
            
        Returns:
            Отформатированное сообщение
        """
        name = product.get('name', 'Без названия')
        price = product.get('price', 0)
        stock = product.get('stock', 0)
        description = product.get('description', '')
        
        # Формируем сообщение
        message = f"💎 **{name}**\n"
        message += f"💰 Цена: {price:,.0f} ₽\n"
        
        # Показываем наличие
        if stock > 0:
            message += f"✅ В наличии: {stock} шт.\n"
        else:
            message += f"❌ Нет в наличии\n"
        
        # Добавляем описание если есть
        if description:
            message += f"📝 {description[:200]}\n"
        
        # Добавляем артикул если есть
        if product.get('article'):
            message += f"🏷️ Артикул: {product['article']}\n"
        
        return message
    
    def format_products_list(self, products: List[Dict], max_products: int = 5) -> str:
        """
        Форматирует список товаров для отправки в чат
        
        Args:
            products: Список товаров
            max_products: Максимальное количество товаров в списке
            
        Returns:
            Отформатированное сообщение со списком товаров
        """
        if not products:
            return "😔 К сожалению, товары по вашим критериям не найдены.\n\nПопробуйте:\n• Увеличить бюджет\n• Изменить категорию\n• Уточнить запрос"
        
        # Берем только нужное количество товаров
        display_products = products[:max_products]
        
        message = f"🛍️ **Найдено {len(products)} товаров, показываю лучшие {len(display_products)}:**\n\n"
        
        for i, product in enumerate(display_products, 1):
            message += f"**{i}. {product.get('name', 'Без названия')}**\n"
            
            # Добавляем фотографию если есть
            images = product.get('images', [])
            if images:
                # Берем первую фотографию
                first_image = images[0]
                message += f"🖼️ {first_image}\n"
            
            message += f"   💰 {product.get('price', 0):,.0f} ₽"
            
            # Показываем статус наличия
            stock = product.get('stock', 0)
            if stock > 0:
                message += f" | ✅ В наличии ({stock} шт.)\n"
            else:
                message += f" | ❌ Нет в наличии\n"
            
            # Краткое описание
            description = product.get('description', '')
            if description:
                short_desc = description[:100] + ("..." if len(description) > 100 else "")
                message += f"   📝 {short_desc}\n"
            
            # Артикул если есть
            if product.get('article'):
                message += f"   🏷️ Артикул: {product['article']}\n"
            
            message += "\n"
        
        if len(products) > max_products:
            message += f"... и еще {len(products) - max_products} товаров\n\n"
        
        message += "💡 Хотите узнать больше о каком-то товаре? Напишите его номер!"
        
        return message
    
    async def get_product_details(self, product_id: str) -> Optional[Dict]:
        """
        Получает детальную информацию о товаре
        
        Args:
            product_id: ID товара
            
        Returns:
            Подробная информация о товаре
        """
        return await self.moysklad.get_product_by_id(product_id)
    
    async def create_order(self, customer_data: Dict, products: List[Dict], telegram_user_id: int) -> Optional[str]:
        """
        Создает заказ в МойСклад
        
        Args:
            customer_data: Данные клиента
            products: Список товаров с количеством
            telegram_user_id: ID пользователя Telegram
            
        Returns:
            ID созданного заказа
        """
        try:
            order_id = await self.moysklad.create_customer_order(customer_data, products, telegram_user_id)
            
            if order_id:
                app_logger.info(f"Создан заказ {order_id} для пользователя {telegram_user_id}")
                return order_id
            else:
                app_logger.error(f"Ошибка создания заказа для пользователя {telegram_user_id}")
                return None
                
        except Exception as e:
            app_logger.error(f"Ошибка создания заказа: {e}")
            return None
    
    def parse_budget_from_text(self, text: str) -> Optional[float]:
        """
        Извлекает бюджет из текста пользователя
        
        Args:
            text: Текст сообщения
            
        Returns:
            Извлеченный бюджет или None
        """
        import re
        
        # Ищем числа с возможными обозначениями валюты
        patterns = [
            r'(\d+(?:\s?\d{3})*)\s*(?:руб|₽|рублей|р\.?)',  # 5000 руб, 5 000 ₽
            r'(\d+)\s*(?:тысяч|тыс\.?)',  # 5 тысяч, 10 тыс
            r'до\s*(\d+(?:\s?\d{3})*)',  # до 5000
            r'(\d+(?:\s?\d{3})*)\s*рублей',  # 5000 рублей
            r'бюджет\s*(\d+(?:\s?\d{3})*)',  # бюджет 5000
        ]
        
        text_lower = text.lower()
        
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                # Берем последнее найденное значение (наиболее релевантное)
                budget_str = matches[-1].replace(' ', '')
                try:
                    budget = float(budget_str)
                    
                    # Если упомянуты тысячи, умножаем
                    if 'тысяч' in text_lower or 'тыс' in text_lower:
                        budget *= 1000
                    
                    return budget
                except ValueError:
                    continue
        
        return None
    
    def extract_category_from_text(self, text: str) -> Optional[str]:
        """
        Определяет категорию товара из текста
        
        Args:
            text: Текст сообщения
            
        Returns:
            Определенная категория или None
        """
        text_lower = text.lower()
        
        # Маппинг ключевых слов на категории
        category_mapping = {
            'кольца': ['кольцо', 'кольца', 'перстень', 'перстни'],
            'серьги': ['серьги', 'сережки', 'серёжки'],
            'браслеты': ['браслет', 'браслеты'],
            'кулоны': ['кулон', 'кулоны', 'подвеска', 'подвески', 'кулончик'],
            'бусы': ['бусы', 'ожерелье', 'колье', 'бусики'],
            'брошки': ['брошь', 'брошка', 'брошки'],
            'комплекты': ['комплект', 'комплекты', 'набор']
        }
        
        for category, keywords in category_mapping.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
        
        return None
    
    async def semantic_search(self, query: str, limit: int = 10, threshold: float = 0.5) -> List[Dict]:
        """
        Выполняет семантический поиск товаров
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            threshold: Минимальный порог сходства
            
        Returns:
            Список похожих товаров
        """
        try:
            # Выполняем семантический поиск
            results = await self.embeddings_manager.semantic_search(query, limit, threshold)
            
            if not results:
                return []
            
            # Конвертируем результаты в формат ProductManager
            products = []
            for result in results:
                product = {
                    'id': result['id'],
                    'name': result['name'],
                    'description': result.get('description', ''),
                    'category': result.get('category', ''),
                    'price': result.get('price', 0),
                    'stock': 0,  # Пока остатки не загружаем
                    'images': [],
                    'article': '',
                    'weight': 0,
                    'volume': 0,
                    'similarity_score': result['similarity_score']  # Дополнительное поле
                }
                products.append(product)
            
            app_logger.info(f"Семантический поиск '{query}': найдено {len(products)} товаров")
            return products
            
        except Exception as e:
            app_logger.error(f"Ошибка семантического поиска: {e}")
            return []
    
    def _calculate_semantic_threshold(self, query: str, category: Optional[str] = None, 
                                    has_budget: bool = False) -> float:
        """
        Вычисляет оптимальный порог сходства для семантического поиска
        
        Args:
            query: Поисковый запрос
            category: Категория товаров
            has_budget: Есть ли ограничение по бюджету
            
        Returns:
            Оптимальный порог сходства
        """
        # Базовый порог для общих запросов
        threshold = 0.4
        
        # Повышаем порог если есть конкретная категория
        if category:
            threshold = 0.5
        
        # Повышаем порог если есть и категория и бюджет (самый конкретный запрос)
        if category and has_budget:
            threshold = 0.6
        
        # Дополнительно повышаем порог для очень специфичных запросов
        specific_words = ['размер', 'цвет', 'стиль', 'модель', 'коллекция', 'дизайн']
        if any(word in query.lower() for word in specific_words):
            threshold += 0.1
        
        # Максимальный порог 0.8
        threshold = min(threshold, 0.8)
        
        app_logger.debug(f"Рассчитанный порог сходства: {threshold} для запроса '{query}', категория={category}, бюджет={has_budget}")
        
        return threshold
    
    async def smart_search(self, query: str, budget_min: Optional[float] = None, 
                          budget_max: Optional[float] = None, category: Optional[str] = None) -> List[Dict]:
        """
        Умный поиск: сначала традиционный, затем семантический как fallback
        
        Args:
            query: Поисковый запрос
            budget_min: Минимальный бюджет
            budget_max: Максимальный бюджет  
            category: Категория товаров
            
        Returns:
            Список найденных товаров
        """
        try:
            # Сначала пробуем обычный поиск
            traditional_results = await self.search_products(query, budget_min, budget_max, category)
            
            # Если найдено достаточно результатов, возвращаем их
            if len(traditional_results) >= 3:
                app_logger.info(f"Традиционный поиск дал {len(traditional_results)} результатов")
                return traditional_results
            
            # Иначе пробуем семантический поиск
            app_logger.info("Недостаточно результатов от традиционного поиска, пробуем семантический")
            
            # Формируем запрос для семантического поиска
            semantic_query = query
            if category:
                semantic_query = f"{category} {query}" if query else category
            
            # Рассчитываем оптимальный порог сходства
            has_budget = budget_min is not None or budget_max is not None
            threshold = self._calculate_semantic_threshold(semantic_query, category, has_budget)
            
            semantic_results = await self.semantic_search(semantic_query, limit=10, threshold=threshold)
            
            # Фильтруем по бюджету если указан
            if budget_min is not None or budget_max is not None:
                filtered_results = []
                for product in semantic_results:
                    price = product.get('price', 0)
                    if budget_min is not None and price < budget_min:
                        continue
                    if budget_max is not None and price > budget_max:
                        continue
                    filtered_results.append(product)
                semantic_results = filtered_results
            
            # Объединяем результаты (традиционные сначала, потом семантические)
            combined_results = traditional_results + semantic_results
            
            # Удаляем дубликаты по ID
            seen_ids = set()
            unique_results = []
            for product in combined_results:
                if product['id'] not in seen_ids:
                    seen_ids.add(product['id'])
                    unique_results.append(product)
            
            app_logger.info(f"Умный поиск: {len(traditional_results)} традиционных + {len(semantic_results)} семантических = {len(unique_results)} уникальных (порог: {threshold})")
            
            return unique_results[:10]  # Ограничиваем до 10 результатов
            
        except Exception as e:
            app_logger.error(f"Ошибка умного поиска: {e}")
            # В случае ошибки возвращаем хотя бы традиционные результаты
            return await self.search_products(query, budget_min, budget_max, category)
    
    async def auto_update_embeddings_for_new_products(self, products: List[Dict]) -> int:
        """
        Автоматически добавляет эмбеддинги для новых товаров
        
        Args:
            products: Список товаров
            
        Returns:
            Количество добавленных эмбеддингов
        """
        try:
            # Получаем ID товаров с существующими эмбеддингами
            existing_ids = self.embeddings_manager.get_existing_product_ids()
            
            # Фильтруем только новые товары
            new_products = [product for product in products if product['id'] not in existing_ids]
            
            if not new_products:
                return 0
            
            app_logger.info(f"Найдено {len(new_products)} новых товаров для добавления эмбеддингов")
            
            # Добавляем эмбеддинги для новых товаров
            success_count = await self.embeddings_manager.batch_add_products(new_products)
            
            app_logger.info(f"Автоматически добавлено {success_count} эмбеддингов для новых товаров")
            return success_count
            
        except Exception as e:
            app_logger.error(f"Ошибка автоматического обновления эмбеддингов: {e}")
            return 0
    
    async def get_categories_summary(self) -> str:
        """
        Получает сводку по доступным категориям товаров
        
        Returns:
            Форматированная информация о категориях
        """
        try:
            categories = await self.moysklad.get_product_categories()
            
            if not categories:
                return "📂 Категории товаров:\n• Кольца\n• Серьги\n• Браслеты\n• Кулоны\n• Бусы\n• Брошки"
            
            message = "📂 **Доступные категории:**\n\n"
            for category in categories:
                name = category.get('name', 'Без названия')
                description = category.get('description', '')
                message += f"• **{name}**"
                if description:
                    message += f" - {description}"
                message += "\n"
            
            return message
            
        except Exception as e:
            app_logger.error(f"Ошибка получения категорий: {e}")
            return "📂 Основные категории: кольца, серьги, браслеты, кулоны, бусы, брошки"
    
    async def calculate_delivery_cost(self, to_postcode: str, products: List[Dict] = None) -> Dict:
        """
        Рассчитывает стоимость доставки для товаров
        
        Args:
            to_postcode: Почтовый индекс получателя
            products: Список товаров для расчета веса и стоимости
            
        Returns:
            Информация о доставке
        """
        try:
            # Рассчитываем общие параметры заказа
            total_weight = self._calculate_total_weight(products) if products else None
            total_value = self._calculate_total_value(products) if products else None
            
            # Получаем расчет доставки через Почту России
            delivery_info = await self.delivery_client.calculate_delivery_cost(
                to_postcode=to_postcode,
                weight=total_weight,
                declared_value=total_value
            )
            
            app_logger.info(f"Рассчитана доставка до {to_postcode}: {delivery_info}")
            return delivery_info
            
        except Exception as e:
            app_logger.error(f"Ошибка расчета доставки: {e}")
            return {
                "success": False,
                "error": f"Ошибка расчета доставки: {e}",
                "cost": 0,
                "delivery_time": 0
            }
    
    async def get_delivery_options(self, to_postcode: str, products: List[Dict] = None) -> List[Dict]:
        """
        Получает различные варианты доставки
        
        Args:
            to_postcode: Почтовый индекс получателя
            products: Список товаров
            
        Returns:
            Список вариантов доставки
        """
        try:
            total_value = self._calculate_total_value(products) if products else 1000
            options = await self.delivery_client.get_delivery_options(to_postcode, total_value)
            
            app_logger.info(f"Получено {len(options)} вариантов доставки до {to_postcode}")
            return options
            
        except Exception as e:
            app_logger.error(f"Ошибка получения вариантов доставки: {e}")
            return []
    
    def _calculate_total_weight(self, products: List[Dict]) -> int:
        """
        Рассчитывает общий вес товаров в граммах
        
        Args:
            products: Список товаров
            
        Returns:
            Общий вес в граммах
        """
        if not products:
            return 50  # Средний вес украшения по умолчанию
        
        # Для янтарных украшений используем примерные веса по категориям
        category_weights = {
            'кольца': 15,
            'серьги': 25,
            'браслеты': 40,
            'кулоны': 20,
            'подвески': 15,
            'бусы': 80,
            'ожерелья': 100,
            'брошки': 30
        }
        
        total_weight = 0
        for product in products:
            category = product.get('category', '').lower()
            # Ищем подходящую категорию
            weight = 30  # Вес по умолчанию
            for cat_name, cat_weight in category_weights.items():
                if cat_name in category:
                    weight = cat_weight
                    break
            
            quantity = product.get('quantity', 1)
            total_weight += weight * quantity
        
        # Добавляем упаковку (примерно 20г на заказ + 5г на каждый товар)
        packaging_weight = 20 + len(products) * 5
        
        return total_weight + packaging_weight
    
    def _calculate_total_value(self, products: List[Dict]) -> float:
        """
        Рассчитывает общую стоимость товаров
        
        Args:
            products: Список товаров
            
        Returns:
            Общая стоимость
        """
        if not products:
            return 1000  # Средняя стоимость по умолчанию
        
        total_value = 0
        for product in products:
            price = product.get('price', 0)
            quantity = product.get('quantity', 1)
            total_value += price * quantity
        
        return total_value
    
    def parse_postcode_from_text(self, text: str) -> Optional[str]:
        """
        Извлекает почтовый индекс из текста
        
        Args:
            text: Текст сообщения
            
        Returns:
            Найденный индекс или None
        """
        import re
        
        # Ищем российские почтовые индексы (6 цифр, не начинающиеся с 0)
        postcode_pattern = r'\b[1-9]\d{5}\b'
        matches = re.findall(postcode_pattern, text)
        
        if matches:
            # Возвращаем первый найденный индекс
            postcode = matches[0]
            app_logger.info(f"Найден индекс в тексте: {postcode}")
            return postcode
        
        return None
    
    def format_delivery_info_with_products(self, delivery_info: Dict, products: List[Dict] = None) -> str:
        """
        Форматирует информацию о доставке с учетом товаров
        
        Args:
            delivery_info: Информация о доставке
            products: Список товаров (опционально)
            
        Returns:
            Отформатированная строка
        """
        if not delivery_info.get("success"):
            return f"❌ {delivery_info.get('error', 'Ошибка расчета доставки')}"
        
        # Основная информация о доставке
        delivery_text = self.delivery_client.format_delivery_info(delivery_info)
        
        # Добавляем информацию о товарах если есть
        if products:
            total_weight = self._calculate_total_weight(products)
            total_value = self._calculate_total_value(products)
            items_count = len(products)
            
            delivery_text += f"""

📦 **Детали отправления:**
• Товаров: {items_count} шт.
• Общий вес: {total_weight}г (включая упаковку)
• Стоимость товаров: {total_value:,.0f} ₽
• Страхование включено в стоимость доставки"""
        
        return delivery_text
    
    async def create_order_with_payment(
        self, 
        customer_data: Dict, 
        products: List[Dict], 
        telegram_user_id: int,
        delivery_info: Optional[Dict] = None
    ) -> Dict:
        """
        Создает заказ и счет для оплаты
        
        Args:
            customer_data: Данные клиента
            products: Список товаров с количеством
            telegram_user_id: ID пользователя Telegram
            delivery_info: Информация о доставке (опционально)
            
        Returns:
            Результат создания заказа и платежа
        """
        try:
            # Рассчитываем общую стоимость
            total_price = self._calculate_total_value(products)
            delivery_cost = delivery_info.get('cost', 0) if delivery_info else 0
            final_amount = total_price + delivery_cost
            
            # Создаем заказ в МойСклад
            order_id = await self.create_order(customer_data, products, telegram_user_id)
            
            if not order_id:
                return {
                    "success": False,
                    "error": "Не удалось создать заказ"
                }
            
            # Подготавливаем данные для платежа
            items_for_payment = self._prepare_payment_items(products, delivery_info)
            
            description = f"Заказ №{order_id} - {len(products)} товар(ов)"
            if delivery_info:
                description += f" с доставкой"
            
            # Создаем платеж в ЮKassa
            payment_result = await self.payment_client.create_payment(
                amount=final_amount,
                order_id=order_id,
                description=description,
                customer_email=customer_data.get('email'),
                customer_phone=customer_data.get('phone'),
                items=items_for_payment,
                moysklad_order_id=order_id,  # Передаем ID заказа из МойСклад
                telegram_user_id=telegram_user_id  # Для последующих уведомлений
            )
            
            if not payment_result.get("success"):
                app_logger.error(f"Не удалось создать платеж для заказа {order_id}")
                return {
                    "success": False,
                    "error": payment_result.get("error", "Ошибка создания платежа"),
                    "order_id": order_id
                }
            
            app_logger.info(f"Создан заказ {order_id} с платежом {payment_result['payment_id']}")
            
            return {
                "success": True,
                "order_id": order_id,
                "payment_id": payment_result["payment_id"],
                "payment_url": payment_result["payment_url"],
                "total_amount": final_amount,
                "products_amount": total_price,
                "delivery_amount": delivery_cost,
                "description": description
            }
            
        except Exception as e:
            app_logger.error(f"Ошибка создания заказа с оплатой: {e}")
            return {
                "success": False,
                "error": f"Техническая ошибка: {e}"
            }
    
    def _prepare_payment_items(self, products: List[Dict], delivery_info: Optional[Dict] = None) -> List[Dict]:
        """
        Подготавливает товары для отправки в ЮKassa (54-ФЗ)
        
        Args:
            products: Список товаров
            delivery_info: Информация о доставке
            
        Returns:
            Список товаров для чека
        """
        items = []
        
        # Добавляем товары
        for product in products:
            item = {
                "name": product.get("name", "Товар"),
                "quantity": product.get("quantity", 1),
                "price": product.get("price", 0)
            }
            items.append(item)
        
        # Добавляем доставку как отдельную позицию
        if delivery_info and delivery_info.get("cost", 0) > 0:
            delivery_item = {
                "name": f"Доставка - {delivery_info.get('service_name', 'Почта России')}",
                "quantity": 1,
                "price": delivery_info["cost"]
            }
            items.append(delivery_item)
        
        return items
    
    async def get_payment_status(self, payment_id: str) -> Dict:
        """
        Получает статус платежа
        
        Args:
            payment_id: ID платежа в ЮKassa
            
        Returns:
            Информация о статусе платежа
        """
        try:
            status_info = await self.payment_client.get_payment_status(payment_id)
            app_logger.info(f"Получен статус платежа {payment_id}: {status_info.get('status')}")
            return status_info
        except Exception as e:
            app_logger.error(f"Ошибка получения статуса платежа: {e}")
            return {"success": False, "error": f"Техническая ошибка: {e}"}
    
    def format_payment_info(self, order_data: Dict) -> str:
        """
        Форматирует информацию о заказе и оплате для клиента
        
        Args:
            order_data: Данные заказа с платежом
            
        Returns:
            Отформатированное сообщение
        """
        if not order_data.get("success"):
            return f"❌ Ошибка создания заказа: {order_data.get('error', 'Неизвестная ошибка')}"
        
        order_id = order_data["order_id"]
        total_amount = order_data["total_amount"]
        products_amount = order_data["products_amount"]
        delivery_amount = order_data.get("delivery_amount", 0)
        payment_url = order_data["payment_url"]
        
        message = f"🛒 **Заказ №{order_id} создан успешно!**\n\n"
        message += f"📦 Товары: {products_amount:,.0f} ₽\n"
        
        if delivery_amount > 0:
            message += f"🚚 Доставка: {delivery_amount:,.0f} ₽\n"
        
        message += f"💰 **Итого к оплате: {total_amount:,.0f} ₽**\n\n"
        
        message += f"💳 **Ссылка для оплаты:**\n{payment_url}\n\n"
        
        message += "✅ **Способы оплаты:**\n"
        message += "• Банковская карта\n"
        message += "• СБП (Система быстрых платежей)\n"  
        message += "• Электронные кошельки\n\n"
        
        message += "⏰ Счет действителен 24 часа\n"
        message += "🔒 Оплата защищена ЮKassa"
        
        return message