"""
Entity Extractor для извлечения сущностей из сообщений пользователя
Извлекает слоты: категория, бюджет, стиль, товар, контактные данные и т.д.
"""
import re
from typing import Dict, List, Optional, Any, Union
from utils.logger import app_logger


class EntityExtractor:
    """
    Извлекает сущности (слоты) из сообщений пользователей
    
    Поддерживаемые слоты:
    - category: категория товара (кольца, серьги, браслеты и т.д.)
    - budget: бюджет пользователя
    - style: стиль украшения (нежный, яркий, классика)
    - product_id: ID конкретного товара
    - postcode: почтовый индекс
    - city: город
    - name: имя клиента
    - phone: номер телефона
    - quantity: количество товара
    """
    
    def __init__(self):
        """Инициализация экстрактора сущностей"""
        self.category_patterns = self._build_category_patterns()
        self.style_patterns = self._build_style_patterns()
        app_logger.info("EntityExtractor инициализирован")
    
    def _build_category_patterns(self) -> Dict[str, List[str]]:
        """Создает паттерны для категорий товаров"""
        return {
            "кольца": [
                "кольцо", "кольца", "перстень", "перстни", 
                "кольцах", "колечко", "колечки"
            ],
            "серьги": [
                "серьги", "сережки", "серёжки", "серьга", 
                "сережка", "гвоздики", "висячие", "длинные серьги"
            ],
            "браслеты": [
                "браслет", "браслеты", "браслеты", "браслетик",
                "браслетики", "на руку", "на запястье"
            ],
            "кулоны": [
                "кулон", "кулоны", "подвеска", "подвески", "кулончик",
                "на шею", "на цепочке", "кулончики"
            ],
            "бусы": [
                "бусы", "ожерелье", "колье", "бусики", "нитка бус",
                "ожерелья", "бусины", "жемчуг"
            ],
            "брошки": [
                "брошь", "брошка", "брошки", "брошечка", 
                "булавка", "заколка", "значок"
            ]
        }
    
    def _build_style_patterns(self) -> Dict[str, List[str]]:
        """Создает паттерны для стилей украшений"""
        return {
            "нежный": [
                "нежный", "нежное", "нежные", "деликатный", "тонкий",
                "изящный", "утонченный", "романтичный", "женственный",
                "легкий", "воздушный", "минималистичный"
            ],
            "яркий": [
                "яркий", "яркое", "яркие", "броский", "заметный",
                "выразительный", "насыщенный", "контрастный",
                "эффектный", "впечатляющий", "привлекающий внимание"
            ],
            "классика": [
                "классический", "классическое", "классические", "традиционный",
                "консервативный", "строгий", "элегантный", "деловой",
                "офисный", "формальный", "сдержанный"
            ],
            "современный": [
                "современный", "модный", "стильный", "трендовый",
                "актуальный", "дизайнерский", "авангардный", "необычный",
                "оригинальный", "креативный", "инновационный"
            ]
        }
    
    def extract_entities(self, message: str) -> Dict[str, Any]:
        """
        Извлекает все сущности из сообщения
        
        Args:
            message: Текст сообщения пользователя
            
        Returns:
            Dict со всеми найденными сущностями
        """
        if not message or not message.strip():
            return {}
        
        entities = {}
        message_lower = message.lower().strip()
        
        # Извлекаем категорию товара
        category = self.extract_category(message_lower)
        if category:
            entities['category'] = category
        
        # Извлекаем бюджет
        budget = self.extract_budget(message)
        if budget:
            entities['budget'] = budget
        
        # Извлекаем стиль
        style = self.extract_style(message_lower)
        if style:
            entities['style'] = style
        
        # Извлекаем контактные данные
        phone = self.extract_phone(message)
        if phone:
            entities['phone'] = phone
            
        # Извлекаем имя
        name = self.extract_name(message)
        if name:
            entities['name'] = name
        
        # Извлекаем почтовый индекс
        postcode = self.extract_postcode(message)
        if postcode:
            entities['postcode'] = postcode
            
        # Извлекаем город
        city = self.extract_city(message)
        if city:
            entities['city'] = city
        
        # Извлекаем количество
        quantity = self.extract_quantity(message)
        if quantity:
            entities['quantity'] = quantity
        
        # Извлекаем ID товара
        product_id = self.extract_product_id(message)
        if product_id:
            entities['product_id'] = product_id
        
        if entities:
            app_logger.debug(f"Extracted entities: {entities}")
        
        return entities
    
    def extract_category(self, message: str) -> Optional[str]:
        """Извлекает категорию товара из сообщения"""
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if pattern in message:
                    return category
        return None
    
    def extract_budget(self, message: str) -> Optional[Dict[str, Union[float, str]]]:
        """Извлекает информацию о бюджете"""
        patterns = [
            # Точные суммы
            r'(\d+(?:\s?\d{3})*)\s*(?:руб|₽|рублей|р\.?)',
            r'(\d+)\s*(?:тысяч|тыс\.?)',
            # Диапазоны
            r'от\s*(\d+(?:\s?\d{3})*)\s*до\s*(\d+(?:\s?\d{3})*)',
            r'(\d+(?:\s?\d{3})*)\s*[-—]\s*(\d+(?:\s?\d{3})*)',
            # До суммы
            r'до\s*(\d+(?:\s?\d{3})*)',
            r'не\s*более\s*(\d+(?:\s?\d{3})*)',
            r'максимум\s*(\d+(?:\s?\d{3})*)',
            # От суммы
            r'от\s*(\d+(?:\s?\d{3})*)',
            r'не\s*менее\s*(\d+(?:\s?\d{3})*)',
            r'минимум\s*(\d+(?:\s?\d{3})*)',
        ]
        
        message_lower = message.lower()
        
        for pattern in patterns:
            matches = re.findall(pattern, message_lower)
            if matches:
                try:
                    if len(matches[0]) == 2 and isinstance(matches[0], tuple):
                        # Диапазон
                        min_val = float(matches[0][0].replace(' ', ''))
                        max_val = float(matches[0][1].replace(' ', ''))
                        
                        # Обработка тысяч
                        if 'тысяч' in message_lower or 'тыс' in message_lower:
                            min_val *= 1000
                            max_val *= 1000
                        
                        return {
                            "type": "range",
                            "min": min_val,
                            "max": max_val
                        }
                    else:
                        # Одно значение
                        if isinstance(matches[0], tuple):
                            value_str = matches[0][0]
                        else:
                            value_str = matches[0]
                            
                        value = float(value_str.replace(' ', ''))
                        
                        # Обработка тысяч
                        if 'тысяч' in message_lower or 'тыс' in message_lower:
                            value *= 1000
                        
                        # Определяем тип ограничения
                        if 'до' in message_lower or 'максимум' in message_lower or 'не более' in message_lower:
                            return {"type": "max", "value": value}
                        elif 'от' in message_lower or 'минимум' in message_lower or 'не менее' in message_lower:
                            return {"type": "min", "value": value}
                        else:
                            return {"type": "exact", "value": value}
                            
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def extract_style(self, message: str) -> Optional[str]:
        """Извлекает стиль украшения"""
        for style, patterns in self.style_patterns.items():
            for pattern in patterns:
                if pattern in message:
                    return style
        return None
    
    def extract_phone(self, message: str) -> Optional[str]:
        """Извлекает номер телефона"""
        patterns = [
            r'\+7\s*\(?\d{3}\)?\s*\d{3}[\-\s]*\d{2}[\-\s]*\d{2}',
            r'8\s*\(?\d{3}\)?\s*\d{3}[\-\s]*\d{2}[\-\s]*\d{2}',
            r'7\s*\(?\d{3}\)?\s*\d{3}[\-\s]*\d{2}[\-\s]*\d{2}',
            r'\d{11}',  # 11 цифр подряд
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                phone = re.sub(r'[^\d+]', '', match.group())
                # Нормализуем к формату +7XXXXXXXXXX
                if phone.startswith('8') and len(phone) == 11:
                    phone = '+7' + phone[1:]
                elif phone.startswith('7') and len(phone) == 11:
                    phone = '+' + phone
                elif len(phone) == 11 and not phone.startswith('+'):
                    phone = '+7' + phone[1:]
                return phone
        
        return None
    
    def extract_name(self, message: str) -> Optional[str]:
        """Извлекает имя из сообщения"""
        patterns = [
            r'меня зовут\s+([А-ЯЁа-яё]+)',
            r'я\s+([А-ЯЁа-яё]+)',
            r'имя\s+([А-ЯЁа-яё]+)',
            r'звать\s+([А-ЯЁа-яё]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip().title()
                if len(name) > 1:  # Минимум 2 символа
                    return name
        
        return None
    
    def extract_postcode(self, message: str) -> Optional[str]:
        """Извлекает почтовый индекс"""
        # Российские индексы - 6 цифр, не начинающиеся с 0
        pattern = r'\b[1-9]\d{5}\b'
        match = re.search(pattern, message)
        if match:
            return match.group()
        return None
    
    def extract_city(self, message: str) -> Optional[str]:
        """Извлекает город из сообщения"""
        patterns = [
            r'город\s+([А-ЯЁа-яё\-]+)',
            r'в\s+([А-ЯЁа-яё\-]+е?)\b',
            r'из\s+([А-ЯЁа-яё\-]+[аы]?)\b',
        ]
        
        # Список крупных городов для лучшего распознавания
        cities = [
            'москва', 'санкт-петербург', 'новосибирск', 'екатеринбург',
            'казань', 'нижний новгород', 'челябинск', 'самара', 'омск',
            'ростов-на-дону', 'уфа', 'красноярск', 'пермь', 'воронеж'
        ]
        
        message_lower = message.lower()
        
        # Ищем упоминания известных городов
        for city in cities:
            if city in message_lower:
                return city.title()
        
        # Ищем по паттернам
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                city = match.group(1).strip().title()
                if len(city) > 2:
                    return city
        
        return None
    
    def extract_quantity(self, message: str) -> Optional[int]:
        """Извлекает количество товара"""
        patterns = [
            r'(\d+)\s*(?:штук|шт\.?|штуки|экземпляр|экз\.?)',
            r'(\d+)\s*(?:кольца|серьги|браслета|кулона)',
            r'количество\s*(\d+)',
            r'нужно\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                quantity = int(match.group(1))
                if 1 <= quantity <= 100:  # Разумные пределы
                    return quantity
        
        return None
    
    def extract_product_id(self, message: str) -> Optional[str]:
        """Извлекает ID товара из сообщения"""
        patterns = [
            r'товар\s*#?(\w+)',
            r'артикул\s*#?(\w+)',
            r'номер\s*#?(\d+)',
            r'id\s*#?(\w+)',
            r'#(\w+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                product_id = match.group(1).strip()
                if len(product_id) > 1:
                    return product_id
        
        return None
    
    def has_required_slots_for_search(self, entities: Dict[str, Any]) -> bool:
        """Проверяет достаточно ли данных для поиска товаров"""
        return bool(entities.get('category') or entities.get('budget'))
    
    def has_required_slots_for_order(self, entities: Dict[str, Any]) -> bool:
        """Проверяет достаточно ли данных для оформления заказа"""
        required = ['name', 'phone']
        return all(entities.get(slot) for slot in required)
    
    def get_missing_slots_for_order(self, entities: Dict[str, Any]) -> List[str]:
        """Возвращает список недостающих слотов для заказа"""
        required = ['name', 'phone']
        return [slot for slot in required if not entities.get(slot)]