"""
Regression тесты для поведения ИИ консультанта янтарного магазина
Проверяют, что изменения в коде не ломают ожидаемое поведение
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any

from src.ai.intent_classifier import IntentClassifier
from src.ai.entity_extractor import EntityExtractor
from src.ai.dialogue_state_manager import DialogueStateManager
from src.ai.delivery_manager import DeliveryManager
from src.ai.guardrails import ConsultantGuardrails, SelfAssessment


class TestIntentClassificationRegression:
    """Регрессионные тесты для классификации намерений"""
    
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()
    
    def test_browse_catalog_intent_stability(self, classifier):
        """Тест стабильности распознавания намерения просмотра каталога"""
        test_cases = [
            ("покажи кольца", "browse_catalog", 0.3),
            ("что у вас есть из серёжек", "browse_catalog", 0.3),
            ("хочу посмотреть браслеты", "browse_catalog", 0.3),
            ("какие есть варианты подвесок", "browse_catalog", 0.3),
        ]
        
        for message, expected_intent, min_confidence in test_cases:
            intent, confidence = classifier.classify_intent(message)
            assert intent == expected_intent, f"Wrong intent for '{message}': got {intent}, expected {expected_intent}"
            assert confidence >= min_confidence, f"Low confidence for '{message}': {confidence} < {min_confidence}"
    
    def test_buy_intent_stability(self, classifier):
        """Тест стабильности распознавания намерения покупки"""
        test_cases = [
            ("хочу купить это кольцо", "buy", 0.2),
            ("беру браслет", "buy", 0.2),
            ("хочу заказать серьги", "buy", 0.2),
            ("мне нужно оформить заказ", "buy", 0.2),
        ]
        
        for message, expected_intent, min_confidence in test_cases:
            intent, confidence = classifier.classify_intent(message)
            assert intent == expected_intent, f"Wrong intent for '{message}': got {intent}, expected {expected_intent}"
            assert confidence >= min_confidence, f"Low confidence for '{message}': {confidence} < {min_confidence}"
    
    def test_handover_request_stability(self, classifier):
        """Тест стабильности запроса живого менеджера"""
        test_cases = [
            ("хочу поговорить с менеджером", "handover_request", 0.2),
            ("переведите на живого человека", "handover_request", 0.2),
            ("нужен консультант", "handover_request", 0.2),
        ]
        
        for message, expected_intent, min_confidence in test_cases:
            intent, confidence = classifier.classify_intent(message)
            assert intent == expected_intent, f"Wrong intent for '{message}': got {intent}, expected {expected_intent}"
            assert confidence >= min_confidence, f"Low confidence for '{message}': {confidence} < {min_confidence}"


class TestEntityExtractionRegression:
    """Регрессионные тесты для извлечения сущностей"""
    
    @pytest.fixture
    def extractor(self):
        return EntityExtractor()
    
    def test_budget_extraction_stability(self, extractor):
        """Тест стабильности извлечения бюджета"""
        test_cases = [
            ("у меня 5000 рублей", {"type": "exact", "value": 5000.0}),
            ("до 10 тысяч", {"type": "max", "value": 10000.0}),
            ("от 3000 до 8000", {"type": "range", "min": 3000.0, "max": 8000.0}),
            ("не более 15000₽", {"type": "max", "value": 15000.0}),
        ]
        
        for message, expected_budget in test_cases:
            entities = extractor.extract_entities(message)
            budget = entities.get('budget')
            assert budget is not None, f"Budget not extracted from '{message}'"
            
            for key, value in expected_budget.items():
                assert budget.get(key) == value, f"Budget {key} mismatch for '{message}': got {budget.get(key)}, expected {value}"
    
    def test_category_extraction_stability(self, extractor):
        """Тест стабильности извлечения категорий"""
        test_cases = [
            ("показать кольца", "кольца"),
            ("хочу серьги", "серьги"),
            ("браслеты на руку", "браслеты"),
            ("подвески на шею", "кулоны"),
            ("красивые бусы", "бусы"),
        ]
        
        for message, expected_category in test_cases:
            entities = extractor.extract_entities(message)
            category = entities.get('category')
            assert category == expected_category, f"Category mismatch for '{message}': got {category}, expected {expected_category}"
    
    def test_phone_extraction_stability(self, extractor):
        """Тест стабильности извлечения телефонов"""
        test_cases = [
            ("мой телефон +7 900 123 45 67", "+7 900 123 45 67"),
            ("8-495-123-45-67", "+7 495 123 45 67"),
            ("79001234567", "+7 900 123 45 67"),
        ]
        
        for message, expected_phone in test_cases:
            entities = extractor.extract_entities(message)
            phone = entities.get('phone')
            assert phone is not None, f"Phone not extracted from '{message}'"
            # Нормализуем для сравнения
            normalized_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            normalized_expected = expected_phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            assert normalized_phone == normalized_expected, f"Phone mismatch for '{message}': got {phone}, expected {expected_phone}"


class TestDialogueStateRegression:
    """Регрессионные тесты для управления состоянием диалога"""
    
    @pytest.fixture
    def state_manager(self):
        return DialogueStateManager()
    
    def test_dialogue_flow_progression(self, state_manager):
        """Тест правильного прогрессирования этапов диалога"""
        user_id = 12345
        
        # Начальное состояние
        initial_stage = state_manager.get_stage(user_id)
        assert initial_stage == "greeting"
        
        # Прогрессия этапов
        state_manager.advance_stage(user_id)
        assert state_manager.get_stage(user_id) == "intent_detection"
        
        state_manager.advance_stage(user_id)
        assert state_manager.get_stage(user_id) == "slot_filling"
        
        state_manager.advance_stage(user_id)
        assert state_manager.get_stage(user_id) == "search"
    
    def test_slot_filling_logic(self, state_manager):
        """Тест логики заполнения слотов"""
        user_id = 12345
        
        # Добавляем слоты постепенно
        state_manager.update_slots(user_id, {"category": "кольца"})
        assert state_manager.has_slot(user_id, "category")
        assert state_manager.get_slot(user_id, "category") == "кольца"
        
        # Проверяем готовность к поиску
        assert state_manager.can_search_products(user_id) == True  # категория есть
        
        # Добавляем контактные данные
        state_manager.update_slots(user_id, {"name": "Анна", "phone": "+7 900 123 45 67"})
        assert state_manager.can_create_order(user_id) == True  # контакты есть
    
    def test_escalation_logic(self, state_manager):
        """Тест логики эскалации к менеджеру"""
        user_id = 12345
        
        # Изначально эскалация не нужна
        assert state_manager.should_escalate_to_manager(user_id) == False
        
        # Превышаем лимит попыток уточнения
        state_manager.increment_clarification_attempts(user_id)
        state_manager.increment_clarification_attempts(user_id)
        state_manager.increment_clarification_attempts(user_id)  # Превышаем max=2
        
        assert state_manager.should_escalate_to_manager(user_id) == True
        
        # Сброс после эскалации
        state_manager.reset_clarification_attempts(user_id)
        assert state_manager.should_escalate_to_manager(user_id) == False


class TestDeliveryRulesRegression:
    """Регрессионные тесты для правил доставки"""
    
    @pytest.fixture
    def delivery_manager(self):
        return DeliveryManager()
    
    def test_free_delivery_threshold(self, delivery_manager):
        """Тест порога бесплатной доставки 15,000₽"""
        # Ниже порога
        result = delivery_manager.calculate_delivery_cost(14999)
        assert result["is_free"] == False
        assert result["cost"] > 0
        
        # На пороге
        result = delivery_manager.calculate_delivery_cost(15000)
        assert result["is_free"] == True
        assert result["cost"] == 0
        
        # Выше порога  
        result = delivery_manager.calculate_delivery_cost(20000)
        assert result["is_free"] == True
        assert result["cost"] == 0
    
    def test_regional_delivery_costs(self, delivery_manager):
        """Тест региональных тарифов доставки"""
        test_cases = [
            ("москва", 200),
            ("санкт-петербург", 220), 
            ("екатеринбург", 350),
            ("владивосток", 500),
        ]
        
        for city, expected_base_cost in test_cases:
            result = delivery_manager.calculate_delivery_cost(5000, city=city)  # Ниже порога
            assert result["cost"] == expected_base_cost, f"Wrong delivery cost for {city}: got {result['cost']}, expected {expected_base_cost}"
    
    def test_delivery_upsell_logic(self, delivery_manager):
        """Тест логики предложения увеличить заказ"""
        # Близко к порогу - должен предлагать
        upsell_text = delivery_manager.get_free_delivery_upsell_text(12000)  # Нужно 3000₽
        assert upsell_text is not None
        assert "3,000₽" in upsell_text or "3000₽" in upsell_text
        
        # Далеко от порога - не предлагает
        upsell_text = delivery_manager.get_free_delivery_upsell_text(5000)  # Нужно 10000₽
        assert upsell_text is None
        
        # Уже выше порога - не предлагает
        upsell_text = delivery_manager.get_free_delivery_upsell_text(20000)
        assert upsell_text is None


class TestGuardrailsRegression:
    """Регрессионные тесты для системы guardrails"""
    
    @pytest.fixture
    def guardrails(self):
        return ConsultantGuardrails()
    
    def test_medical_claims_blocking(self, guardrails):
        """Тест блокировки медицинских утверждений"""
        dangerous_responses = [
            "Янтарь лечит артрит",
            "Это поможет от депрессии", 
            "Янтарь имеет лечебные свойства",
            "Носите для исцеления",
        ]
        
        for response in dangerous_responses:
            assert guardrails.is_response_safe(response) == False, f"Should block: '{response}'"
            results = guardrails.check_response(response)
            critical_results = [r for r in results if r.severity == "critical" and not r.passed]
            assert len(critical_results) > 0, f"Should have critical violations for: '{response}'"
    
    def test_inventory_claims_blocking(self, guardrails):
        """Тест блокировки утверждений о наличии товаров"""
        dangerous_responses = [
            "У нас есть такое кольцо",
            "В наличии браслеты",
            "Можем предложить серьги", 
        ]
        
        for response in dangerous_responses:
            assert guardrails.is_response_safe(response) == False, f"Should block: '{response}'"
    
    def test_safe_responses_passing(self, guardrails):
        """Тест пропуска безопасных ответов"""
        safe_responses = [
            "Рекомендую посмотреть наш каталог украшений",
            "Давайте найдем подходящий вариант в нашем ассортименте",
            "Янтарь - это красивый природный материал",
            "Доставка бесплатно от 15,000₽",
        ]
        
        for response in safe_responses:
            assert guardrails.is_response_safe(response) == True, f"Should pass: '{response}'"


class TestSelfAssessmentRegression:
    """Регрессионные тесты для системы самооценки"""
    
    @pytest.fixture
    def assessment(self):
        return SelfAssessment()
    
    def test_quality_scoring_stability(self, assessment):
        """Тест стабильности оценки качества"""
        test_cases = [
            ("Добро пожаловать! Рад помочь вам выбрать украшения из янтаря. Что вас интересует?", 0.7, 1.0),
            ("да", 0.0, 0.4),  # Слишком короткий
            ("", 0.0, 0.1),    # Пустой
            ("Рекомендую посмотреть кольца от 5,000₽ до 15,000₽. Какой стиль предпочитаете?", 0.6, 1.0),
        ]
        
        for response, min_score, max_score in test_cases:
            result = assessment.assess_response(response)
            score = result["overall_score"]
            assert min_score <= score <= max_score, f"Score {score} not in range [{min_score}, {max_score}] for: '{response}'"
    
    def test_helpfulness_assessment(self, assessment):
        """Тест оценки полезности"""
        helpful_response = "Показываю каталог колец с янтарем. У нас есть классические и современные модели от 3,000₽ до 25,000₽. Какой бюджет рассматриваете?"
        result = assessment.assess_response(helpful_response)
        
        # Должна быть высокая оценка полезности
        assert result["criteria_scores"]["helpfulness"] >= 0.6
        assert result["overall_score"] >= 0.6


class TestEndToEndBehavior:
    """Комплексные end-to-end тесты поведения"""
    
    @pytest.fixture
    def components(self):
        """Создает все компоненты системы"""
        return {
            "intent_classifier": IntentClassifier(),
            "entity_extractor": EntityExtractor(), 
            "state_manager": DialogueStateManager(),
            "delivery_manager": DeliveryManager(),
            "guardrails": ConsultantGuardrails(),
            "assessment": SelfAssessment(),
        }
    
    def test_typical_customer_journey(self, components):
        """Тест типичного пути клиента"""
        user_id = 99999
        classifier = components["intent_classifier"]
        extractor = components["entity_extractor"] 
        state_manager = components["state_manager"]
        
        # 1. Приветствие
        greeting = "Здравствуйте, хочу кольцо"
        intent, confidence = classifier.classify_intent(greeting)
        entities = extractor.extract_entities(greeting)
        
        assert intent in ["browse_catalog", "buy"]
        assert "category" in entities
        assert entities["category"] == "кольца"
        
        # 2. Обновляем состояние
        state_manager.add_intent_to_history(user_id, intent, confidence)
        state_manager.update_slots(user_id, entities)
        state_manager.set_stage(user_id, "slot_filling")
        
        # 3. Уточнение бюджета
        budget_message = "У меня 10000 рублей"
        entities2 = extractor.extract_entities(budget_message)
        state_manager.update_slots(user_id, entities2)
        
        assert "budget" in entities2
        assert state_manager.can_search_products(user_id) == True
        
        # 4. Готовность к заказу после выбора
        contact_message = "Меня зовут Мария, телефон +7 900 555 77 88"
        entities3 = extractor.extract_entities(contact_message)
        state_manager.update_slots(user_id, entities3)
        
        assert "name" in entities3
        assert "phone" in entities3
        assert state_manager.can_create_order(user_id) == True
    
    def test_delivery_integration(self, components):
        """Тест интеграции с доставкой"""
        delivery_manager = components["delivery_manager"]
        guardrails = components["guardrails"]
        
        # Проверяем корректное формирование текста о доставке
        delivery_text = delivery_manager.get_delivery_info_text(12000, city="москва")
        
        # Текст должен пройти guardrails
        assert guardrails.is_response_safe(delivery_text) == True
        
        # Должен содержать полезную информацию
        assert "доставка" in delivery_text.lower()
        assert any(word in delivery_text for word in ["₽", "рублей", "руб"])
    
    def test_escalation_scenario(self, components):
        """Тест сценария эскалации"""
        state_manager = components["state_manager"]
        classifier = components["intent_classifier"]
        user_id = 55555
        
        # Клиент просит менеджера
        handover_request = "хочу поговорить с живым консультантом"
        intent, confidence = classifier.classify_intent(handover_request)
        
        assert intent == "handover_request"
        
        # Обновляем состояние
        state_manager.add_intent_to_history(user_id, intent, confidence)
        
        # Должна сработать эскалация
        assert state_manager.should_escalate_to_manager(user_id) == True


class TestRegressionMetrics:
    """Тесты для отслеживания регрессии метрик"""
    
    def test_performance_baselines(self):
        """Тест базовых показателей производительности"""
        import time
        
        # Intent classification должна быть быстрой
        classifier = IntentClassifier()
        start_time = time.time()
        
        for _ in range(100):
            classifier.classify_intent("хочу купить кольцо")
        
        end_time = time.time()
        avg_time = (end_time - start_time) / 100
        
        # Должно быть меньше 10мс на классификацию
        assert avg_time < 0.01, f"Intent classification too slow: {avg_time:.4f}s"
    
    def test_memory_usage_baselines(self):
        """Тест базового потребления памяти"""
        import sys
        
        # Создаем компоненты и проверяем что они не слишком "тяжелые"
        components = {
            IntentClassifier(),
            EntityExtractor(),
            DialogueStateManager(), 
            DeliveryManager(),
            ConsultantGuardrails(),
            SelfAssessment(),
        }
        
        # Размер объектов в байтах (примерная оценка)
        total_size = sum(sys.getsizeof(comp) for comp in components)
        
        # Не должно превышать 1MB в совокупности 
        assert total_size < 1024 * 1024, f"Components too memory-heavy: {total_size} bytes"


if __name__ == "__main__":
    # Запуск всех тестов
    pytest.main([__file__, "-v", "--tb=short"])