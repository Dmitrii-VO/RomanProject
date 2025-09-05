"""
Dialogue State Manager - управление состоянием диалога и слотами
Отслеживает что уже известно о клиенте и его запросах
"""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import json
from utils.logger import app_logger


class DialogueStateManager:
    """
    Управляет состоянием диалога с клиентом

    Отслеживает:
    - Текущие слоты (категория, бюджет, стиль и т.д.)
    - Этап диалога (search, clarification, ordering)
    - Историю намерений
    - Данные о клиенте из CRM
    - Необходимые уточнения
    """

    def __init__(self):
        """Инициализация менеджера состояния диалога"""
        # Состояние для каждого пользователя
        self.user_states: Dict[int, Dict[str, Any]] = {}

        # Определяем этапы диалога
        self.dialogue_stages = [
            "greeting",      # Приветствие
            "intent_detection", # Определение намерения
            "slot_filling",  # Сбор слотов
            "search",        # Поиск товаров
            "selection",     # Выбор конкретного товара
            "ordering",      # Оформление заказа
            "payment",       # Оплата
            "completed"      # Завершен
        ]

        app_logger.info("DialogueStateManager инициализирован")
    
    def initialize_dialogue(self, user_id: int, intent: str, entities: Dict) -> Dict[str, Any]:
        """Инициализирует новое состояние диалога для пользователя"""
        if user_id not in self.user_states:
            self.user_states[user_id] = self._create_initial_state()
        
        state = self.user_states[user_id]
        state["current_intent"] = intent
        state["stage"] = "intent_detection"
        
        # Добавляем извлеченные сущности в слоты
        if entities:
            state["slots"].update(entities)
        
        # Добавляем намерение в историю
        self.add_intent_to_history(user_id, intent, 1.0)
        
        return state
    
    def update_state(self, dialogue_state: Dict, intent: str, entities: Dict, user_message: str) -> Dict:
        """Обновляет существующее состояние диалога"""
        dialogue_state["current_intent"] = intent
        dialogue_state["last_activity"] = datetime.now().isoformat()
        dialogue_state["conversation_count"] = dialogue_state.get("conversation_count", 0) + 1
        
        # Обновляем сущности
        if entities:
            if "entities" not in dialogue_state:
                dialogue_state["entities"] = {}
            dialogue_state["entities"].update(entities)
            dialogue_state["slots"].update(entities)
        
        return dialogue_state

    def get_user_state(self, user_id: int) -> Dict[str, Any]:
        """Получает текущее состояние пользователя"""
        if user_id not in self.user_states:
            self.user_states[user_id] = self._create_initial_state()

        return self.user_states[user_id]

    def _create_initial_state(self) -> Dict[str, Any]:
        """Создает начальное состояние для нового пользователя"""
        return {
            "stage": "greeting",
            "slots": {},
            "intent_history": [],
            "current_intent": None,
            "clarification_attempts": 0,
            "max_clarification_attempts": 2,
            "selected_products": [],
            "current_search_results": [],
            "needs_clarification": [],
            "crm_data": {},
            "conversation_count": 0,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "is_manager_handling": False
        }

    def update_user_state(self, user_id: int, updates: Dict[str, Any]):
        """Обновляет состояние пользователя"""
        state = self.get_user_state(user_id)

        # Обновляем время активности
        state["last_activity"] = datetime.now().isoformat()
        state["conversation_count"] += 1

        # Применяем обновления
        for key, value in updates.items():
            if key == "slots":
                # Слоты объединяем, не перезаписываем
                state["slots"].update(value)
            else:
                state[key] = value

        app_logger.debug(f"Updated state for user {user_id}: {updates}")

    def add_intent_to_history(self, user_id: int, intent: str, confidence: float):
        """Добавляет намерение в историю"""
        state = self.get_user_state(user_id)

        intent_record = {
            "intent": intent,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }

        state["intent_history"].append(intent_record)
        state["current_intent"] = intent

        # Ограничиваем историю последними 10 записями
        if len(state["intent_history"]) > 10:
            state["intent_history"] = state["intent_history"][-10:]

    def update_slots(self, user_id: int, new_slots: Dict[str, Any]):
        """Обновляет слоты пользователя"""
        state = self.get_user_state(user_id)

        # Объединяем новые слоты с существующими
        state["slots"].update(new_slots)

        app_logger.debug(f"Updated slots for user {user_id}: {new_slots}")

    def get_slot(self, user_id: int, slot_name: str) -> Any:
        """Получает значение конкретного слота"""
        state = self.get_user_state(user_id)
        return state["slots"].get(slot_name)

    def has_slot(self, user_id: int, slot_name: str) -> bool:
        """Проверяет наличие слота"""
        return self.get_slot(user_id, slot_name) is not None

    def get_missing_slots_for_search(self, user_id: int) -> List[str]:
        """Возвращает недостающие слоты для поиска товаров"""
        state = self.get_user_state(user_id)
        slots = state["slots"]

        missing = []

        # Для поиска нужна хотя бы категория или бюджет
        if not slots.get("category") and not slots.get("budget"):
            missing.append("category_or_budget")

        return missing

    def get_missing_slots_for_order(self, user_id: int) -> List[str]:
        """Возвращает недостающие слоты для оформления заказа"""
        state = self.get_user_state(user_id)
        slots = state["slots"]

        required_slots = ["name", "phone"]
        missing = []

        for slot in required_slots:
            if not slots.get(slot):
                missing.append(slot)

        return missing

    def can_search_products(self, user_id: int) -> bool:
        """Проверяет можно ли искать товары"""
        return len(self.get_missing_slots_for_search(user_id)) == 0

    def can_create_order(self, user_id: int) -> bool:
        """Проверяет можно ли оформить заказ"""
        return len(self.get_missing_slots_for_order(user_id)) == 0

    def set_stage(self, user_id: int, stage: str):
        """Устанавливает текущий этап диалога"""
        if stage in self.dialogue_stages:
            self.update_user_state(user_id, {"stage": stage})
        else:
            app_logger.warning(f"Unknown dialogue stage: {stage}")

    def get_stage(self, user_id: int) -> str:
        """Получает текущий этап диалога"""
        state = self.get_user_state(user_id)
        return state.get("stage", "greeting")

    def advance_stage(self, user_id: int):
        """Переходит к следующему этапу диалога"""
        current_stage = self.get_stage(user_id)

        if current_stage in self.dialogue_stages:
            current_index = self.dialogue_stages.index(current_stage)
            if current_index < len(self.dialogue_stages) - 1:
                next_stage = self.dialogue_stages[current_index + 1]
                self.set_stage(user_id, next_stage)
                app_logger.debug(f"Advanced stage for user {user_id}: {current_stage} -> {next_stage}")

    def increment_clarification_attempts(self, user_id: int):
        """Увеличивает счетчик попыток уточнения"""
        state = self.get_user_state(user_id)
        state["clarification_attempts"] += 1

    def reset_clarification_attempts(self, user_id: int):
        """Сбрасывает счетчик попыток уточнения"""
        self.update_user_state(user_id, {"clarification_attempts": 0})

    def should_escalate_to_manager(self, dialogue_state_or_user_id) -> bool:
        """Проверяет нужна ли эскалация к менеджеру"""
        # Поддерживаем как user_id, так и dialogue_state
        if isinstance(dialogue_state_or_user_id, int):
            state = self.get_user_state(dialogue_state_or_user_id)
        else:
            state = dialogue_state_or_user_id

        # Эскалация при превышении попыток уточнения
        if state.get("clarification_attempts", 0) >= state.get("max_clarification_attempts", 2):
            return True

        # Эскалация при явном запросе
        current_intent = state.get("current_intent")
        if current_intent == "handover_request":
            return True

        return False
    
    def get_missing_slots_for_search(self, dialogue_state: Dict) -> List[str]:
        """Определяет какие слоты нужны для поиска товаров"""
        required_slots = ["category"]  # Минимум нужна категория
        current_slots = dialogue_state.get("slots", {})
        entities = dialogue_state.get("entities", {})
        
        # Объединяем слоты и сущности
        all_data = {**current_slots, **entities}
        
        missing = []
        for slot in required_slots:
            if slot not in all_data or not all_data[slot]:
                missing.append(slot)
        
        return missing

    def set_manager_handling(self, user_id: int, handling: bool = True):
        """Устанавливает флаг обработки менеджером"""
        self.update_user_state(user_id, {"is_manager_handling": handling})

    def is_manager_handling(self, user_id: int) -> bool:
        """Проверяет ведет ли диалог менеджер"""
        state = self.get_user_state(user_id)
        return state.get("is_manager_handling", False)

    def set_search_results(self, user_id: int, products: List[Dict]):
        """Сохраняет результаты поиска товаров"""
        self.update_user_state(user_id, {"current_search_results": products})

    def get_search_results(self, user_id: int) -> List[Dict]:
        """Получает сохраненные результаты поиска"""
        state = self.get_user_state(user_id)
        return state.get("current_search_results", [])

    def add_selected_product(self, user_id: int, product: Dict):
        """Добавляет товар к выбранным"""
        state = self.get_user_state(user_id)
        selected = state.get("selected_products", [])

        # Проверяем что товар еще не выбран
        product_id = product.get("id")
        if not any(p.get("id") == product_id for p in selected):
            selected.append(product)
            self.update_user_state(user_id, {"selected_products": selected})

    def get_selected_products(self, user_id: int) -> List[Dict]:
        """Получает выбранные товары"""
        state = self.get_user_state(user_id)
        return state.get("selected_products", [])

    def clear_selected_products(self, user_id: int):
        """Очищает список выбранных товаров"""
        self.update_user_state(user_id, {"selected_products": []})

    def set_crm_data(self, user_id: int, crm_data: Dict):
        """Сохраняет данные из CRM"""
        self.update_user_state(user_id, {"crm_data": crm_data})

    def get_crm_data(self, user_id: int) -> Dict:
        """Получает данные из CRM"""
        state = self.get_user_state(user_id)
        return state.get("crm_data", {})

    def is_first_interaction(self, user_id: int) -> bool:
        """Проверяет первое ли это взаимодействие"""
        state = self.get_user_state(user_id)
        return state.get("conversation_count", 0) <= 1

    def get_context_summary(self, user_id: int) -> str:
        """Формирует краткую сводку контекста для ИИ"""
        state = self.get_user_state(user_id)

        summary_parts = []

        # Текущий этап
        stage = state.get("stage", "greeting")
        summary_parts.append(f"Этап: {stage}")

        # Слоты
        slots = state.get("slots", {})
        if slots:
            slots_str = ", ".join([f"{k}={v}" for k, v in slots.items()])
            summary_parts.append(f"Известно: {slots_str}")

        # Выбранные товары
        selected = state.get("selected_products", [])
        if selected:
            summary_parts.append(f"Выбрано товаров: {len(selected)}")

        # Попытки уточнения
        attempts = state.get("clarification_attempts", 0)
        if attempts > 0:
            summary_parts.append(f"Попыток уточнения: {attempts}")

        return " | ".join(summary_parts)

    def cleanup_old_states(self, hours: int = 24):
        """Очищает старые состояния пользователей"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        to_remove = []
        for user_id, state in self.user_states.items():
            last_activity = datetime.fromisoformat(state["last_activity"])
            if last_activity < cutoff_time:
                to_remove.append(user_id)

        for user_id in to_remove:
            del self.user_states[user_id]

        if to_remove:
            app_logger.info(f"Cleaned up {len(to_remove)} old user states")

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику состояний"""
        total_users = len(self.user_states)
        stages_stats = {}

        for state in self.user_states.values():
            stage = state.get("stage", "unknown")
            stages_stats[stage] = stages_stats.get(stage, 0) + 1

        return {
            "total_active_users": total_users,
            "stages_distribution": stages_stats,
            "manager_handling": sum(1 for s in self.user_states.values()
                                  if s.get("is_manager_handling", False))
        }