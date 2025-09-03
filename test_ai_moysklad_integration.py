#!/usr/bin/env python3
"""
Тестирование интеграции ИИ консультанта с МойСклад
"""
import asyncio
import os
from src.ai.consultant import AmberAIConsultant
from utils.logger import app_logger


async def test_ai_product_requests():
    """Тестирует обработку запросов товаров через ИИ консультанта"""
    print("🤖 Тестирование интеграции ИИ консультанта с каталогом товаров")
    print("=" * 60)
    
    # Создаем ИИ консультанта
    ai_consultant = AmberAIConsultant()
    
    # Тестовые запросы от пользователей
    test_requests = [
        {
            'user_id': 12345,
            'message': 'Покажите мне кольца до 5000 рублей',
            'description': 'Поиск колец с бюджетом'
        },
        {
            'user_id': 12346,
            'message': 'Хочу посмотреть что у вас есть из серёг',
            'description': 'Поиск серёг без бюджета'
        },
        {
            'user_id': 12347,
            'message': 'Покажите ассортимент браслетов',
            'description': 'Просмотр категории браслетов'
        }
    ]
    
    for i, test_case in enumerate(test_requests, 1):
        print(f"\n🧪 Тест {i}: {test_case['description']}")
        print(f"👤 Пользователь {test_case['user_id']}: {test_case['message']}")
        print("-" * 40)
        
        try:
            # Обрабатываем сообщение через ИИ консультанта
            response = await ai_consultant.process_message(
                test_case['user_id'], 
                test_case['message']
            )
            
            print(f"🤖 Ответ ИИ консультанта:")
            print(response)
            
            # Проверяем, есть ли в ответе товары
            if '🛍️' in response or '💎' in response:
                print("✅ Товары успешно показаны!")
            else:
                print("ℹ️ Товары не найдены или не показаны")
                
        except Exception as e:
            print(f"❌ Ошибка обработки запроса: {e}")
            app_logger.error(f"Ошибка тестирования ИИ консультанта: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 Тестирование интеграции завершено!")


async def test_budget_parsing_integration():
    """Тестирует интеграцию парсинга бюджета в ИИ консультанте"""
    print("\n💰 Тестирование распознавания бюджета в диалоге:")
    print("-" * 40)
    
    ai_consultant = AmberAIConsultant()
    
    budget_messages = [
        "Ищу подарок жене до 10000 рублей, покажите что есть",
        "Бюджет у меня 5 тысяч, что можете предложить?",
        "Хочу кольцо за 3000₽ максимум"
    ]
    
    for i, message in enumerate(budget_messages, 1):
        print(f"\n🧪 Бюджетный тест {i}:")
        print(f"👤 Сообщение: {message}")
        
        try:
            response = await ai_consultant.process_message(98765 + i, message)
            
            # Проверяем наличие товаров в ответе
            if any(keyword in response for keyword in ['₽', 'руб', '💰', '🛍️']):
                print("✅ Бюджет распознан, товары показаны")
            else:
                print("ℹ️ Бюджет не распознан или товары не подходят")
                
            print(f"🤖 Ответ: {response[:200]}{'...' if len(response) > 200 else ''}")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")


async def main():
    """Основная функция тестирования интеграции"""
    try:
        # Проверяем наличие всех необходимых переменных
        required_vars = [
            'OPENAI_API_KEY', 'MOYSKLAD_TOKEN', 
            'AMOCRM_SUBDOMAIN', 'AMOCRM_CLIENT_ID'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            print(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
            return
        
        # Запускаем тесты
        await test_ai_product_requests()
        await test_budget_parsing_integration()
        
        print("\n🎉 Все тесты интеграции завершены успешно!")
        
    except Exception as e:
        print(f"❌ Критическая ошибка тестирования: {e}")
        app_logger.error(f"Критическая ошибка интеграции: {e}")


if __name__ == "__main__":
    asyncio.run(main())