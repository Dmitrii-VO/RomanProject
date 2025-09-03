# 🤖 Amber AI Consultant

**Интеллектуальный ИИ-консультант для автоматизации продаж янтарных украшений**

## 🎯 О проекте

Amber AI Consultant — это полностью автоматизированная система продаж, которая превращает обычный диалог с клиентом в персональный опыт покупки. Система использует современные технологии ИИ для понимания потребностей клиентов и автоматически проводит их через весь процесс заказа.

### ✨ Ключевые возможности

- **🧠 Интеллектуальный диалог**: Понимает естественную речь клиентов и адаптируется под их стиль общения
- **🔍 Умный подбор товаров**: Семантический поиск по каталогу с использованием OpenAI embeddings
- **🚀 Полная автоматизация заказов**: От первого сообщения до оплаты без участия менеджера
- **💳 Интеграция платежей**: Автоматическое выставление счетов через ЮKassa
- **📦 Расчет доставки**: Интеграция с Почтой России для точного расчета стоимости
- **📊 CRM интеграция**: Синхронизация с AmoCRM и МойСклад для управления продажами
- **🔄 Webhook обработка**: Автоматические уведомления об оплате и обновление статусов

### 📈 Бизнес-выгоды

- **⚡ Экономия времени**: Автоматизация до 80% рутинных задач менеджеров
- **📞 24/7 доступность**: Клиенты могут оформить заказ в любое время
- **🎯 Увеличение конверсии**: Персонализированный подход к каждому клиенту
- **💰 Снижение затрат**: Меньше нагрузка на операторов call-центра
- **📋 Прозрачная аналитика**: Полная история диалогов и метрики продаж

## 🏗️ Архитектура системы

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Telegram Bot  │────│  AI Consultant   │────│   OpenAI API    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │                        ▼                        │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Dialog   │    │ Order Automation │    │   Product Mgr   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │                        ▼                        │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│    AmoCRM       │────│  Payment System  │────│   MoysSklad     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                    ┌──────────────────┐
                    │     ЮKassa       │
                    └──────────────────┘
```

## 🚀 Быстрый старт (локально)

### Требования

- Python 3.8+
- pip
- Виртуальное окружение (рекомендуется)

### Установка

1. **Клонирование репозитория**
```bash
git clone https://github.com/your-repo/amber_ai_consultant.git
cd amber_ai_consultant
```

2. **Создание виртуального окружения**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

3. **Установка зависимостей**
```bash
pip install -r requirements.txt
```

4. **Настройка переменных окружения**

Создайте файл `.env` в корне проекта:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key
OpenAI_BASE_URL=https://api.openai.com/v1

# AI Parameters
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=500
AI_PRESENCE_PENALTY=0.6
AI_FREQUENCY_PENALTY=0.5

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# MoysSklad Integration
MOYSKLAD_LOGIN=admin@amberry
MOYSKLAD_PASSWORD=Amberry39
MOYSKLAD_API_URL=https://api.moysklad.ru/api/remap/1.2

# AmoCRM Integration
AMOCRM_ACCESS_TOKEN=your_amocrm_token
AMOCRM_REFRESH_TOKEN=your_refresh_token
AMOCRM_SUBDOMAIN=your_subdomain

# ЮKassa Payments
YUKASSA_SHOP_ID=your_shop_id
YUKASSA_SECRET_KEY=your_secret_key
YUKASSA_WEBHOOK_SECRET=your_webhook_secret

# Application Settings
DEBUG=True
LOG_LEVEL=INFO
```

5. **Запуск системы**
```bash
python main.py
```

### 🧪 Тестирование

Запустите интеграционные тесты:

```bash
python test_full_automation_scenarios.py
```

Ожидаемый результат:
```
✅ Сценарий 1: Заказ < 15000₽: ПРОЙДЕН
✅ Сценарий 2: Заказ ≥ 15000₽: ПРОЙДЕН  
✅ Сценарий 3: Общий запрос: ПРОЙДЕН
✅ Сценарий 4: Отмена заказа: ПРОЙДЕН
📊 Процент успеха: 100.0%
```

## 🐳 Деплой в продакшен

### Docker Compose (рекомендуется)

1. **Создание docker-compose.yml**
```yaml
version: '3.8'

services:
  amber-ai:
    build: .
    container_name: amber-ai-consultant
    restart: unless-stopped
    environment:
      - NODE_ENV=production
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: amber-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    
  nginx:
    image: nginx:alpine
    container_name: amber-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - amber-ai

volumes:
  redis_data:
```

2. **Dockerfile**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
```

3. **Запуск контейнеров**
```bash
docker-compose up -d
```

### VPS/Cloud.ru деплой

1. **Подготовка сервера**
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

2. **Настройка SSL (Let's Encrypt)**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

3. **Настройка systemd для автозапуска**

Создайте файл `/etc/systemd/system/amber-ai.service`:
```ini
[Unit]
Description=Amber AI Consultant
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/amber-ai-consultant
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Активация:
```bash
sudo systemctl enable amber-ai.service
sudo systemctl start amber-ai.service
```

4. **Мониторинг и логирование**

```bash
# Просмотр логов
docker-compose logs -f

# Мониторинг ресурсов
docker stats

# Проверка health-check
curl http://localhost:8000/health
```

## 📊 Мониторинг и аналитика

### Health Check endpoints

- `GET /health` - Проверка работоспособности системы
- `GET /webhook/yukassa/health` - Проверка webhook'ов ЮKassa
- `GET /metrics` - Метрики приложения (Prometheus format)

### Логирование

Все события системы логируются с разными уровнями:
- `INFO`: Обычные операции
- `WARNING`: Предупреждения и нестандартные ситуации  
- `ERROR`: Ошибки интеграций и обработки
- `DEBUG`: Детальная отладочная информация

Логи сохраняются в:
- Консоль (для разработки)
- Файл `logs/app.log` (для продакшена)

## 🔧 API Документация

После запуска системы документация Swagger доступна по адресу:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

### Основные endpoints

#### Webhook'и
- `POST /webhook/yukassa` - Обработка платежей от ЮKassa
- `POST /webhook/telegram` - Telegram Bot API

#### Управление
- `GET /health` - Health check
- `GET /metrics` - Метрики системы

## 🔍 Тестирование

### Интеграционные тесты

Система включает комплексные тесты всех сценариев:

```bash
# Запуск всех тестов
python test_full_automation_scenarios.py

# Тестирование конкретного сценария
python -m pytest tests/test_order_automation.py -v

# Тестирование платежей
python -m pytest tests/test_yukassa_integration.py -v
```

### Тестовые данные

Для тестирования используются:
- **Тестовый пользователь**: Анна Иванова (ID: 987654321)
- **Тестовые товары**: Кольца, браслеты, серьги различных ценовых категорий
- **Тестовая доставка**: СПб (индекс 190000)

## 🛠️ Разработка

### Структура проекта

```
amber_ai_consultant/
├── src/
│   ├── ai/                     # ИИ компоненты
│   │   ├── consultant_v2.py    # Основной ИИ консультант
│   │   ├── order_automation_manager.py  # Автоматизация заказов
│   │   └── context_manager.py  # Управление контекстом диалогов
│   ├── integrations/           # Внешние интеграции
│   │   ├── amocrm_client.py   # AmoCRM API
│   │   ├── moysklad_client.py # МойСклад API
│   │   └── telegram_bot.py    # Telegram Bot
│   ├── payments/              # Платежная система
│   │   ├── yukassa_client.py  # ЮKassa API
│   │   └── webhook_handler.py # Webhook обработчик
│   ├── catalog/               # Каталог товаров
│   │   └── product_manager.py # Управление товарами
│   └── utils/                 # Утилиты
│       └── logger.py          # Логирование
├── tests/                     # Тесты
├── data/                      # Данные (embeddings, cache)
├── logs/                      # Логи приложения
├── requirements.txt           # Зависимости Python
├── docker-compose.yml         # Docker Compose конфигурация
├── main.py                    # Точка входа
└── README.md                  # Документация
```

### Добавление новых интеграций

1. Создайте клиент в папке `src/integrations/`
2. Добавьте конфигурацию в `.env`
3. Интегрируйте в `consultant_v2.py`
4. Добавьте тесты в `tests/`

### Расширение функциональности ИИ

1. Обновите промпты в `src/ai/prompts.py`
2. Добавьте новые методы в `OrderAutomationManager`
3. Протестируйте через `test_full_automation_scenarios.py`

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs -f amber-ai`
2. Убедитесь в корректности `.env` файла
3. Проверьте доступность внешних API (OpenAI, MoysSklad, AmoCRM)
4. Запустите health check: `curl http://localhost:8000/health`

## 📄 Лицензия

Проект разработан для внутреннего использования компании.

---

**🚀 Готовы к запуску? Следуйте инструкциям выше и ваш ИИ-консультант будет готов обслуживать клиентов 24/7!**