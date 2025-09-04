"""
Клиент для работы с МойСклад API
"""
import os
import base64
from typing import Dict, List, Optional, Any
import aiohttp
from dotenv import load_dotenv
from utils.logger import app_logger

# Загружаем переменные окружения
load_dotenv()


class MoySkladClient:
    """
    Клиент для работы с МойСклад API
    """
    
    def __init__(self):
        """Инициализация МойСклад клиента"""
        self.token = os.getenv("MOYSKLAD_TOKEN")
        self.login = os.getenv("MOYSKLAD_LOGIN")
        self.password = os.getenv("MOYSKLAD_PASSWORD")
        self.base_url = os.getenv("MOYSKLAD_API_URL", "https://online.moysklad.ru/api/remap/1.2")
        
        # Подготавливаем авторизацию
        if self.token:
            self.auth_header = f"Bearer {self.token}"
        elif self.login and self.password:
            credentials = base64.b64encode(f"{self.login}:{self.password}".encode()).decode()
            self.auth_header = f"Basic {credentials}"
        else:
            raise ValueError("Отсутствуют данные для авторизации в МойСклад")
        
        app_logger.info("МойСклад клиент инициализирован")
    
    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Выполняет HTTP запрос к МойСклад API
        
        Args:
            method: HTTP метод
            endpoint: Endpoint API
            params: Параметры запроса
            data: Данные для отправки
            
        Returns:
            Ответ от API или None при ошибке
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            'Authorization': self.auth_header,
            'Content-Type': 'application/json;charset=utf-8',
            'Accept': 'application/json;charset=utf-8'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, params=params, json=data) as response:
                    if response.status in [200, 201]:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        app_logger.error(f"Ошибка МойСклад API {response.status}: {error_text}")
                        return None
                        
        except Exception as e:
            app_logger.error(f"Ошибка запроса к МойСклад API: {e}")
            return None
    
    async def get_products(self, limit: int = 100, search: Optional[str] = None, 
                          price_min: Optional[float] = None, price_max: Optional[float] = None) -> List[Dict]:
        """
        Получает список товаров из каталога
        
        Args:
            limit: Лимит товаров
            search: Поисковый запрос
            price_min: Минимальная цена
            price_max: Максимальная цена
            
        Returns:
            Список товаров
        """
        params = {
            'limit': limit,
            'expand': 'images,salePrices'
        }
        
        # Добавляем фильтр поиска
        filters = []
        if search:
            filters.append(f"name~{search}")
        # Фильтрацию по цене делаем после получения товаров, так как МойСклад API не поддерживает фильтрацию по salePrices.value
        # if price_min is not None:
        #     filters.append(f"salePrices.value>={int(price_min * 100)}")  # МойСклад хранит цены в копейках
        # if price_max is not None:
        #     filters.append(f"salePrices.value<={int(price_max * 100)}")
            
        if filters:
            params['filter'] = ';'.join(filters)
        
        result = await self._make_request("GET", "entity/product", params)
        
        if result and 'rows' in result:
            products = []
            for row in result['rows']:
                product = await self._parse_product(row)
                if product:
                    products.append(product)
            
            app_logger.info(f"Загружено {len(products)} товаров из МойСклад")
            return products
        
        app_logger.error("Ошибка загрузки товаров из МойСклад")
        return []
    
    async def _parse_product(self, product_data: Dict) -> Optional[Dict]:
        """
        Парсит данные товара из МойСклад API
        
        Args:
            product_data: Данные товара от API
            
        Returns:
            Структурированные данные товара
        """
        try:
            # Извлекаем основные данные
            product_id = product_data.get('id')
            name = product_data.get('name', 'Без названия')
            description = product_data.get('description', '')
            
            # Получаем цену (берем первую цену продажи)
            price = 0
            sale_prices = product_data.get('salePrices', [])
            if sale_prices:
                price = sale_prices[0].get('value', 0) / 100  # Переводим из копеек в рубли
            
            # Получаем остатки (временно ставим 0, так как отдельный запрос для каждого товара неэффективен)
            stock = 0
            
            # Получаем изображения
            images = []
            if 'images' in product_data and product_data['images'].get('rows'):
                for image_data in product_data['images']['rows']:
                    # Используем миниатюру для быстрой загрузки в Telegram
                    if 'miniature' in image_data and 'downloadHref' in image_data['miniature']:
                        images.append(image_data['miniature']['downloadHref'])
                    # Если миниатюры нет, используем оригинал
                    elif 'meta' in image_data and 'downloadHref' in image_data['meta']:
                        images.append(image_data['meta']['downloadHref'])
                    # Резервный вариант - tiny изображение
                    elif 'tiny' in image_data and 'href' in image_data['tiny']:
                        images.append(image_data['tiny']['href'])
            
            # Извлекаем категорию (группу товаров)
            category = "Янтарные изделия"
            if 'productFolder' in product_data:
                folder_data = product_data['productFolder']
                if 'name' in folder_data:
                    category = folder_data['name']
            
            return {
                'id': product_id,
                'name': name,
                'description': description,
                'price': price,
                'category': category,
                'stock': stock,
                'images': images,
                'article': product_data.get('article', ''),
                'weight': product_data.get('weight', 0),
                'volume': product_data.get('volume', 0)
            }
            
        except Exception as e:
            app_logger.error(f"Ошибка парсинга товара {product_data.get('id', 'unknown')}: {e}")
            return None
    
    async def _get_product_stock(self, product_id: str) -> int:
        """
        Получает остатки товара по ID
        
        Args:
            product_id: ID товара
            
        Returns:
            Количество на складе
        """
        try:
            result = await self._make_request("GET", f"report/stock/all", {
                'filter': f'product=entity/product/{product_id}'
            })
            
            if result and 'rows' in result and result['rows']:
                return result['rows'][0].get('stock', 0)
                
        except Exception as e:
            app_logger.error(f"Ошибка получения остатков для товара {product_id}: {e}")
        
        return 0
    
    async def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """
        Получает информацию о товаре по ID
        
        Args:
            product_id: ID товара
            
        Returns:
            Данные товара
        """
        result = await self._make_request("GET", f"entity/product/{product_id}", {
            'expand': 'images,salePrices'
        })
        
        if result:
            return await self._parse_product(result)
        
        return None
    
    async def search_products_by_category(self, category: str, limit: int = 50) -> List[Dict]:
        """
        Ищет товары по категории/типу
        
        Args:
            category: Категория товаров (кольца, серьги, браслеты и т.д.)
            limit: Лимит результатов
            
        Returns:
            Список товаров
        """
        # Маппинг категорий для поиска
        category_keywords = {
            'кольца': ['кольцо', 'перстень'],
            'серьги': ['серьги', 'сережки'],
            'браслеты': ['браслет'],
            'кулоны': ['кулон', 'подвеска', 'подвески'],
            'бусы': ['бусы', 'ожерелье', 'колье'],
            'брошки': ['брошь', 'брошка'],
            'комплекты': ['комплект', 'набор']
        }
        
        keywords = category_keywords.get(category.lower(), [category])
        
        all_products = []
        for keyword in keywords:
            products = await self.get_products(limit=limit//len(keywords) + 1, search=keyword)
            all_products.extend(products)
        
        # Удаляем дубликаты по ID
        seen_ids = set()
        unique_products = []
        for product in all_products:
            if product['id'] not in seen_ids:
                seen_ids.add(product['id'])
                unique_products.append(product)
        
        return unique_products[:limit]
    
    async def create_customer_order(self, customer_data: Dict, products: List[Dict], 
                                   telegram_user_id: int) -> Optional[str]:
        """
        Создает заказ покупателя в МойСклад
        
        Args:
            customer_data: Данные покупателя (имя, телефон, адрес)
            products: Список товаров с количеством
            telegram_user_id: ID пользователя Telegram
            
        Returns:
            ID созданного заказа или None
        """
        try:
            # Создаем или находим контрагента
            counterparty_id = await self._get_or_create_counterparty(customer_data, telegram_user_id)
            
            if not counterparty_id:
                app_logger.error("Не удалось создать контрагента для заказа")
                return None
            
            # Формируем позиции заказа
            positions = []
            total_sum = 0
            
            for item in products:
                product_id = item.get('product_id')
                quantity = item.get('quantity', 1)
                
                # Получаем актуальную информацию о товаре
                product_info = await self.get_product_by_id(product_id)
                if not product_info:
                    continue
                
                price = product_info['price'] * 100  # Переводим в копейки
                position_sum = price * quantity
                
                positions.append({
                    "quantity": quantity,
                    "price": price,
                    "assortment": {
                        "meta": {
                            "href": f"{self.base_url}/entity/product/{product_id}",
                            "type": "product"
                        }
                    }
                })
                
                total_sum += position_sum
            
            if not positions:
                app_logger.error("Нет валидных позиций для создания заказа")
                return None
            
            # Создаем заказ
            order_data = {
                "name": f"Заказ Telegram {telegram_user_id}",
                "description": f"Заказ от пользователя Telegram ID: {telegram_user_id}",
                "agent": {
                    "meta": {
                        "href": f"{self.base_url}/entity/counterparty/{counterparty_id}",
                        "type": "counterparty"
                    }
                },
                "positions": positions,
                "sum": total_sum
            }
            
            result = await self._make_request("POST", "entity/customerorder", data=order_data)
            
            if result and 'id' in result:
                order_id = result['id']
                app_logger.info(f"Создан заказ МойСклад ID: {order_id} для пользователя {telegram_user_id}")
                return order_id
            else:
                app_logger.error("Ошибка создания заказа в МойСклад")
                return None
                
        except Exception as e:
            app_logger.error(f"Ошибка создания заказа в МойСклад: {e}")
            return None
    
    async def _get_or_create_counterparty(self, customer_data: Dict, telegram_user_id: int) -> Optional[str]:
        """
        Получает или создает контрагента в МойСклад
        
        Args:
            customer_data: Данные покупателя
            telegram_user_id: ID пользователя Telegram
            
        Returns:
            ID контрагента или None
        """
        try:
            # Пытаемся найти существующего контрагента по Telegram ID
            search_result = await self._make_request("GET", "entity/counterparty", {
                'filter': f'description~Telegram ID: {telegram_user_id}',
                'limit': 1
            })
            
            if search_result and search_result.get('rows'):
                counterparty_id = search_result['rows'][0]['id']
                app_logger.info(f"Найден существующий контрагент {counterparty_id}")
                return counterparty_id
            
            # Создаем нового контрагента
            counterparty_data = {
                "name": customer_data.get('name', f'Клиент Telegram {telegram_user_id}'),
                "description": f"Telegram ID: {telegram_user_id}",
                "companyType": "individual"  # Физическое лицо
            }
            
            # Добавляем контактную информацию если есть
            if customer_data.get('phone'):
                counterparty_data["phone"] = customer_data['phone']
            if customer_data.get('email'):
                counterparty_data["email"] = customer_data['email']
            if customer_data.get('address'):
                counterparty_data["actualAddress"] = customer_data['address']
            
            result = await self._make_request("POST", "entity/counterparty", data=counterparty_data)
            
            if result and 'id' in result:
                counterparty_id = result['id']
                app_logger.info(f"Создан контрагент МойСклад ID: {counterparty_id}")
                return counterparty_id
            else:
                app_logger.error("Ошибка создания контрагента в МойСклад")
                return None
                
        except Exception as e:
            app_logger.error(f"Ошибка работы с контрагентом в МойСклад: {e}")
            return None
    
    async def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Получает статус заказа
        
        Args:
            order_id: ID заказа
            
        Returns:
            Данные о статусе заказа
        """
        result = await self._make_request("GET", f"entity/customerorder/{order_id}")
        
        if result:
            return {
                'id': result.get('id'),
                'name': result.get('name'),
                'sum': result.get('sum', 0) / 100,  # Переводим в рубли
                'state': result.get('state', {}).get('name', 'Новый'),
                'created': result.get('created'),
                'updated': result.get('updated')
            }
        
        return None
    
    async def get_product_categories(self) -> List[Dict]:
        """
        Получает список категорий товаров (папок)
        
        Returns:
            Список категорий
        """
        result = await self._make_request("GET", "entity/productfolder")
        
        categories = []
        if result and 'rows' in result:
            for row in result['rows']:
                categories.append({
                    'id': row.get('id'),
                    'name': row.get('name'),
                    'description': row.get('description', '')
                })
        
        return categories
    
    async def get_customer_order_by_id(self, order_id: str) -> Optional[Dict]:
        """
        Получает заказ клиента по ID
        
        Args:
            order_id: ID заказа в МойСклад
            
        Returns:
            Данные заказа или None
        """
        try:
            result = await self._make_request("GET", f"entity/customerorder/{order_id}")
            return result
        except Exception as e:
            app_logger.error(f"Ошибка получения заказа {order_id}: {e}")
            return None
    
    async def process_payment_webhook(self, moysklad_order_id: str, payment_amount: float, payment_id: str, telegram_user_id: int = None) -> Dict:
        """
        Обрабатывает webhook о платеже: обновляет заказ + создает входящий платеж
        
        Args:
            moysklad_order_id: ID заказа в МойСклад (из metadata платежа)
            payment_amount: Сумма платежа в рублях
            payment_id: ID платежа в ЮKassa
            telegram_user_id: ID пользователя Telegram для уведомления
            
        Returns:
            Результат обработки
        """
        try:
            # Шаг 1: Находим заказ в МойСклад
            order = await self.get_customer_order_by_id(moysklad_order_id)
            if not order:
                app_logger.error(f"Заказ {moysklad_order_id} не найден в МойСклад")
                return {"success": False, "error": "Заказ не найден"}
            
            # Шаг 2: Обновляем заказ - устанавливаем payedSum и статус
            from datetime import datetime
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            
            # Сумма в копейках для МойСклад
            payment_amount_kopecks = int(payment_amount * 100)
            
            update_data = {
                'payedSum': payment_amount_kopecks,
                'description': f"{order.get('description', '')}\n💳 Оплачен через ЮKassa ({timestamp})\n🆔 Платеж: {payment_id}"
            }
            
            # Обновляем заказ
            updated_order = await self._make_request(
                "PUT",
                f"entity/customerorder/{moysklad_order_id}",
                data=update_data
            )
            
            if not updated_order:
                return {"success": False, "error": "Ошибка обновления заказа"}
            
            # Шаг 3: Создаем входящий платеж (customerPayment)
            payment_result = await self.create_customer_payment(
                order_id=moysklad_order_id,
                amount=payment_amount,
                description=f"Оплата заказа {order.get('name', '')} через ЮKassa",
                yukassa_payment_id=payment_id
            )
            
            app_logger.info(f"✅ Обработан платеж {payment_id}: заказ {moysklad_order_id} на {payment_amount}₽")
            
            return {
                "success": True,
                "order_id": moysklad_order_id,
                "payment_amount": payment_amount,
                "payment_id": payment_id,
                "order_updated": True,
                "customer_payment_created": payment_result.get("success", False),
                "customer_payment_id": payment_result.get("payment_id"),
                "telegram_user_id": telegram_user_id,
                "message": f"Оплата получена, заказ {order.get('name', '')} готов к отправке"
            }
                
        except Exception as e:
            app_logger.error(f"Ошибка обработки webhook платежа {payment_id}: {e}")
            return {"success": False, "error": f"Техническая ошибка: {e}"}
    
    async def create_customer_payment(self, order_id: str, amount: float, description: str, yukassa_payment_id: str) -> Dict:
        """
        Создает входящий платеж (customerPayment) в МойСклад
        
        Args:
            order_id: ID заказа
            amount: Сумма в рублях
            description: Описание платежа
            yukassa_payment_id: ID платежа в ЮKassa
            
        Returns:
            Результат создания платежа
        """
        try:
            # Получаем заказ для связи
            order = await self.get_customer_order_by_id(order_id)
            if not order:
                return {"success": False, "error": "Заказ не найден"}
            
            # Подготавливаем данные платежа
            payment_amount_kopecks = int(amount * 100)  # МойСклад работает в копейках
            
            payment_data = {
                "organization": {"meta": order.get("organization", {}).get("meta")},
                "agent": order.get("agent", {}),
                "sum": payment_amount_kopecks,
                "description": description,
                "operations": [
                    {
                        "meta": order.get("meta"),
                        "linkedSum": payment_amount_kopecks
                    }
                ]
            }
            
            # Добавляем референс на ЮKassa платеж в описание
            payment_data["description"] += f" (ЮKassa ID: {yukassa_payment_id})"
            
            # Создаем платеж
            result = await self._make_request(
                "POST",
                "entity/paymentin",
                data=payment_data
            )
            
            if result:
                payment_id = result.get("id")
                app_logger.info(f"✅ Создан входящий платеж {payment_id} для заказа {order_id}")
                return {
                    "success": True,
                    "payment_id": payment_id,
                    "amount": amount
                }
            else:
                app_logger.error(f"❌ Ошибка создания платежа для заказа {order_id}")
                return {"success": False, "error": "Ошибка создания платежа"}
                
        except Exception as e:
            app_logger.error(f"Исключение при создании платежа для заказа {order_id}: {e}")
            return {"success": False, "error": f"Техническая ошибка: {e}"}
    
    async def add_order_note(self, order_id: str, note: str) -> bool:
        """
        Добавляет примечание к заказу
        
        Args:
            order_id: ID заказа
            note: Текст примечания
            
        Returns:
            True если успешно добавлено
        """
        try:
            # Получаем текущий заказ
            order = await self.get_customer_order_by_id(order_id)
            if not order:
                return False
            
            # Добавляем примечание к описанию
            current_description = order.get('description', '')
            from datetime import datetime
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            new_note = f"[{timestamp}] {note}"
            
            if current_description:
                new_description = f"{current_description}\n{new_note}"
            else:
                new_description = new_note
            
            # Обновляем заказ
            result = await self._make_request(
                "PUT",
                f"entity/customerorder/{order_id}",
                data={"description": new_description}
            )
            
            return result is not None
            
        except Exception as e:
            app_logger.error(f"Ошибка добавления примечания к заказу {order_id}: {e}")
            return False