"""
Intent Classification система для ИИ консультанта янтарного магазина
Распознает намерения клиентов по их сообщениям
"""
import re
from typing import Dict, List, Optional, Tuple
from utils.logger import app_logger


class IntentClassifier:
    """
    Классифицирует намерения клиентов в диалогах
    
    Поддерживаемые интенты:
    - browse_catalog: просмотр каталога
    - product_question: вопрос о товаре
    - buy: покупка
    - delivery: доставка  
    - payment: оплата
    - warranty_returns: гарантия/возврат
    - smalltalk: общение
    - handover_request: запрос менеджера
    - unknown: неопределенное
    """
    
    def __init__(self):
        """Инициализация классификатора намерений"""
        self.intent_patterns = self._build_intent_patterns()
        app_logger.info("IntentClassifier инициализирован")
    
    def _build_intent_patterns(self) -> Dict[str, List[str]]:
        """Создает паттерны для распознавания намерений"""
        return {
            "browse_catalog": [
                # Просмотр каталога
                "покажи", "покажите", "посмотреть", "какие есть", "что у вас есть",
                "ассортимент", "каталог", "товары", "выбрать из", "подскажите что",
                "что можете предложить", "варианты", "предложите", "хочу посмотреть",
                "есть ли", "что есть", "показать", "демонстрация", "выбор",
                # Категории товаров
                "кольца", "серьги", "браслеты", "кулоны", "бусы", "брошки", "подвески"
            ],
            
            "product_question": [
                # Вопросы о товарах
                "свойства", "характеристики", "размер", "вес", "материал", 
                "янтарь", "происхождение", "качество", "цвет", "прозрачность",
                "включения", "инклюзы", "возраст", "месторождение", "балтийский",
                "целебные", "лечебные", "магические", "энергетика", "аура",
                "как носить", "уход", "чистка", "хранение"
            ],
            
            "buy": [
                # Покупка
                "купить", "заказать", "оформить", "хочу", "беру", "покупаю",
                "приобрести", "взять", "оформление", "заказ", "бронирование",
                "резерв", "забронировать", "выбираю", "мне нужно", "требуется"
            ],
            
            "delivery": [
                # Доставка
                "доставка", "отправка", "курьер", "почта", "транспорт",
                "сроки", "когда получу", "время доставки", "стоимость доставки",
                "бесплатная доставка", "регион", "город", "адрес", "индекс",
                "самовывоз", "забрать", "получение"
            ],
            
            "payment": [
                # Оплата
                "оплата", "платеж", "карта", "наличные", "перевод", "счет",
                "квитанция", "чек", "банк", "сбербанк", "тинькофф", "альфа",
                "кошелек", "яндекс деньги", "qiwi", "webmoney", "киви",
                "оплатить", "заплатить", "цена", "стоимость", "сколько"
            ],
            
            "warranty_returns": [
                # Гарантия и возврат
                "возврат", "обмен", "гарантия", "брак", "дефект", "поломка",
                "не подошло", "не нравится", "качество", "претензия", "жалоба",
                "рекламация", "ремонт", "замена", "не работает", "сломалось"
            ],
            
            "handover_request": [
                # Запрос менеджера
                "менеджер", "сотрудник", "человек", "живой", "оператор",
                "консультант", "руководитель", "директор", "администрация",
                "жалобная книга", "главный", "начальник", "специалист"
            ],
            
            "smalltalk": [
                # Общение
                "привет", "здравствуйте", "добрый", "спасибо", "благодарю",
                "пока", "до свидания", "хорошего", "отлично", "супер", "класс",
                "как дела", "как поживаете", "погода", "настроение", "праздник"
            ]
        }
    
    def classify_intent(self, message: str) -> Tuple[str, float]:
        """
        Классифицирует намерение сообщения
        
        Args:
            message: Текст сообщения пользователя
            
        Returns:
            Tuple[intent, confidence] - намерение и уверенность (0.0-1.0)
        """
        if not message or not message.strip():
            return "unknown", 0.0
            
        message_lower = message.lower().strip()
        intent_scores = {}
        
        # Подсчитываем очки для каждого намерения
        for intent, patterns in self.intent_patterns.items():
            score = 0
            total_patterns = len(patterns)
            
            for pattern in patterns:
                if pattern in message_lower:
                    # Длинные паттерны более специфичны
                    weight = len(pattern.split()) 
                    score += weight
            
            # Нормализуем счет
            if total_patterns > 0:
                intent_scores[intent] = score / total_patterns
        
        # Находим лучший результат
        if not intent_scores or max(intent_scores.values()) == 0:
            return "unknown", 0.0
        
        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = min(intent_scores[best_intent], 1.0)  # Максимум 1.0
        
        # Минимальный порог уверенности
        if confidence < 0.1:
            return "unknown", confidence
        
        app_logger.debug(f"Intent: {best_intent} ({confidence:.2f}) for: '{message[:50]}...'")
        return best_intent, confidence
    
    def get_intent_description(self, intent: str) -> str:
        """Возвращает человекочитаемое описание намерения"""
        descriptions = {
            "browse_catalog": "Просмотр каталога товаров",
            "product_question": "Вопрос о товаре или янтаре", 
            "buy": "Покупка товара",
            "delivery": "Вопросы о доставке",
            "payment": "Вопросы об оплате",
            "warranty_returns": "Гарантия и возврат",
            "smalltalk": "Общение и приветствие",
            "handover_request": "Запрос живого менеджера",
            "unknown": "Неопределенное намерение"
        }
        return descriptions.get(intent, "Неизвестное намерение")
    
    def is_high_confidence(self, confidence: float) -> bool:
        """Проверяет высокую уверенность классификации"""
        return confidence >= 0.7
    
    def requires_clarification(self, intent: str, confidence: float) -> bool:
        """Определяет нужно ли уточнение намерения"""
        if intent == "unknown":
            return True
        
        if confidence < 0.3:
            return True
            
        return False