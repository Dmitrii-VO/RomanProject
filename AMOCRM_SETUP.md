# Настройка AmoCRM интеграции

## Шаг 1: Создание приложения в AmoCRM

1. Зайдите в ваш аккаунт AmoCRM
2. Перейдите в **Настройки** → **Интеграции** → **Разработчикам**
3. Нажмите **"Создать интеграцию"**
4. Заполните данные приложения:
   - Название: "Янтарный ИИ Консультант"
   - Описание: "Telegram бот для консультации клиентов"
   - Redirect URI: `https://amberry.ru/callback`

## Шаг 2: Настройка прав доступа

Выберите следующие права:
- **Контакты**: создание, редактирование, просмотр
- **Сделки**: создание, редактирование, просмотр  
- **Примечания**: создание, просмотр
- **Задачи**: создание, редактирование
- **Пользователи**: просмотр (для назначения задач)

## Шаг 3: Получение учетных данных

После создания приложения скопируйте:
- **Client ID**
- **Client Secret**

## Шаг 4: Обновление .env файла

Обновите ваш `.env` файл:

```env
# AmoCRM API настройки
AMOCRM_SUBDOMAIN=ваш_поддомен  # например: amber-jewelry
AMOCRM_CLIENT_ID=
AMOCRM_CLIENT_SECRET=ваш_client_secret
AMOCRM_REDIRECT_URI=https://amberry.ru/callback
AMOCRM_BASE_URL=https://ваш_поддомен.amocrm.ru
```

## Шаг 5: Первичная авторизация

1. Откройте в браузере URL для авторизации:
```
https://ваш_поддомен.amocrm.ru/oauth2/authorize?client_id=ВАШИ_CLIENT_ID&response_type=code&redirect_uri=https://amberry.ru/callback&scope=crm
```

2. Разрешите доступ к вашему аккаунту AmoCRM

3. Скопируйте код авторизации из URL после редиректа:
```
https://amberry.ru/callback?code=ПОЛУЧЕННЫЙ_КОД&referer=...
```

4. Создайте скрипт для обмена кода на токены:

```python
import requests
import json

# Данные из .env
client_id = "ваш_client_id"
client_secret = "ваш_client_secret"
redirect_uri = "https://amberry.ru/callback"
authorization_code = "КОД_ИЗ_ПРЕДЫДУЩЕГО_ШАГА"
subdomain = "ваш_поддомен"

# Обмен кода на токены
url = f"https://{subdomain}.amocrm.ru/oauth2/access_token"
data = {
    "client_id": client_id,
    "client_secret": client_secret,
    "grant_type": "authorization_code",
    "code": authorization_code,
    "redirect_uri": redirect_uri
}

response = requests.post(url, json=data)
tokens = response.json()

print("Access Token:", tokens.get("access_token"))
print("Refresh Token:", tokens.get("refresh_token"))
print("Expires In:", tokens.get("expires_in"))
```

## Шаг 6: Добавление токенов в систему

1. Добавьте полученные токены в `.env`:
```env
AMOCRM_ACCESS_TOKEN=полученный_access_token
AMOCRM_REFRESH_TOKEN=полученный_refresh_token
```

2. Или используйте TokenManager для программного сохранения:
```python
from src.integrations.token_manager import TokenManager

token_manager = TokenManager()
token_manager.save_amocrm_tokens(
    access_token="полученный_access_token",
    refresh_token="полученный_refresh_token",
    expires_in=86400  # время жизни в секундах
)
```

## Шаг 7: Настройка полей AmoCRM

В коде AmoCRM клиента необходимо обновить ID полей на реальные:

```python
# В методе create_contact() замените:
"field_id": 123456,  # TODO: ID поля Telegram ID
"field_id": 123457,  # TODO: ID поля телефона

# В методе create_lead() замените:
"status_id": 123456,  # TODO: ID статуса "Новая заявка"  
"field_id": 123458,  # TODO: ID поля "Источник"
```

Для получения ID полей используйте API запросы:
- Поля контактов: `GET /api/v4/contacts/custom_fields`
- Поля сделок: `GET /api/v4/leads/custom_fields`
- Статусы сделок: `GET /api/v4/leads/pipelines`

## Шаг 8: Тестирование

Запустите тест интеграции:
```bash
python test_amocrm.py
```

Если все настроено правильно, вы увидите:
```
✅ Успешно: 3/3
🎉 Все тесты прошли успешно!
✅ Интеграция с AmoCRM работает корректно
```

## Автоматическое обновление токенов

Система автоматически обновляет токены при истечении срока действия. Токены сохраняются в файл `tokens.json` и синхронизируются с `.env` файлом.

## Дополнительные ресурсы

- [Документация AmoCRM API](https://www.amocrm.ru/developers/)
- [Руководство по OAuth 2.0](https://www.amocrm.ru/developers/content/oauth/step-by-step)
- [Управление правами доступа](https://www.amocrm.ru/developers/content/oauth/scopes)