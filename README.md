# Система управления магазином

Два Telegram-бота для полного цикла управления интернет-магазином.

## Боты

| Бот | Назначение | Ссылка |
|-----|------------|--------|
| **Shop Bot** | Магазин для покупателей | [@mahoorka_bot](https://t.me/mahoorka_bot) |
| **Owner Bot** | Управление складом | [@tophitboss_bot](https://t.me/tophitboss_bot) |

**Полная документация:** [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)

---

## Shop Bot — Магазин для покупателей

Каталог товаров, корзина, оформление заказов с интеграцией CDEK.

### Возможности

- **Каталог** — 1 колонка, 8 товаров на странице, бейджи (#hit 🔥, #sale 🏷️, #new 🆕), категории, поиск
- **Корзина** — добавление, изменение количества, счётчик на кнопке, лимит 20 позиций
- **Оформление** — телефон, выбор ПВЗ CDEK, подтверждение заказа, PDF-счёт
- **AI-менеджер** — естественно-языковой интерфейс (OpenAI, выключен по умолчанию)

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

**Деплой:** Автоматический через GitHub Actions → GitHub Pages. Для production используется `.env.production` с `VITE_APPS_SCRIPT_URL`.

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
| Теги | Нет | Категории + бейджи (#hit, #sale, #new) |
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

## Changelog

### v1.7 (2026-02-01)
- **feat:** Редизайн каталога — 1 колонка + бейджи
  - Переход на 1-колоночный layout (8 товаров на странице)
  - Новый формат кнопок: `🔥 Название — 1 000 ₽`
  - Бейджи через теги в Google Sheets: `#hit` → 🔥, `#sale` → 🏷️, `#new` → 🆕
  - Автоматический бейдж ⛔️ для товаров с `stock=0`
  - Кнопка страницы показывает toast при нажатии
  - Добавлен `CATALOG_PAGE_SIZE=8` в конфиг
  - 19 unit-тестов для форматирования каталога

### v1.6 (2026-02-01)
- **feat:** UX-улучшения каталога и корзины
  - Каталог: сетка 6 товаров (2×3) вместо поштучного просмотра
  - Счётчик корзины на кнопках ("🧺 Корзина (3)")
  - Экран подтверждения заказа перед оплатой
  - Лимит корзины: максимум 20 позиций
  - Убрана двойная навигация (только inline-меню)
  - AI-режим выключен по умолчанию
  - Сообщение "Спасибо за заказ" после оформления

### v1.5 (2026-01-31)
- **fix:** GitHub Pages деплой — убран пустой `env:` блок из deploy.yml, добавлен `.env.production`
- **feat:** TTL-кэш товаров в Owner Bot (5 мин) — снижает нагрузку на Google Sheets API
- **fix:** Исправлено 25 failing tests в shop_bot
- **ci:** Расширен CI pipeline для обоих ботов (lint + test)
- **refactor:** Улучшены type hints в storage модулях

### v1.4 (2026-01-31)
- **fix:** Исправлена навигация по каталогу — кнопки "След. ➡️" и "⬅️ Пред." теперь работают корректно
  - Изменён порядок операций: сначала отправляется новое сообщение, потом удаляется старое
  - Добавлено логирование ошибок отправки фото

### v1.3
- CRM система: воронка продаж, история сообщений, AI-сводки

### v1.2
- Owner Bot: управление складом, загрузка фото

### v1.1
- Листы "Внесение" и "Списание" с двухстрочными заголовками
- Автосписание при заказе

### v1.0
- Shop Bot: каталог, корзина, оформление заказов
- Интеграция с Google Sheets и CDEK

---

## Ссылки

- [Полная документация системы](./SYSTEM_OVERVIEW.md)
- [Документация Owner Bot](./owner_bot/README.md)
- [Руководство для клиента](./docs/CLIENT_GUIDE.md)
- Google Sheets: используйте `GOOGLE_SHEETS_ID` из `.env`
