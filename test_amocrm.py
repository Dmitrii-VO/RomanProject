#!/usr/bin/env python3
"""
Тестирование интеграции с AmoCRM
"""
import asyncio
import os
from dotenv import load_dotenv

from utils.logger import setup_logger, app_logger
from src.integrations.amocrm_client import AmoCRMClient
from src.integrations.token_manager import TokenManager


async def test_token_manager():
    """Тестирование менеджера токенов"""
    print("\n🔐 Тестирование TokenManager...")
    
    token_manager = TokenManager()
    
    # Проверяем статус токенов
    status = token_manager.get_token_status()
    print(f"📊 Статус токенов: {status}")
    
    # Если есть токены, показываем их статус
    if status.get('amocrm', {}).get('has_tokens'):
        access_token = token_manager.get_amocrm_access_token()
        refresh_token = token_manager.get_amocrm_refresh_token()
        is_expired = token_manager.is_amocrm_token_expired()
        
        print(f"✅ Access token: {'✓' if access_token else '✗'}")
        print(f"✅ Refresh token: {'✓' if refresh_token else '✗'}")
        print(f"⏰ Токен истек: {'Да' if is_expired else 'Нет'}")
    else:
        print("❌ Токены AmoCRM отсутствуют")


async def test_amocrm_connection():
    """Тестирование подключения к AmoCRM"""
    print("\n🔗 Тестирование подключения к AmoCRM...")
    
    client = AmoCRMClient()
    
    # Проверяем наличие токенов
    if not client.access_token:
        print("❌ Отсутствует access_token для AmoCRM")
        print("💡 Для получения токенов необходимо пройти OAuth авторизацию")
        return False
    
    print(f"✅ Access token присутствует: {client.access_token[:20]}...")
    
    # Пытаемся сделать тестовый запрос
    try:
        result = await client._make_request("GET", "account")
        if result:
            print("✅ Подключение к AmoCRM успешно!")
            print(f"📊 Аккаунт: {result.get('name', 'Неизвестно')}")
            return True
        else:
            print("❌ Ошибка подключения к AmoCRM")
            return False
    except Exception as e:
        print(f"❌ Ошибка тестирования AmoCRM: {e}")
        return False


async def test_create_contact_and_lead():
    """Тестирование создания контакта и сделки"""
    print("\n👤 Тестирование создания контакта и сделки...")
    
    client = AmoCRMClient()
    
    if not client.access_token:
        print("❌ Нет токена для тестирования")
        return
    
    # Тестовые данные
    test_telegram_id = 999999999
    test_name = "Тестовый клиент"
    
    try:
        # Создаем контакт и сделку
        contact_id, lead_id = await client.get_or_create_contact_and_lead(
            test_telegram_id, test_name
        )
        
        if contact_id and lead_id:
            print(f"✅ Создан контакт ID: {contact_id}")
            print(f"✅ Создана сделка ID: {lead_id}")
            
            # Тестируем добавление примечания
            await client.add_note_to_lead(
                lead_id, 
                "🤖 Тестовое примечание от бота\nЭто проверка интеграции с Telegram"
            )
            print("✅ Добавлено примечание к сделке")
            
            # Тестируем логирование переписки
            await client.log_conversation(
                test_telegram_id,
                "Привет! Хочу купить янтарные украшения",
                "Здравствуйте! Рада приветствовать вас в нашем магазине. Какие украшения вас интересуют?"
            )
            print("✅ Переписка залогирована в AmoCRM")
            
            # Тестируем создание задачи
            await client.escalate_to_manager(
                test_telegram_id, 
                "Тестовая эскалация от бота"
            )
            print("✅ Создана задача для менеджера")
            
            return True
        else:
            print("❌ Ошибка создания контакта или сделки")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования создания контакта: {e}")
        return False


async def test_full_integration():
    """Полное тестирование интеграции"""
    print("\n🔄 Полное тестирование интеграции AmoCRM...\n")
    
    success_count = 0
    total_tests = 3
    
    # Тест 1: TokenManager
    try:
        await test_token_manager()
        success_count += 1
    except Exception as e:
        print(f"❌ Ошибка тестирования TokenManager: {e}")
    
    # Тест 2: Подключение к AmoCRM
    try:
        if await test_amocrm_connection():
            success_count += 1
    except Exception as e:
        print(f"❌ Ошибка тестирования подключения: {e}")
    
    # Тест 3: Создание контакта и сделки
    try:
        if await test_create_contact_and_lead():
            success_count += 1
    except Exception as e:
        print(f"❌ Ошибка тестирования создания сущностей: {e}")
    
    # Результаты
    print(f"\n📊 Результаты тестирования:")
    print(f"✅ Успешно: {success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("🎉 Все тесты прошли успешно!")
        print("✅ Интеграция с AmoCRM работает корректно")
    else:
        print("⚠️ Некоторые тесты не прошли")
        print("💡 Проверьте настройки и токены AmoCRM")


def setup_oauth_instructions():
    """Выводит инструкции по настройке OAuth для AmoCRM"""
    print("\n🔧 Инструкции по настройке AmoCRM OAuth:\n")
    
    print("1. Зайдите в амoCRM -> Настройки -> Интеграции -> Разработчикам")
    print("2. Создайте приложение с правами:")
    print("   - Контакты: создание, редактирование, просмотр")
    print("   - Сделки: создание, редактирование, просмотр")
    print("   - Примечания: создание, просмотр")
    print("   - Задачи: создание, редактирование")
    
    print("\n3. Получите данные приложения:")
    print("   - Client ID")
    print("   - Client Secret")
    print("   - Redirect URI")
    
    print("\n4. Обновите .env файл:")
    print("   AMOCRM_CLIENT_ID=ваш_client_id")
    print("   AMOCRM_CLIENT_SECRET=ваш_client_secret")
    print("   AMOCRM_REDIRECT_URI=https://amberry.ru/callback")
    print("   AMOCRM_SUBDOMAIN=ваш_поддомен")
    
    print("\n5. Получите код авторизации через URL:")
    client_id = os.getenv("AMOCRM_CLIENT_ID", "ваш_client_id")
    subdomain = os.getenv("AMOCRM_SUBDOMAIN", "ваш_поддомен")
    redirect_uri = os.getenv("AMOCRM_REDIRECT_URI", "https://amberry.ru/callback")
    
    oauth_url = (
        f"https://{subdomain}.amocrm.ru/oauth2/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=crm"
    )
    
    print(f"OAuth URL: {oauth_url}")
    
    print("\n6. После получения кода обмените его на токены через API")
    print("   Подробнее: https://www.amocrm.ru/developers/content/oauth/step-by-step")


async def main():
    """Основная функция тестирования"""
    
    # Загрузка переменных окружения
    load_dotenv()
    
    # Настройка логирования
    setup_logger()
    
    app_logger.info("🧪 Запуск тестирования AmoCRM интеграции")
    
    print("🧪 Тестирование интеграции с AmoCRM")
    print("=" * 50)
    
    # Проверяем наличие базовой конфигурации
    required_vars = ["AMOCRM_SUBDOMAIN", "AMOCRM_CLIENT_ID", "AMOCRM_CLIENT_SECRET"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        setup_oauth_instructions()
        return
    
    # Запуск тестирования
    await test_full_integration()
    
    app_logger.info("🏁 Тестирование AmoCRM завершено")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Тестирование прервано пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        exit(1)