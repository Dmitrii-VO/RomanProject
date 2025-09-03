"""
Клиент для работы с API Почты России
"""
import os
import aiohttp
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from utils.logger import app_logger


class RussianPostClient:
    """
    Клиент для интеграции с API Почты России
    
    Функциональность:
    - Расчет стоимости доставки по индексу
    - Определение сроков доставки
    - Трекинг отправлений (будущая функция)
    """
    
    def __init__(self):
        """Инициализация клиента Почты России"""
        # API настройки (заглушки для будущей интеграции)
        self.api_key = os.getenv("RUSSIAN_POST_API_KEY", "placeholder_key")
        self.login = os.getenv("RUSSIAN_POST_LOGIN", "placeholder_login")
        self.password = os.getenv("RUSSIAN_POST_PASSWORD", "placeholder_password")
        self.base_url = "https://otpravka-api.pochta.ru"
        
        # Настройки по умолчанию для отправлений
        self.default_from_postcode = "344002"  # Ростов-на-Дону (пример)
        self.default_weight = 50  # Средний вес украшения в граммах
        self.default_dimensions = {"length": 10, "width": 8, "height": 3}  # см
        
        app_logger.info("RussianPostClient инициализирован (заглушка)")
    
    async def calculate_delivery_cost(
        self, 
        to_postcode: str,
        weight: int = None,
        dimensions: Dict = None,
        declared_value: float = None
    ) -> Dict:
        """
        Рассчитывает стоимость доставки по почтовому индексу
        
        Args:
            to_postcode: Индекс получателя
            weight: Вес отправления в граммах
            dimensions: Габариты {"length": x, "width": y, "height": z}
            declared_value: Объявленная ценность
            
        Returns:
            Словарь с информацией о доставке
        """
        try:
            # Проверяем корректность индекса (базовая валидация)
            if not self._is_valid_postcode(to_postcode):
                return {
                    "success": False,
                    "error": "Некорректный почтовый индекс",
                    "cost": 0,
                    "delivery_time": 0
                }
            
            # TODO: Здесь будет реальный API вызов к Почте России
            # Пока возвращаем заглушку с примерными расценками
            
            # Используем значения по умолчанию если не переданы
            weight = weight or self.default_weight
            dimensions = dimensions or self.default_dimensions
            declared_value = declared_value or 1000
            
            # Заглушка: примерный расчет на основе региона
            mock_delivery_info = self._calculate_mock_delivery(
                to_postcode, weight, declared_value
            )
            
            app_logger.info(f"Рассчитана доставка до {to_postcode}: {mock_delivery_info['cost']}₽")
            
            return mock_delivery_info
            
        except Exception as e:
            app_logger.error(f"Ошибка расчета доставки: {e}")
            return {
                "success": False,
                "error": f"Ошибка расчета доставки: {e}",
                "cost": 0,
                "delivery_time": 0
            }
    
    def _is_valid_postcode(self, postcode: str) -> bool:
        """
        Проверяет корректность российского почтового индекса
        
        Args:
            postcode: Почтовый индекс
            
        Returns:
            True если индекс корректный
        """
        # Российский индекс: 6 цифр
        if not postcode or not isinstance(postcode, str):
            return False
        
        # Убираем пробелы и проверяем длину
        postcode = postcode.strip()
        if len(postcode) != 6:
            return False
        
        # Проверяем что все символы - цифры
        if not postcode.isdigit():
            return False
        
        # Первая цифра не может быть 0
        if postcode[0] == '0':
            return False
            
        return True
    
    def _calculate_mock_delivery(
        self, 
        to_postcode: str, 
        weight: int, 
        declared_value: float
    ) -> Dict:
        """
        Заглушка для расчета доставки (имитация реального API)
        
        Args:
            to_postcode: Индекс получателя
            weight: Вес в граммах
            declared_value: Объявленная ценность
            
        Returns:
            Информация о доставке
        """
        # Определяем регион по первым цифрам индекса
        region_code = to_postcode[:3]
        
        # Базовые тарифы по регионам (примерные)
        regional_tariffs = {
            # Москва и область
            "101": {"base_cost": 200, "days": 2},
            "102": {"base_cost": 200, "days": 2},
            "103": {"base_cost": 200, "days": 2},
            "141": {"base_cost": 250, "days": 3},
            
            # Санкт-Петербург и область  
            "190": {"base_cost": 250, "days": 3},
            "191": {"base_cost": 250, "days": 3},
            "196": {"base_cost": 250, "days": 3},
            
            # Ростов-на-Дону (наш регион)
            "344": {"base_cost": 150, "days": 1},
            
            # Краснодар
            "350": {"base_cost": 200, "days": 2},
            
            # Екатеринбург
            "620": {"base_cost": 350, "days": 5},
            
            # Новосибирск
            "630": {"base_cost": 400, "days": 6},
            
            # Владивосток
            "690": {"base_cost": 500, "days": 8}
        }
        
        # Получаем тариф для региона или используем средний
        tariff = regional_tariffs.get(region_code, {"base_cost": 300, "days": 4})
        
        # Расчет стоимости
        base_cost = tariff["base_cost"]
        
        # Надбавка за вес (если больше 50г)
        if weight > 50:
            weight_surcharge = ((weight - 50) // 20 + 1) * 30
            base_cost += weight_surcharge
        
        # Страховка от объявленной ценности
        insurance_cost = max(20, declared_value * 0.01)  # минимум 20₽ или 1% от стоимости
        
        total_cost = int(base_cost + insurance_cost)
        delivery_days = tariff["days"]
        
        # Расчет ориентировочной даты доставки
        delivery_date = datetime.now() + timedelta(days=delivery_days)
        
        return {
            "success": True,
            "cost": total_cost,
            "delivery_time": delivery_days,
            "delivery_date": delivery_date.strftime("%d.%m.%Y"),
            "service_name": "Почта России - Посылка 1 класса",
            "details": {
                "base_cost": base_cost,
                "insurance_cost": int(insurance_cost),
                "weight": weight,
                "region": self._get_region_name(region_code)
            }
        }
    
    def _get_region_name(self, region_code: str) -> str:
        """
        Возвращает название региона по коду
        
        Args:
            region_code: Первые 3 цифры индекса
            
        Returns:
            Название региона
        """
        region_names = {
            "101": "Москва",
            "102": "Москва", 
            "103": "Москва",
            "141": "Московская область",
            "190": "Санкт-Петербург",
            "191": "Санкт-Петербург",
            "196": "Санкт-Петербург",
            "344": "Ростовская область",
            "350": "Краснодарский край",
            "620": "Свердловская область",
            "630": "Новосибирская область", 
            "690": "Приморский край"
        }
        
        return region_names.get(region_code, "Другой регион")
    
    async def get_delivery_options(self, to_postcode: str, declared_value: float = 1000) -> List[Dict]:
        """
        Получает варианты доставки (будущая функция)
        
        Args:
            to_postcode: Индекс получателя
            declared_value: Объявленная ценность
            
        Returns:
            Список вариантов доставки
        """
        # TODO: Реализовать получение различных вариантов доставки
        # (обычная почта, EMS, курьер и т.д.)
        
        standard_delivery = await self.calculate_delivery_cost(to_postcode, declared_value=declared_value)
        
        if not standard_delivery["success"]:
            return []
        
        # Заглушка: создаем несколько вариантов
        options = [
            {
                "type": "standard",
                "name": "Посылка 1 класса",
                "cost": standard_delivery["cost"],
                "delivery_time": standard_delivery["delivery_time"],
                "delivery_date": standard_delivery["delivery_date"]
            },
            {
                "type": "ems",
                "name": "EMS Почта России", 
                "cost": int(standard_delivery["cost"] * 1.8),
                "delivery_time": max(1, standard_delivery["delivery_time"] - 2),
                "delivery_date": (datetime.now() + timedelta(days=max(1, standard_delivery["delivery_time"] - 2))).strftime("%d.%m.%Y")
            }
        ]
        
        return options
    
    async def track_shipment(self, track_number: str) -> Dict:
        """
        Отслеживание отправления (будущая функция)
        
        Args:
            track_number: Номер для отслеживания
            
        Returns:
            Информация о статусе отправления
        """
        # TODO: Реализовать трекинг через API Почты России
        
        return {
            "success": False,
            "error": "Функция отслеживания будет реализована позже",
            "track_number": track_number,
            "status": "unknown"
        }
    
    def format_delivery_info(self, delivery_info: Dict) -> str:
        """
        Форматирует информацию о доставке для показа клиенту
        
        Args:
            delivery_info: Информация о доставке
            
        Returns:
            Отформатированная строка
        """
        if not delivery_info.get("success"):
            return f"❌ {delivery_info.get('error', 'Ошибка расчета доставки')}"
        
        cost = delivery_info["cost"]
        days = delivery_info["delivery_time"] 
        date = delivery_info["delivery_date"]
        service = delivery_info["service_name"]
        region = delivery_info.get("details", {}).get("region", "")
        
        # Склонение слова "день"
        if days == 1:
            days_text = "1 день"
        elif 2 <= days <= 4:
            days_text = f"{days} дня"
        else:
            days_text = f"{days} дней"
        
        return f"""📦 **Доставка {service}**
🌍 Регион: {region}
💰 Стоимость: **{cost} ₽**
⏰ Срок: **{days_text}** (до {date})
✅ Включена страховка и отслеживание"""