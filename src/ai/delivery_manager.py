"""
Delivery Manager - управление правилами доставки
Обрабатывает логику бесплатной доставки от 15,000₽ и тарифы Почты России
"""
from typing import Dict, List, Optional, Any, Union
from utils.logger import app_logger


class DeliveryManager:
    """
    Управляет правилами доставки и расчетом стоимости
    
    Правила:
    - Бесплатная доставка при заказе ≥ 15,000₽
    - Для остальных - по тарифам Почты России
    - Поддержка разных регионов России
    - Расчет примерных сроков доставки
    """
    
    def __init__(self):
        """Инициализация менеджера доставки"""
        self.free_delivery_threshold = 15000  # Порог бесплатной доставки в рублях
        self.base_regions = self._build_regions_data()
        self.delivery_methods = self._build_delivery_methods()
        
        app_logger.info("DeliveryManager инициализирован")
    
    def _build_regions_data(self) -> Dict[str, Dict]:
        """Создает данные о регионах и тарифах"""
        return {
            "moscow": {
                "name": "Москва",
                "zone": 1,
                "base_cost": 200,
                "delivery_days": "1-2",
                "keywords": ["москва", "московская область", "мск"]
            },
            "spb": {
                "name": "Санкт-Петербург", 
                "zone": 1,
                "base_cost": 220,
                "delivery_days": "1-3",
                "keywords": ["санкт-петербург", "спб", "питер", "ленинградская область"]
            },
            "center": {
                "name": "Центральный регион",
                "zone": 2,
                "base_cost": 280,
                "delivery_days": "2-4",
                "keywords": ["воронеж", "тула", "калуга", "рязань", "тамбов", "липецк"]
            },
            "volga": {
                "name": "Поволжье",
                "zone": 2,
                "base_cost": 300,
                "delivery_days": "3-5", 
                "keywords": ["казань", "нижний новгород", "самара", "саратов", "волгоград", "уфа"]
            },
            "ural": {
                "name": "Урал",
                "zone": 3,
                "base_cost": 350,
                "delivery_days": "4-6",
                "keywords": ["екатеринбург", "челябинск", "пермь", "тюмень"]
            },
            "siberia": {
                "name": "Сибирь",
                "zone": 3,
                "base_cost": 400,
                "delivery_days": "5-8",
                "keywords": ["новосибирск", "омск", "красноярск", "томск", "барнаул"]
            },
            "far_east": {
                "name": "Дальний Восток",
                "zone": 4,
                "base_cost": 500,
                "delivery_days": "7-12",
                "keywords": ["владивосток", "хабаровск", "благовещенск", "южно-сахалинск"]
            },
            "other": {
                "name": "Другие регионы",
                "zone": 3,
                "base_cost": 380,
                "delivery_days": "4-7",
                "keywords": []
            }
        }
    
    def _build_delivery_methods(self) -> Dict[str, Dict]:
        """Создает методы доставки"""
        return {
            "russian_post": {
                "name": "Почта России",
                "description": "Стандартная доставка по тарифам Почты России",
                "is_default": True
            },
            "courier": {
                "name": "Курьерская доставка", 
                "description": "Доставка курьером (только крупные города)",
                "is_default": False,
                "extra_cost": 200,
                "available_regions": ["moscow", "spb"]
            }
        }
    
    def calculate_delivery_cost(self, order_total: float, city: Optional[str] = None, 
                               postcode: Optional[str] = None) -> Dict[str, Any]:
        """
        Рассчитывает стоимость доставки
        
        Args:
            order_total: Общая стоимость заказа
            city: Город доставки
            postcode: Почтовый индекс
            
        Returns:
            Dict с информацией о доставке
        """
        # Проверяем бесплатную доставку
        if order_total >= self.free_delivery_threshold:
            return {
                "is_free": True,
                "cost": 0,
                "reason": f"Бесплатная доставка при заказе от {self.free_delivery_threshold:,}₽",
                "delivery_days": "1-3",
                "methods": ["russian_post"]
            }
        
        # Определяем регион
        region_data = self._detect_region(city, postcode)
        
        # Рассчитываем стоимость
        base_cost = region_data["base_cost"]
        
        return {
            "is_free": False,
            "cost": base_cost,
            "region": region_data["name"],
            "delivery_days": region_data["delivery_days"],
            "methods": ["russian_post"],
            "description": "По тарифам Почты России"
        }
    
    def _detect_region(self, city: Optional[str] = None, 
                      postcode: Optional[str] = None) -> Dict[str, Any]:
        """Определяет регион доставки"""
        if city:
            city_lower = city.lower().strip()
            
            # Ищем по ключевым словам
            for region_code, region_data in self.base_regions.items():
                for keyword in region_data["keywords"]:
                    if keyword in city_lower:
                        return region_data
        
        # Определяем по почтовому индексу
        if postcode and len(postcode) == 6:
            first_digit = int(postcode[0])
            
            # Москва и область: 1xxxxx
            if first_digit == 1:
                return self.base_regions["moscow"]
            # СПб и область: 2xxxxx  
            elif first_digit == 2:
                return self.base_regions["spb"]
            # Центральные регионы: 3xxxxx, 4xxxxx
            elif first_digit in [3, 4]:
                return self.base_regions["center"]
            # Поволжье: 4xxxxx, 5xxxxx
            elif first_digit in [4, 5]:
                return self.base_regions["volga"]
            # Урал: 6xxxxx
            elif first_digit == 6:
                return self.base_regions["ural"]
            # Сибирь: 6xxxxx, 7xxxxx
            elif first_digit in [6, 7]:
                return self.base_regions["siberia"]
            # Дальний Восток: 6xxxxx, 7xxxxx
            elif first_digit in [6, 7]:
                return self.base_regions["far_east"]
        
        # По умолчанию - другие регионы
        return self.base_regions["other"]
    
    def get_delivery_info_text(self, order_total: float, city: Optional[str] = None,
                              postcode: Optional[str] = None) -> str:
        """
        Формирует текстовое описание условий доставки
        
        Args:
            order_total: Стоимость заказа
            city: Город
            postcode: Индекс
            
        Returns:
            Готовый текст для отправки клиенту
        """
        delivery_info = self.calculate_delivery_cost(order_total, city, postcode)
        
        if delivery_info["is_free"]:
            return f"""🚚 **Доставка бесплатно!**

✅ {delivery_info['reason']}
📅 Срок доставки: {delivery_info['delivery_days']} дня
📦 Способ: Почта России"""
        
        else:
            region_text = f" ({delivery_info['region']})" if delivery_info.get('region') else ""
            
            return f"""🚚 **Условия доставки**{region_text}

💰 Стоимость: {delivery_info['cost']}₽
📅 Срок доставки: {delivery_info['delivery_days']} дней
📦 Способ: {delivery_info['description']}

💡 *Доставка станет бесплатной при заказе от {self.free_delivery_threshold:,}₽*"""
    
    def check_free_delivery_eligibility(self, order_total: float) -> Dict[str, Any]:
        """Проверяет право на бесплатную доставку"""
        if order_total >= self.free_delivery_threshold:
            return {
                "eligible": True,
                "current_total": order_total,
                "threshold": self.free_delivery_threshold,
                "savings": 0  # Экономия уже получена
            }
        else:
            needed_amount = self.free_delivery_threshold - order_total
            estimated_savings = 300  # Средняя экономия
            
            return {
                "eligible": False,
                "current_total": order_total,
                "threshold": self.free_delivery_threshold,
                "needed_amount": needed_amount,
                "estimated_savings": estimated_savings
            }
    
    def get_free_delivery_upsell_text(self, order_total: float) -> Optional[str]:
        """
        Формирует текст для стимулирования увеличения заказа до бесплатной доставки
        
        Args:
            order_total: Текущая сумма заказа
            
        Returns:
            Текст предложения или None если не нужен
        """
        eligibility = self.check_free_delivery_eligibility(order_total)
        
        if eligibility["eligible"]:
            return None
        
        needed = eligibility["needed_amount"]
        savings = eligibility["estimated_savings"]
        
        # Предлагаем только если нужно добавить не более 5000₽
        if needed <= 5000:
            return f"""💡 **Совет по экономии**

До бесплатной доставки осталось всего {needed:,}₽!
Экономия составит около {savings}₽ 

Может быть, добавите что-то еще из каталога? 🛍️"""
        
        return None
    
    def validate_delivery_address(self, city: Optional[str] = None, 
                                 postcode: Optional[str] = None,
                                 address: Optional[str] = None) -> Dict[str, Any]:
        """Валидирует адрес доставки"""
        issues = []
        
        # Проверяем почтовый индекс
        if postcode:
            if len(postcode) != 6 or not postcode.isdigit():
                issues.append("Некорректный формат почтового индекса (должно быть 6 цифр)")
            elif postcode.startswith('0'):
                issues.append("Почтовые индексы в России не начинаются с 0")
        
        # Проверяем город
        if city and len(city.strip()) < 2:
            issues.append("Слишком короткое название города")
        
        # Проверяем адрес
        if address and len(address.strip()) < 10:
            issues.append("Адрес слишком короткий - укажите улицу, дом и квартиру")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "suggestions": self._get_address_suggestions(city, postcode)
        }
    
    def _get_address_suggestions(self, city: Optional[str], 
                                postcode: Optional[str]) -> List[str]:
        """Генерирует подсказки по адресу"""
        suggestions = []
        
        if not city and not postcode:
            suggestions.append("Укажите город или почтовый индекс для расчета доставки")
        
        if city and not postcode:
            suggestions.append("Для точного расчета укажите почтовый индекс")
        
        if postcode and not city:
            suggestions.append("Подтвердите город доставки")
        
        return suggestions
    
    def get_delivery_methods_for_region(self, region_code: str) -> List[Dict[str, Any]]:
        """Возвращает доступные способы доставки для региона"""
        available_methods = []
        
        # Почта России доступна везде
        russian_post = self.delivery_methods["russian_post"].copy()
        available_methods.append(russian_post)
        
        # Курьерская доставка только в крупных городах
        courier = self.delivery_methods["courier"]
        if region_code in courier.get("available_regions", []):
            courier_info = courier.copy()
            available_methods.append(courier_info)
        
        return available_methods
    
    def estimate_delivery_date_range(self, region_data: Dict[str, Any]) -> str:
        """Оценивает диапазон дат доставки"""
        from datetime import datetime, timedelta
        
        delivery_days = region_data["delivery_days"]
        
        # Парсим диапазон дней (например "3-5")
        if "-" in delivery_days:
            min_days, max_days = map(int, delivery_days.split("-"))
        else:
            min_days = max_days = int(delivery_days)
        
        today = datetime.now()
        min_date = today + timedelta(days=min_days)
        max_date = today + timedelta(days=max_days)
        
        # Форматируем даты
        min_str = min_date.strftime("%d.%m")
        max_str = max_date.strftime("%d.%m")
        
        if min_str == max_str:
            return min_str
        else:
            return f"{min_str} - {max_str}"
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику менеджера доставки"""
        return {
            "free_delivery_threshold": self.free_delivery_threshold,
            "total_regions": len(self.base_regions),
            "delivery_methods": len(self.delivery_methods),
            "supported_zones": list(set(r["zone"] for r in self.base_regions.values()))
        }