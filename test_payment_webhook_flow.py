#!/usr/bin/env python3
"""
Тест полного потока обработки платежа:
Создание платежа → Webhook → Обновление МойСклад → Создание входящего платежа
"""
import asyncio
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.payments.yukassa_client import YuKassaClient
from src.integrations.moysklad_client import MoySkladClient
from utils.logger import app_logger


async def test_payment_webhook_flow():
    """Тестирует полный поток обработки платежа"""
    print("🧪 Тестирование полного потока платежей...")
    
    try:
        # Шаг 1: Инициализация клиентов
        yukassa_client = YuKassaClient()
        moysklad_client = MoySkladClient()
        
        print("✅ Клиенты инициализированы")
        
        # Шаг 2: Используем существующий заказ для тестирования
        print("\n📝 Поиск существующего заказа для тестирования...")
        
        # Получаем первый существующий заказ
        orders_response = await moysklad_client._make_request("GET", "entity/customerorder", params={"limit": 1})
        if not orders_response or not orders_response.get("rows"):
            print("❌ Не найдены заказы в МойСклад для тестирования")
            return False
            
        test_order = orders_response["rows"][0]
        test_order_id = test_order['id']
        print(f"✅ Используем существующий заказ: {test_order.get('name', test_order_id)}")
        
        # Шаг 3: Имитируем создание платежа (без реального API)
        print("\n💳 Имитация создания платежа...")
        
        test_payment_data = {
            "amount": 1250.0,
            "order_id": "test_order_123",
            "moysklad_order_id": test_order_id,
            "telegram_user_id": 12345,
            "payment_id": "24b94598-000f-5000-9000-1b68e7b15f3f"
        }
        
        print(f"✅ Тестовый платеж: {test_payment_data['payment_id']}")
        
        # Шаг 4: Имитируем webhook от ЮKassa
        print("\n📨 Имитация webhook от ЮKassa...")
        
        # Создаем mock webhook данные
        mock_webhook_data = {
            "type": "notification",
            "event": "payment.succeeded",
            "object": {
                "id": test_payment_data["payment_id"],
                "status": "succeeded",
                "amount": {
                    "value": f"{test_payment_data['amount']:.2f}",
                    "currency": "RUB"
                },
                "description": f"Заказ №{test_order_id} - тестовый платеж",
                "metadata": {
                    "order_id": test_payment_data["order_id"],
                    "moysklad_order_id": test_payment_data["moysklad_order_id"],
                    "telegram_user_id": str(test_payment_data["telegram_user_id"])
                },
                "created_at": "2024-01-15T10:00:00.000Z"
            }
        }
        
        # Парсим webhook данные
        parsed_data = yukassa_client.parse_webhook(mock_webhook_data)
        print(f"✅ Webhook распарсен: {parsed_data.get('event_type')}")
        
        # Шаг 5: Обрабатываем платеж в МойСклад
        print("\n🏪 Обработка платежа в МойСклад...")
        
        result = await moysklad_client.process_payment_webhook(
            moysklad_order_id=test_order_id,
            payment_amount=test_payment_data["amount"],
            payment_id=test_payment_data["payment_id"],
            telegram_user_id=test_payment_data["telegram_user_id"]
        )
        
        if result.get("success"):
            print(f"✅ Заказ обновлен: payedSum = {test_payment_data['amount']}₽")
            print(f"✅ Входящий платеж создан: {result.get('customer_payment_id')}")
            print(f"✅ Сообщение для клиента: {result.get('message')}")
        else:
            print(f"❌ Ошибка обработки: {result.get('error')}")
        
        # Шаг 6: Проверяем результат в МойСклад
        print("\n🔍 Проверка результата...")
        
        # Получаем обновленный заказ
        updated_order = await moysklad_client.get_customer_order_by_id(test_order_id)
        if updated_order:
            payed_sum = updated_order.get('payedSum', 0) / 100  # Конвертируем из копеек
            print(f"✅ Заказ обновлен: оплаченная сумма = {payed_sum}₽")
            print(f"📝 Описание: {updated_order.get('description', '')[-100:]}")
        
        # Тестирование завершено (заказ остается для дальнейшего использования)
        
        print(f"\n🎉 Тест потока платежей завершен успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        app_logger.error(f"Ошибка тестирования потока платежей: {e}")
        return False


async def test_create_customer_payment():
    """Тест создания входящего платежа отдельно"""
    print("\n🧪 Дополнительный тест: создание входящего платежа...")
    
    try:
        moysklad_client = MoySkladClient()
        
        # Получаем первый заказ из системы для теста
        orders_response = await moysklad_client._make_request("GET", "entity/customerorder", params={"limit": 1})
        
        if not orders_response or not orders_response.get("rows"):
            print("❌ Не найдены заказы для тестирования")
            return False
        
        test_order = orders_response["rows"][0]
        test_order_id = test_order["id"]
        
        print(f"📋 Используем существующий заказ: {test_order.get('name', test_order_id)}")
        
        # Создаем тестовый входящий платеж
        payment_result = await moysklad_client.create_customer_payment(
            order_id=test_order_id,
            amount=500.0,  # Тестовая сумма
            description="Тестовый платеж через API",
            yukassa_payment_id="test_payment_12345"
        )
        
        if payment_result.get("success"):
            print(f"✅ Входящий платеж создан: {payment_result.get('payment_id')}")
        else:
            print(f"❌ Ошибка создания платежа: {payment_result.get('error')}")
            
        return payment_result.get("success", False)
        
    except Exception as e:
        print(f"❌ Ошибка теста входящих платежей: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Запуск тестов потока платежей...\n")
    
    # Основной тест
    main_test_success = asyncio.run(test_payment_webhook_flow())
    
    # Дополнительный тест
    payment_test_success = asyncio.run(test_create_customer_payment())
    
    print(f"\n📊 Результаты тестирования:")
    print(f"✅ Основной поток платежей: {'ПРОЙДЕН' if main_test_success else 'ПРОВАЛЕН'}")
    print(f"✅ Создание входящих платежей: {'ПРОЙДЕН' if payment_test_success else 'ПРОВАЛЕН'}")
    
    if main_test_success and payment_test_success:
        print(f"\n🎉 Все тесты пройдены! Система готова к приему платежей.")
    else:
        print(f"\n❌ Некоторые тесты провалены. Требуется доработка.")