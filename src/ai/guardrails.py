"""
Guardrails система для контроля качества ответов ИИ консультанта
Проверяет соответствие ответов политикам и предотвращает ошибки
"""
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from utils.logger import app_logger


@dataclass
class GuardrailResult:
    """Результат проверки guardrail"""
    passed: bool
    rule_name: str
    severity: str  # "critical", "warning", "info"
    message: str
    suggestions: List[str] = None


class ConsultantGuardrails:
    """
    Система guardrails для консультанта янтарного магазина
    
    Проверяет:
    - Отсутствие выдумок фактов
    - Соответствие персоне консультанта  
    - Корректность информации о товарах
    - Этичность ответов
    - Соответствие бизнес-правилам
    """
    
    def __init__(self):
        """Инициализация системы guardrails"""
        self.critical_rules = self._build_critical_rules()
        self.warning_rules = self._build_warning_rules()
        self.info_rules = self._build_info_rules()
        
        # Forbidden patterns - что нельзя говорить
        self.forbidden_patterns = self._build_forbidden_patterns()
        
        # Required patterns - что должно присутствовать в определенных ситуациях
        self.required_patterns = self._build_required_patterns()
        
        app_logger.info("ConsultantGuardrails инициализирован")
    
    def _build_critical_rules(self) -> Dict[str, Dict]:
        """Критические правила - блокируют ответ"""
        return {
            "no_medical_claims": {
                "description": "Запрет медицинских утверждений",
                "patterns": [
                    r"лечит", r"излечивает", r"помогает от болезни", r"лекарство",
                    r"медицинские свойства", r"терапевтический эффект", 
                    r"исцеляет", r"от боли", r"от депрессии"
                ],
                "message": "Нельзя делать медицинские утверждения о янтаре"
            },
            
            "no_guarantees_without_basis": {
                "description": "Запрет необоснованных гарантий", 
                "patterns": [
                    r"гарантирую", r"обещаю", r"точно будет", r"100% подойдет",
                    r"определенно", r"без сомнения будет"
                ],
                "message": "Нельзя давать необоснованные гарантии"
            },
            
            "no_fake_inventory": {
                "description": "Запрет выдумывания товаров",
                "patterns": [
                    r"у нас есть (\w+)", r"в наличии (\w+)", r"можем предложить (\w+)"
                ],
                "message": "Нельзя утверждать наличие товаров без проверки каталога"
            },
            
            "no_competitor_bashing": {
                "description": "Запрет критики конкурентов",
                "patterns": [
                    r"другие магазины", r"конкуренты", r"у них хуже", 
                    r"мы лучше чем", r"только у нас"
                ],
                "message": "Нельзя критиковать конкурентов"
            }
        }
    
    def _build_warning_rules(self) -> Dict[str, Dict]:
        """Правила-предупреждения"""
        return {
            "price_mentions_without_context": {
                "description": "Упоминание цен без контекста",
                "patterns": [
                    r"стоит (\d+)", r"цена (\d+)", r"(\d+) рублей"
                ],
                "message": "При упоминании цен желательно указать за что именно"
            },
            
            "informal_tone": {
                "description": "Слишком неформальный тон",
                "patterns": [
                    r"\bбля\b", r"\bблин\b", r"\bкруто\b", r"\bофигенно\b",
                    r"\bпиздец\b", r"\bохренеть\b"
                ],
                "message": "Тон может быть слишком неформальным для консультанта"
            },
            
            "missing_helpful_info": {
                "description": "Отсутствие полезной информации",
                "patterns": [
                    r"^да$", r"^нет$", r"^хорошо$", r"^понятно$"
                ],
                "message": "Ответ слишком короткий, можно добавить полезную информацию"
            }
        }
    
    def _build_info_rules(self) -> Dict[str, Dict]:
        """Информационные правила - подсказки"""
        return {
            "delivery_context": {
                "description": "Контекст доставки",
                "patterns": [r"доставк", r"отправ", r"получ"],
                "message": "При обсуждении доставки стоит упомянуть бесплатную доставку от 15,000₽"
            },
            
            "amber_education": {
                "description": "Образовательная информация о янтаре",
                "patterns": [r"янтарь", r"свойства", r"происхождение"],
                "message": "Можно добавить интересные факты о янтаре"
            }
        }
    
    def _build_forbidden_patterns(self) -> List[Dict[str, str]]:
        """Запрещенные паттерны и их замены"""
        return [
            {
                "pattern": r"я не знаю",
                "replacement": "Позвольте мне уточнить эту информацию",
                "reason": "Консультант должен звучать компетентно"
            },
            {
                "pattern": r"не могу помочь", 
                "replacement": "Давайте найдем решение вместе",
                "reason": "Консультант должен быть решение-ориентированным"
            },
            {
                "pattern": r"это не мое дело",
                "replacement": "Позвольте мне найти правильного специалиста",
                "reason": "Консультант должен быть сервис-ориентированным"
            }
        ]
    
    def _build_required_patterns(self) -> Dict[str, Dict]:
        """Обязательные паттерны для определенных ситуаций"""
        return {
            "greeting_response": {
                "triggers": [r"привет", r"здравствуй", r"добрый"],
                "required": [r"здравствуйте", r"добро пожаловать", r"рад помочь"],
                "message": "В приветствии должны быть вежливые формулы"
            },
            
            "price_inquiry": {
                "triggers": [r"сколько стоит", r"какая цена", r"стоимость"],
                "required": [r"рублей", r"₽", r"стоимость"],
                "message": "При запросе цены должна быть конкретная информация"
            }
        }
    
    def check_response(self, response_text: str, context: Dict[str, Any] = None) -> List[GuardrailResult]:
        """
        Проверяет ответ консультанта на соответствие правилам
        
        Args:
            response_text: Текст ответа для проверки
            context: Контекст диалога (намерение, слоты и т.д.)
            
        Returns:
            List[GuardrailResult] - список результатов проверок
        """
        if not response_text or not response_text.strip():
            return [GuardrailResult(
                passed=False,
                rule_name="empty_response",
                severity="critical", 
                message="Ответ не может быть пустым",
                suggestions=["Предоставьте содержательный ответ"]
            )]
        
        results = []
        
        # Проверяем критические правила
        results.extend(self._check_rule_set(response_text, self.critical_rules, "critical"))
        
        # Проверяем предупреждения
        results.extend(self._check_rule_set(response_text, self.warning_rules, "warning"))
        
        # Проверяем информационные правила
        results.extend(self._check_rule_set(response_text, self.info_rules, "info"))
        
        # Проверяем запрещенные паттерны
        results.extend(self._check_forbidden_patterns(response_text))
        
        # Проверяем обязательные паттерны
        if context:
            results.extend(self._check_required_patterns(response_text, context))
        
        # Если нет нарушений, добавляем успешный результат
        if not results:
            results.append(GuardrailResult(
                passed=True,
                rule_name="all_checks_passed",
                severity="info",
                message="Все проверки пройдены успешно"
            ))
        
        app_logger.debug(f"Guardrails check: {len(results)} results for response length {len(response_text)}")
        return results
    
    def _check_rule_set(self, text: str, rules: Dict[str, Dict], severity: str) -> List[GuardrailResult]:
        """Проверяет набор правил"""
        results = []
        text_lower = text.lower()
        
        for rule_name, rule_config in rules.items():
            patterns = rule_config.get("patterns", [])
            
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    results.append(GuardrailResult(
                        passed=False,
                        rule_name=rule_name,
                        severity=severity,
                        message=rule_config["message"],
                        suggestions=rule_config.get("suggestions", [])
                    ))
                    break  # Один trigger на правило достаточно
        
        return results
    
    def _check_forbidden_patterns(self, text: str) -> List[GuardrailResult]:
        """Проверяет запрещенные паттерны"""
        results = []
        
        for forbidden in self.forbidden_patterns:
            if re.search(forbidden["pattern"], text, re.IGNORECASE):
                results.append(GuardrailResult(
                    passed=False,
                    rule_name=f"forbidden_{forbidden['pattern'][:20]}",
                    severity="warning",
                    message=f"{forbidden['reason']}",
                    suggestions=[f"Используйте: {forbidden['replacement']}"]
                ))
        
        return results
    
    def _check_required_patterns(self, text: str, context: Dict[str, Any]) -> List[GuardrailResult]:
        """Проверяет обязательные паттерны"""
        results = []
        user_intent = context.get("intent", "")
        
        for pattern_name, pattern_config in self.required_patterns.items():
            # Проверяем триггеры
            triggers = pattern_config.get("triggers", [])
            triggered = any(re.search(trigger, user_intent, re.IGNORECASE) for trigger in triggers)
            
            if triggered:
                # Проверяем наличие обязательных элементов
                required = pattern_config.get("required", [])
                found_required = any(re.search(req, text, re.IGNORECASE) for req in required)
                
                if not found_required:
                    results.append(GuardrailResult(
                        passed=False,
                        rule_name=pattern_name,
                        severity="warning",
                        message=pattern_config["message"],
                        suggestions=[f"Добавьте: {', '.join(required)}"]
                    ))
        
        return results
    
    def is_response_safe(self, response_text: str, context: Dict[str, Any] = None) -> bool:
        """
        Быстрая проверка безопасности ответа
        
        Returns:
            True если ответ безопасен для отправки
        """
        results = self.check_response(response_text, context)
        
        # Блокируем только критические нарушения
        critical_failures = [r for r in results if r.severity == "critical" and not r.passed]
        return len(critical_failures) == 0
    
    def get_improvement_suggestions(self, response_text: str, 
                                   context: Dict[str, Any] = None) -> List[str]:
        """Получает предложения по улучшению ответа"""
        results = self.check_response(response_text, context)
        
        suggestions = []
        for result in results:
            if not result.passed and result.suggestions:
                suggestions.extend(result.suggestions)
        
        return list(set(suggestions))  # Убираем дубликаты
    
    def get_quality_score(self, response_text: str, context: Dict[str, Any] = None) -> float:
        """
        Рассчитывает оценку качества ответа (0.0 - 1.0)
        
        Returns:
            Оценка от 0.0 (очень плохо) до 1.0 (отлично)
        """
        results = self.check_response(response_text, context)
        
        if not results:
            return 0.5  # Нейтрально если нет проверок
        
        penalty_weights = {
            "critical": 0.5,  # Критические ошибки сильно снижают оценку
            "warning": 0.2,   # Предупреждения умеренно снижают
            "info": 0.05      # Информационные подсказки почти не влияют
        }
        
        total_penalty = 0
        total_checks = len(results)
        
        for result in results:
            if not result.passed:
                total_penalty += penalty_weights.get(result.severity, 0.1)
        
        # Начинаем с 1.0 и вычитаем штрафы
        score = max(0.0, 1.0 - (total_penalty / max(total_checks, 1)))
        
        return score
    
    def format_guardrail_report(self, results: List[GuardrailResult]) -> str:
        """Форматирует отчет о проверках для логов"""
        if not results:
            return "Guardrails: No checks performed"
        
        passed = len([r for r in results if r.passed])
        failed = len([r for r in results if not r.passed])
        
        report = f"Guardrails Report: {passed} passed, {failed} failed\n"
        
        # Группируем по severity
        critical = [r for r in results if r.severity == "critical" and not r.passed]
        warnings = [r for r in results if r.severity == "warning" and not r.passed]
        
        if critical:
            report += f"🚨 CRITICAL ({len(critical)}): " + ", ".join([r.rule_name for r in critical]) + "\n"
        
        if warnings:
            report += f"⚠️  WARNINGS ({len(warnings)}): " + ", ".join([r.rule_name for r in warnings])
        
        return report
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику системы guardrails"""
        return {
            "total_critical_rules": len(self.critical_rules),
            "total_warning_rules": len(self.warning_rules),
            "total_info_rules": len(self.info_rules),
            "total_forbidden_patterns": len(self.forbidden_patterns),
            "total_required_patterns": len(self.required_patterns)
        }


class SelfAssessment:
    """
    Система самооценки качества ответов консультанта
    Использует мини-оценки для контроля качества
    """
    
    def __init__(self):
        """Инициализация системы самооценки"""
        self.assessment_criteria = self._build_assessment_criteria()
        app_logger.info("SelfAssessment инициализирован")
    
    def _build_assessment_criteria(self) -> Dict[str, Dict]:
        """Создает критерии самооценки"""
        return {
            "helpfulness": {
                "description": "Полезность ответа для клиента",
                "weight": 0.3,
                "checks": [
                    "Отвечает ли на вопрос клиента?",
                    "Содержит ли практическую информацию?", 
                    "Помогает ли продвинуться в диалоге?"
                ]
            },
            
            "accuracy": {
                "description": "Точность и корректность информации",
                "weight": 0.25,
                "checks": [
                    "Вся ли информация основана на фактах?",
                    "Нет ли противоречий с политиками магазина?",
                    "Корректны ли цены и условия?"
                ]
            },
            
            "professionalism": {
                "description": "Профессионализм консультанта",
                "weight": 0.2,
                "checks": [
                    "Соответствует ли тон профессиональному консультанту?",
                    "Вежлив ли ответ?",
                    "Звучит ли компетентно?"
                ]
            },
            
            "completeness": {
                "description": "Полнота ответа",
                "weight": 0.15,
                "checks": [
                    "Покрыты ли все аспекты вопроса?",
                    "Предложены ли следующие шаги?",
                    "Достаточно ли информации для принятия решения?"
                ]
            },
            
            "engagement": {
                "description": "Вовлеченность и персонализация",
                "weight": 0.1,
                "checks": [
                    "Учитывает ли ответ контекст диалога?",
                    "Поддерживает ли интерес клиента?",
                    "Побуждает ли к дальнейшему взаимодействию?"
                ]
            }
        }
    
    def assess_response(self, response_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Проводит самооценку качества ответа
        
        Args:
            response_text: Текст ответа
            context: Контекст диалога
            
        Returns:
            Dict с результатами оценки
        """
        if not response_text or not response_text.strip():
            return {
                "overall_score": 0.0,
                "criteria_scores": {},
                "suggestions": ["Ответ не может быть пустым"],
                "assessment_summary": "Критическая ошибка: пустой ответ"
            }
        
        criteria_scores = {}
        suggestions = []
        
        # Оцениваем по каждому критерию
        for criterion_name, criterion_config in self.assessment_criteria.items():
            score = self._evaluate_criterion(response_text, criterion_name, criterion_config, context)
            criteria_scores[criterion_name] = score
            
            # Добавляем предложения если оценка низкая
            if score < 0.6:
                suggestions.extend(self._get_improvement_suggestions_for_criterion(
                    criterion_name, criterion_config, score
                ))
        
        # Рассчитываем общую оценку
        overall_score = sum(
            score * self.assessment_criteria[criterion]["weight"] 
            for criterion, score in criteria_scores.items()
        )
        
        return {
            "overall_score": round(overall_score, 2),
            "criteria_scores": criteria_scores,
            "suggestions": suggestions[:3],  # Топ-3 предложения
            "assessment_summary": self._generate_assessment_summary(overall_score, criteria_scores)
        }
    
    def _evaluate_criterion(self, response_text: str, criterion_name: str, 
                           criterion_config: Dict, context: Dict[str, Any] = None) -> float:
        """Оценивает ответ по конкретному критерию"""
        
        # Базовые проверки для каждого критерия
        if criterion_name == "helpfulness":
            return self._assess_helpfulness(response_text, context)
        
        elif criterion_name == "accuracy":
            return self._assess_accuracy(response_text, context)
        
        elif criterion_name == "professionalism":
            return self._assess_professionalism(response_text)
        
        elif criterion_name == "completeness":
            return self._assess_completeness(response_text, context)
        
        elif criterion_name == "engagement":
            return self._assess_engagement(response_text, context)
        
        else:
            return 0.5  # Нейтральная оценка для неизвестных критериев
    
    def _assess_helpfulness(self, text: str, context: Dict[str, Any] = None) -> float:
        """Оценивает полезность ответа"""
        score = 0.5  # Базовая оценка
        
        # Плюсы
        if len(text.strip()) > 50:
            score += 0.1  # Содержательный ответ
        
        if any(word in text.lower() for word in ["помогу", "рекомендую", "предлагаю", "советую"]):
            score += 0.1  # Активная помощь
        
        if re.search(r"\d+(?:\s?\d{3})*\s*₽", text):
            score += 0.1  # Конкретные цены
        
        if context and context.get("intent") == "browse_catalog" and "каталог" in text.lower():
            score += 0.2  # Соответствие намерению
        
        # Минусы
        if len(text.strip()) < 20:
            score -= 0.2  # Слишком короткий
        
        return min(1.0, max(0.0, score))
    
    def _assess_accuracy(self, text: str, context: Dict[str, Any] = None) -> float:
        """Оценивает точность информации"""
        score = 0.7  # Начинаем с хорошей оценки
        
        # Проверяем на потенциальные выдумки
        risky_phrases = [
            "у нас есть", "в наличии", "гарантирую", "точно подойдет",
            "лечебные свойства", "медицинский эффект"
        ]
        
        for phrase in risky_phrases:
            if phrase in text.lower():
                score -= 0.15
        
        # Плюсы за осторожные формулировки
        careful_phrases = ["возможно", "обычно", "как правило", "уточню"]
        for phrase in careful_phrases:
            if phrase in text.lower():
                score += 0.1
        
        return min(1.0, max(0.0, score))
    
    def _assess_professionalism(self, text: str) -> float:
        """Оценивает профессионализм"""
        score = 0.6
        
        # Плюсы за вежливость
        polite_words = ["пожалуйста", "спасибо", "будет приятно", "рад помочь"]
        score += sum(0.05 for word in polite_words if word in text.lower())
        
        # Минусы за неформальность
        informal_words = ["крутой", "офигенный", "класс", "супер"]
        score -= sum(0.1 for word in informal_words if word in text.lower())
        
        # Плюсы за профессиональную лексику
        professional_words = ["консультант", "рекомендации", "ассортимент"]
        score += sum(0.05 for word in professional_words if word in text.lower())
        
        return min(1.0, max(0.0, score))
    
    def _assess_completeness(self, text: str, context: Dict[str, Any] = None) -> float:
        """Оценивает полноту ответа"""
        score = 0.5
        
        # Плюсы за структуру
        if ":" in text or "•" in text or "-" in text:
            score += 0.1  # Структурированный ответ
        
        # Плюсы за следующие шаги
        next_step_phrases = ["также можете", "рекомендую", "предлагаю посмотреть", "следующий шаг"]
        if any(phrase in text.lower() for phrase in next_step_phrases):
            score += 0.15
        
        # Базируется на длине и содержательности
        if len(text.strip()) > 100:
            score += 0.1
        elif len(text.strip()) < 30:
            score -= 0.2
        
        return min(1.0, max(0.0, score))
    
    def _assess_engagement(self, text: str, context: Dict[str, Any] = None) -> float:
        """Оценивает вовлеченность"""
        score = 0.5
        
        # Плюсы за вопросы клиенту
        if "?" in text:
            score += 0.15
        
        # Плюсы за персонализацию
        personal_words = ["вам", "ваш", "для вас", "вашего"]
        score += sum(0.05 for word in personal_words if word in text.lower())
        
        # Плюсы за эмоциональные элементы (в меру)
        if any(emoji in text for emoji in ["😊", "✨", "💎", "🌟"]):
            score += 0.1
        
        return min(1.0, max(0.0, score))
    
    def _get_improvement_suggestions_for_criterion(self, criterion_name: str, 
                                                  criterion_config: Dict, score: float) -> List[str]:
        """Генерирует предложения по улучшению для критерия"""
        suggestions = {
            "helpfulness": [
                "Добавьте больше практической информации",
                "Предложите конкретные варианты действий",
                "Сделайте ответ более содержательным"
            ],
            "accuracy": [
                "Используйте только проверенную информацию",
                "Добавьте оговорки для неточной информации",
                "Избегайте категоричных утверждений"
            ],
            "professionalism": [
                "Используйте более вежливые формулировки",
                "Избегайте слишком разговорного стиля",
                "Добавьте профессиональную лексику"
            ],
            "completeness": [
                "Покройте больше аспектов вопроса",
                "Добавьте информацию о следующих шагах",
                "Структурируйте ответ лучше"
            ],
            "engagement": [
                "Задайте вопрос клиенту",
                "Сделайте ответ более персональным",
                "Поддержите интерес к диалогу"
            ]
        }
        
        return suggestions.get(criterion_name, ["Улучшите качество ответа"])
    
    def _generate_assessment_summary(self, overall_score: float, criteria_scores: Dict[str, float]) -> str:
        """Генерирует краткую сводку оценки"""
        if overall_score >= 0.8:
            return "Отличный ответ консультанта"
        elif overall_score >= 0.6:
            return "Хороший ответ, есть место для улучшений"
        elif overall_score >= 0.4:
            return "Удовлетворительный ответ, требует доработки"
        else:
            return "Неудовлетворительный ответ, нужна значительная доработка"
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику системы самооценки"""
        return {
            "total_criteria": len(self.assessment_criteria),
            "criteria_weights": {k: v["weight"] for k, v in self.assessment_criteria.items()}
        }