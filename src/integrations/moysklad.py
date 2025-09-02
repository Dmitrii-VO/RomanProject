"""
Интеграция с МойСклад API для управления товарами и заказами
"""
import os
import requests
from typing import List, Dict, Optional
from utils.logger import app_logger


class MoySkladClient:
    """
    Клиент для работы с МойСклад API
    """
    
    def __init__(self):
        """Инициализация клиента МойСклад"""
        self.base_url = os.getenv("MOYSKLAD_BASE_URL")
        self.token = os.getenv("MOYSKLAD_TOKEN")
        self.login = os.getenv("MOYSKLAD_LOGIN")
        self.password = os.getenv("MOYSKLAD_PASSWORD")
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        app_logger.info("МойСклад клиент инициализирован")
    
    async def get_products(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """
        Получение списка товаров
        
        Args:
            limit: Количество товаров
            offset: Смещение
            
        Returns:
            Список товаров
        """
        try:
            url = f"{self.base_url}/entity/product"
            params = {"limit": limit, "offset": offset}
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            products = response.json().get("rows", [])
            app_logger.info(f"Получено {len(products)} товаров из МойСклад")
            
            return products
            
        except Exception as e:
            app_logger.error(f"Ошибка получения товаров из МойСклад: {e}")
            return []
    
    async def search_products(self, query: str) -> List[Dict]:
        """
        Поиск товаров по запросу
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Найденные товары
        """
        try:
            url = f"{self.base_url}/entity/product"
            params = {"search": query}
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            products = response.json().get("rows", [])
            app_logger.info(f"Найдено {len(products)} товаров по запросу: {query}")
            
            return products
            
        except Exception as e:
            app_logger.error(f"Ошибка поиска товаров в МойСклад: {e}")
            return []
    
    async def get_product_stock(self, product_id: str) -> Optional[int]:
        """
        Получение остатка товара
        
        Args:
            product_id: ID товара
            
        Returns:
            Остаток товара или None
        """
        try:
            url = f"{self.base_url}/report/stock/byproduct"
            params = {"product.id": product_id}
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            stock_data = response.json().get("rows", [])
            if stock_data:
                stock = stock_data[0].get("stock", 0)
                app_logger.info(f"Остаток товара {product_id}: {stock}")
                return stock
            
            return 0
            
        except Exception as e:
            app_logger.error(f"Ошибка получения остатка товара: {e}")
            return None
    
    async def create_order(self, customer_info: Dict, items: List[Dict]) -> Optional[str]:
        """
        Создание заказа в МойСклад
        
        Args:
            customer_info: Информация о клиенте
            items: Товары в заказе
            
        Returns:
            ID созданного заказа или None
        """
        try:
            url = f"{self.base_url}/entity/customerorder"
            
            order_data = {
                "name": f"Заказ от {customer_info.get('name', 'Клиент')}",
                "description": f"Заказ из Telegram от {customer_info.get('telegram_id')}",
                "positions": []
            }
            
            # Добавляем товары в заказ
            for item in items:
                position = {
                    "quantity": item.get("quantity", 1),
                    "price": item.get("price", 0),
                    "assortment": {
                        "meta": {
                            "href": item.get("product_href"),
                            "type": "product"
                        }
                    }
                }
                order_data["positions"].append(position)
            
            response = requests.post(url, headers=self.headers, json=order_data)
            response.raise_for_status()
            
            order = response.json()
            order_id = order.get("id")
            
            app_logger.info(f"Создан заказ в МойСклад: {order_id}")
            return order_id
            
        except Exception as e:
            app_logger.error(f"Ошибка создания заказа в МойСклад: {e}")
            return None