# Система управления магазином

Два Telegram-бота для полного цикла управления интернет-магазином.

## Боты

| Бот | Назначение | Ссылка |
|-----|------------|--------|
| **Shop Bot** | Магазин для покупателей | [@agrosna1b_bot](https://t.me/agrosna1b_bot) |
| **Owner Bot** | Управление складом | [@tophitboss_bot](https://t.me/tophitboss_bot) |

**Полная документация:** [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)

---

## Shop Bot — Магазин для покупателей

Каталог товаров, корзина, оформление заказов с интеграцией CDEK.

### Возможности

- **Каталог** — просмотр товаров с фото, категории, поиск
- **Корзина** — добавление, изменение количества, проверка остатков
- **Оформление** — телефон, выбор ПВЗ CDEK, PDF-счёт
- **AI-менеджер** — естественно-языковой интерфейс (OpenAI)

### Быстрый старт

```bash
# 1. Настроить .env
cp .env.example .env
# Заполнить TELEGRAM_BOT_TOKEN, GOOGLE_SHEETS_ID, и т.д.

# 2. Запустить
source .venv/bin/activate
python -m app.main
```

### Конфигурация (.env)

```bash
TELEGRAM_BOT_TOKEN=...
GOOGLE_SHEETS_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/path/to/service-account.json

# AI-менеджер (опционально)
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o

# CDEK доставка (опционально)
CDEK_DEMO_MODE=true  # Демо без API
# или реальный режим:
# CDEK_CLIENT_ID=...
# CDEK_CLIENT_SECRET=...

# Автосписание после заказа
AUTO_WRITE_SPISANIE=true
```

---

## Owner Bot — Управление складом

Приём товаров, управление каталогом, загрузка фото.

**Документация:** [owner_bot/README.md](./owner_bot/README.md)

### Возможности

- **Приход товара** — быстрый ввод "Название Цена Кол-во"
- **Просмотр склада** — все товары с пагинацией
- **Поиск товаров** — по SKU или названию
- **Операции с товарами** — списание, корректировка, архивация
- **Управление фото** — загрузка, анализ качества, улучшение
- **CRM** — управление клиентами, воронка продаж
- **Диагностика** — проверка подключений к Sheets и Drive

### Быстрый старт

```bash
cd owner_bot
cp .env.example .env
# Заполнить .env

source .venv/bin/activate
python -m app.main
```

---

## Сайт — React-каталог

React-приложение для отображения каталога товаров с интеграцией Google Sheets.

**Папка:** [sitemahorkaproject/](./sitemahorkaproject/)

### Архитектура

```
┌─────────────────┐     fetch JSON      ┌──────────────────┐
│   React App     │ ◄────────────────── │  Apps Script     │
│   (Vite)        │                     │  Web App         │
└─────────────────┘                     └────────┬─────────┘
                                                 │ читает
                                                 ▼
                                        ┌──────────────────┐
                                        │  Google Sheets   │
                                        │  лист "Склад"    │
                                        └──────────────────┘
```

### Быстрый старт (сайт)

```bash
cd sitemahorkaproject
npm install
cp .env.example .env
# Добавьте VITE_APPS_SCRIPT_URL в .env
npm run dev
```

---

## Google Sheets — Структура (v1.1)

### Лист "Склад"

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| SKU | Да | Уникальный ID товара |
| Наименование | Да | Название |
| Цена_руб | Да | Цена |
| Стартовый_остаток | Да | Начальный остаток |
| Внесено_всего | Авто | Формула SUMIF из Внесение |
| Списано_всего | Авто | Формула SUMIF из Списание |
| Остаток_расчет | Авто | Формула: Старт + Внесено - Списано |
| Фото_URL | Да | Ссылка на фото |
| Активен | Да | TRUE/FALSE (чекбокс) |
| Теги | Нет | Для категорий |
| Описание_кратко | Нет | Краткое описание |

### Листы "Внесение" и "Списание"

**Структура:** двухстрочные заголовки
- Row 1: Английские заголовки (для кода)
- Row 2: Русские подписи (для пользователя)
- Row 3+: Данные

**Колонки:** `date`, `operation_id`, `sku`, `name`, `qty`, `stock_before`, `stock_after`, `reason`, `source`, `actor_id`, `actor_username`, `note`

**Документация:** [docs/SHEETS_SPEC_V1.md](./docs/SHEETS_SPEC_V1.md)

---

## Docker

### Структура проекта для Docker

```
excel-telegram-bot-starter/
├── secrets/                          # Google Service Account JSON (общая папка)
│   └── meta-origin-483709-v3-xxx.json
├── docker-compose.yml                # Shop Bot
├── .env                              # Shop Bot config
├── owner_bot/
│   ├── docker-compose.yml            # Owner Bot
│   └── .env                          # Owner Bot config
└── ...
```

### Настройка secrets

1. Создайте папку `secrets/` в корне проекта:

```bash
mkdir -p secrets
```

2. Поместите JSON-файл сервисного аккаунта Google:

```bash
cp /path/to/your-service-account.json secrets/
```

3. Настройте пути в `.env` файлах:

**Shop Bot (`.env` в корне):**
```bash
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/run/secrets/your-service-account.json
```

**Owner Bot (`owner_bot/.env`):**
```bash
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/app/secrets/your-service-account.json
```

### Volumes в docker-compose

**Shop Bot (`docker-compose.yml`):**
```yaml
services:
  bot:
    volumes:
      - ./secrets:/run/secrets:ro   # Credentials (read-only)
      - ./data:/app/data            # Persistent data
```

**Owner Bot (`owner_bot/docker-compose.yml`):**
```yaml
services:
  owner-bot:
    volumes:
      - ./tmp:/app/tmp              # Temp files
      - ./data:/app/data            # Persistent data
      - ../secrets:/app/secrets     # Credentials (shared from root)
```

### Запуск

```bash
# Shop Bot (из корня)
docker compose up --build

# Owner Bot (из owner_bot/)
cd owner_bot
docker compose up --build
```

---

## Google Apps Script — API каталога

Web App для отдачи каталога на сайт + мониторинг, валидация, бэкапы.

**Код:** [`sitemahorkaproject/google-apps-script/Code.gs`](./sitemahorkaproject/google-apps-script/Code.gs)

### Функции

| Функция | Описание |
|---------|----------|
| `doGet()` | Web App — JSON каталог активных товаров |
| `dailyHealthCheck()` | Проверка данных + Telegram алерты |
| `dailyBackup()` | Копия листа "Склад" |
| `weeklyExportToDrive()` | CSV экспорт в Google Drive |
| `setupDataValidation()` | Data Validation правила |
| `setupConditionalFormatting()` | Цветовая индикация проблем |
| `initializeSystem()` | Полная инициализация (триггеры + всё) |

### Деплой

```bash
cd sitemahorkaproject/google-apps-script
clasp push --force
clasp deploy --description "vX.X"
```

Затем в Apps Script Editor запустить `initializeSystem()`.

### API Endpoint

```
https://script.google.com/macros/s/AKfycbzJ31qZN_j6opR-uEteEdZbo1w6GjXUyQWdr9Lmjp384jjrvyE7smmPqVQz2TMC12oS/exec
```

---

## Ссылки

- [Полная документация системы](./SYSTEM_OVERVIEW.md)
- [Документация Owner Bot](./owner_bot/README.md)
- [Руководство для клиента](./docs/CLIENT_GUIDE.md)
- [Google Sheets](https://docs.google.com/spreadsheets/d/1r9rpm7WF1tAjPud8DhpgszpPQNVhfforh1XXyKNuR9A)
