# 🏪 Amber AI Consultant - ИИ Консультант Янтарного Магазина

Интеллектуальный помощник для автоматизации процесса консультирования клиентов интернет-магазина янтарных украшений с возможностью эскалации к живому сотруднику.

## 🎯 Основные функции

- 🤖 **ИИ консультирование** - автоматические ответы на вопросы о янтарных украшениях
- 💎 **Подбор украшений** - помощь в выборе изделий по критериям и бюджету
- 📦 **Управление заказами** - интеграция с МойСклад для оформления покупок
- 💳 **Обработка платежей** - интеграция с ЮKassa
- 📈 **CRM интеграция** - автоматическое ведение клиентской базы в AmoCRM
- 🚀 **Эскалация** - передача сложных случаев живым консультантам
- 📊 **Логирование** - полная запись всех диалогов для аналитики

## 🏗 Архитектура

```
Клиент → Telegram Bot ↔ ИИ Консультант ↔ CRM ↔ Склад ↔ Оплата
```

### Компоненты:
- **Telegram Bot** (Telethon) - взаимодействие с клиентами
- **ИИ движок** (OpenAI GPT) - обработка запросов и генерация ответов
- **МойСклад API** - управление каталогом и заказами
- **AmoCRM API** - ведение клиентской базы и сделок
- **ЮKassa API** - обработка платежей
- **FastAPI** - веб API и webhook'и

## 🚀 Быстрый старт

### 1. Клонирование и настройка

```bash
git clone git@github.com:Dmitrii-VO/RomanProject.git
cd RomanProject
```

### 2. Создание виртуального окружения

```bash
python3 -m virtualenv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и настройте API ключи:

```bash
cp .env.example .env
# Отредактируйте .env файл с вашими API ключами
```

### 5. Тестирование окружения

```bash
python test_hello.py
```

### 6. Запуск ИИ консультанта

```bash
python main.py
```

### 7. Запуск веб API (опционально)

```bash
python -m uvicorn src.api.main:app --reload
```

## ⚙️ Конфигурация

### Переменные окружения (.env):

```env
# OpenAI
OPENAI_API_KEY=ваш_ключ_openai
OpenAI_BASE_URL=https://api.openai.com/v1

# Telegram
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash

# МойСклад
MOYSKLAD_TOKEN=ваш_токен
MOYSKLAD_LOGIN=ваш_логин
MOYSKLAD_PASSWORD=ваш_пароль
MOYSKLAD_BASE_URL=https://api.moysklad.ru/api/remap/1.2

# AmoCRM
AMOCRM_CLIENT_ID=ваш_client_id
AMOCRM_CLIENT_SECRET=ваш_client_secret
AMOCRM_REDIRECT_URI=https://example.com/callback
AMOCRM_AUTH_CODE=код_авторизации

# ЮKassa
YUKASSA_SHOP_ID=ваш_shop_id
YUKASSA_SECRET_KEY=ваш_secret_key

# Настройки ИИ
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=500
AI_PRESENCE_PENALTY=0.6
AI_FREQUENCY_PENALTY=0.5

# Приложение
DEBUG=True
LOG_LEVEL=INFO
```

## 📁 Структура проекта

```
amber_ai_consultant/
├── src/                    # Исходный код
│   ├── api/               # FastAPI приложение
│   ├── bot/               # Telegram Bot
│   ├── ai/                # ИИ консультант
│   ├── integrations/      # Внешние API
│   └── database/          # База данных
├── tests/                 # Тесты
├── logs/                  # Файлы логов
├── utils/                 # Утилиты
├── knowledge_map/         # Карты знаний проекта
├── .env                   # Переменные окружения
├── main.py               # Главный файл запуска
└── requirements.txt      # Зависимости
```

## 🔧 API Документация

После запуска FastAPI сервера документация доступна по адресам:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Основные эндпоинты:

- `POST /chat` - общение с ИИ консультантом
- `POST /payment/create` - создание платежа
- `POST /webhook/yukassa` - webhook для платежей
- `GET /health` - проверка здоровья сервиса

## 📊 Логирование

Система логирования сохраняет данные в три файла:
- `logs/bot.log` - основные логи приложения
- `logs/conversations.log` - все диалоги с клиентами
- `logs/errors.log` - только ошибки

## 🧪 Тестирование

Запуск тестов:

```bash
# Тест окружения
python test_hello.py

# Unit тесты
pytest tests/unit/

# Интеграционные тесты
pytest tests/integration/
```

## 🚀 Деплой

### Docker (будет добавлено)

```bash
docker build -t amber-ai-consultant .
docker run -d --env-file .env amber-ai-consultant
```

### Systemd сервис (Linux)

Создайте файл `/etc/systemd/system/amber-ai-consultant.service`:

```ini
[Unit]
Description=Amber AI Consultant
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/amber_ai_consultant
Environment=PATH=/path/to/amber_ai_consultant/venv/bin
ExecStart=/path/to/amber_ai_consultant/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🤝 Участие в разработке

1. Fork репозитория
2. Создайте ветку для новой функции (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add amazing feature'`)
4. Отправьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 👥 Авторы

- **Claude AI** - Первоначальная разработка
- **Dmitrii-VO** - Владелец проекта

## 📞 Поддержка

По вопросам и предложениям создавайте Issues в репозитории GitHub.

---

🔶 **Amber AI Consultant** - Ваш умный помощник в мире янтарных украшений!