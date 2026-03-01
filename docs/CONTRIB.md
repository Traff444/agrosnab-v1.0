# Руководство для разработчиков

**Обновлено:** 2026-03-01

## Требования

- Node.js 18+
- npm 9+
- Python 3.11+ (для ботов)
- uv (Python package manager)
- Docker + Docker Compose (для деплоя ботов)

## Структура проекта

```
agrosnab-v1.0/
├── src/                    # React-фронтенд (Vite + TypeScript)
│   ├── App.tsx             # Главный компонент (лендинг)
│   ├── components/         # UI-компоненты
│   │   ├── Header.tsx      # Шапка сайта
│   │   ├── HeroSection.tsx # Героическая секция
│   │   ├── Footer.tsx      # Подвал
│   │   ├── ProductCard.tsx # Карточка товара
│   │   └── CountUp.tsx     # Анимация счётчиков
│   ├── lib/
│   │   └── catalog.ts      # Загрузка каталога из Apps Script
│   ├── index.css           # Tailwind + кастомные стили
│   └── main.tsx            # Точка входа React
├── app/                    # Shop Bot (Python / aiogram)
│   ├── main.py             # Точка входа бота
│   ├── config.py           # Настройки (pydantic-settings)
│   ├── sheets.py           # Google Sheets клиент
│   ├── keyboards.py        # Telegram-клавиатуры
│   ├── ai_manager.py       # OpenAI AI-менеджер
│   ├── cdek.py             # Интеграция СДЭК
│   ├── invoice.py          # Генерация PDF-счетов
│   ├── handlers/           # Обработчики команд
│   │   ├── start.py        # /start, deep links
│   │   ├── catalog.py      # Каталог товаров
│   │   ├── cart.py         # Корзина и чекаут
│   │   ├── ai.py           # AI-режим
│   │   ├── common.py       # Общие обработчики
│   │   └── navigation.py   # Навигация по страницам
│   ├── services/           # Бизнес-логика
│   │   ├── product_service.py
│   │   └── cart_service.py
│   └── storage/            # Хранение данных (SQLite)
│       ├── db.py           # Инициализация БД
│       ├── cart.py          # Корзина
│       ├── crm.py          # CRM-события
│       └── chat_history.py # История чата AI
├── owner_bot/              # Owner Bot (управление складом)
├── tests/                  # Тесты Shop Bot (pytest)
├── google-apps-script/     # Google Apps Script (каталог для сайта)
│   ├── Code.gs             # Основной код
│   └── migration.gs        # Миграция данных
├── docs/                   # Документация
├── data/                   # Runtime-данные (SQLite, счета)
├── secrets/                # Секреты (не коммитятся)
├── docker-compose.yml      # Docker для Shop Bot
├── Dockerfile              # Docker-образ Shop Bot
├── package.json            # Frontend-зависимости
├── requirements.txt        # Python-зависимости
├── pyproject.toml          # Конфигурация ruff, pytest
└── .github/workflows/      # CI/CD
    ├── ci.yml              # Lint + тесты (оба бота)
    └── deploy.yml          # Deploy сайта на GitHub Pages
```

## Настройка окружения

### Фронтенд (сайт)

1. Клонируйте репозиторий
2. Установите зависимости:
   ```bash
   npm install
   ```
3. Создайте файл `.env` на основе `.env.example`:
   ```bash
   cp .env.example .env
   ```
4. Добавьте URL Apps Script в `.env`:
   ```
   VITE_APPS_SCRIPT_URL=https://script.google.com/macros/s/xxx/exec
   ```

### Shop Bot (Python)

1. Создайте виртуальное окружение:
   ```bash
   uv venv && source .venv/bin/activate
   ```
2. Установите зависимости:
   ```bash
   uv pip install -r requirements.txt
   ```
3. Настройте `.env`:
   ```bash
   cp .env.example .env
   # Заполните TELEGRAM_BOT_TOKEN, GOOGLE_SHEETS_ID,
   # GOOGLE_SERVICE_ACCOUNT_JSON_PATH
   ```
4. Положите `service-account.json` в `secrets/`

### Owner Bot

```bash
cd owner_bot
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
# Заполните переменные окружения
```

## Разработка

### Запуск dev-сервера (фронтенд)

```bash
npm run dev
```

Сервер запустится на http://localhost:8300/

### Запуск Shop Bot (локально)

```bash
source .venv/bin/activate
python -m app.main
```

### Запуск Owner Bot (локально)

```bash
cd owner_bot
source .venv/bin/activate
python -m app.main
```

## Скрипты (npm)

| Команда | Описание |
|---------|----------|
| `npm run dev` | Запуск Vite dev-сервера с HMR (порт 8300) |
| `npm run build` | Production-сборка в `dist/` |
| `npm run preview` | Локальный просмотр production-сборки |
| `npm run lint` | Проверка ESLint |
| `npm run typecheck` | Проверка типов TypeScript (`tsc --noEmit`) |

## Скрипты (Python)

| Команда | Описание |
|---------|----------|
| `uv run pytest tests/ -v` | Запуск тестов Shop Bot |
| `uv run pytest tests/ --cov=app --cov-report=term-missing` | Тесты с покрытием |
| `ruff check app tests` | Линтер Python |
| `ruff format app tests` | Форматирование Python |
| `python -m app.main` | Запуск Shop Bot |

## Workflow перед коммитом

```bash
# Фронтенд
npm run typecheck && npm run lint && npm run build

# Shop Bot
ruff check app tests && ruff format --check app tests && uv run pytest tests/ -q

# Owner Bot
cd owner_bot && ruff check app tests && ruff format --check app tests && uv run pytest tests/ -q
```

### Pre-commit hooks

Проект использует pre-commit (`.pre-commit-config.yaml`):
- **ruff** -- линтер + авто-фикс
- **ruff-format** -- форматирование
- **trailing-whitespace** -- удаление пробелов
- **end-of-file-fixer** -- пустая строка в конце файла
- **check-yaml** -- валидация YAML
- **check-added-large-files** -- защита от больших файлов

Установка хуков:
```bash
pip install pre-commit
pre-commit install
```

## CI Pipeline

При push/PR в `main`/`master` автоматически запускается CI (`.github/workflows/ci.yml`):

| Job | Что проверяет |
|-----|---------------|
| `lint-shop-bot` | `ruff check` + `ruff format --check` для `app/` и `tests/` |
| `lint-owner-bot` | То же для `owner_bot/app/` и `owner_bot/tests/` |
| `test-shop-bot` | `pytest` для Shop Bot (~255 тестов) |
| `test-owner-bot` | `pytest` для Owner Bot |

Убедитесь, что все проверки проходят перед мержем.

## Переменные окружения

### Сайт (корень проекта)

| Переменная | Обязательная | Описание |
|------------|:------------:|----------|
| `VITE_APPS_SCRIPT_URL` | Да | URL Google Apps Script Web App для загрузки каталога |

**Формат URL:** `https://script.google.com/macros/s/{DEPLOYMENT_ID}/exec`

### Shop Bot (корень проекта)

| Переменная | Обязательная | Описание |
|------------|:------------:|----------|
| `TELEGRAM_BOT_TOKEN` | Да | Токен бота от @BotFather |
| `GOOGLE_SHEETS_ID` | Да | ID Google Sheets или полный URL |
| `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` | Да | Путь к JSON-файлу сервисного аккаунта |
| `OPENAI_API_KEY` | Нет | Ключ OpenAI для AI-менеджера |
| `OPENAI_MODEL` | Нет | Модель OpenAI (по умолчанию: `gpt-4o`) |
| `AUTO_WRITE_SPISANIE` | Нет | Авто-списание после заказа (`true`/`false`, по умолчанию: `true`) |
| `CDEK_DEMO_MODE` | Нет | Демо-режим СДЭК без API (`true`/`false`) |
| `CDEK_CLIENT_ID` | Нет | ID клиента СДЭК API |
| `CDEK_CLIENT_SECRET` | Нет | Секрет клиента СДЭК API |
| `CDEK_TEST_MODE` | Нет | Тестовый режим СДЭК API (`true`/`false`, по умолчанию: `true`) |
| `OWNER_TELEGRAM_IDS` | Нет | ID владельцев через запятую (для уведомлений) |
| `OWNER_BOT_TOKEN` | Нет | Токен бота управляющего (уведомления о заказах) |

### Owner Bot (owner_bot/)

| Переменная | Обязательная | Описание |
|------------|:------------:|----------|
| `TELEGRAM_BOT_TOKEN` | Да | Токен бота от @BotFather |
| `OWNER_TELEGRAM_IDS` | Да | ID владельцев через запятую |
| `GOOGLE_SHEETS_ID` | Да | ID Google Sheets |
| `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` | Да | Путь к JSON-файлу сервисного аккаунта |
| `CLOUDINARY_CLOUD_NAME` | Да | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Да | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Да | Cloudinary API secret |
| `PHOTO_MIN_SIZE` | Нет | Мин. размер фото (по умолчанию: 800) |
| `PHOTO_SHARPNESS_THRESHOLD` | Нет | Порог резкости (по умолчанию: 100.0) |
| `PHOTO_BRIGHTNESS_MIN` | Нет | Мин. яркость (по умолчанию: 40) |
| `PHOTO_BRIGHTNESS_MAX` | Нет | Макс. яркость (по умолчанию: 220) |
| `LOG_LEVEL` | Нет | Уровень логирования (по умолчанию: `INFO`) |
| `TIMEZONE` | Нет | Часовой пояс (по умолчанию: `Europe/Vilnius`) |
| `SENTRY_DSN` | Нет | DSN для Sentry мониторинга |
| `ENVIRONMENT` | Нет | Окружение: `production`/`staging`/`development` |

## Архитектура данных

### Загрузка каталога (фронтенд)

Файл `src/lib/catalog.ts` отвечает за:
- Fetch данных из Google Apps Script
- Кеширование в sessionStorage (TTL: 5 минут)
- Валидацию и нормализацию данных
- Fallback при ошибках

### Типы данных (фронтенд)

```typescript
interface Product {
  sku: string;           // Уникальный идентификатор
  name: string;          // Наименование
  descriptionShort: string;
  descriptionFull: string;
  priceRub: number;      // Цена в рублях
  stock: number;         // Остаток (Остаток_расчет)
  photoUrl: string;      // URL фото
  tags: string[];        // Теги
}
```

### Google Sheets структура

Лист "Склад" должен содержать колонки:
- SKU
- Наименование
- Описание_кратко
- Описание_полное
- Цена_руб
- Остаток_расчет
- Фото_URL
- Активен (TRUE/FALSE)
- Теги
- Вес_упаковки (опционально)

### SQLite (Shop Bot)

База: `data/bot.sqlite3` (автосоздается при первом запуске)

| Таблица | Назначение |
|---------|-----------|
| `cart_items` | Текущая корзина пользователя |
| `checkout_sessions` | Идемпотентность чекаута |
| `order_counter` | Порядковая нумерация ORD-000001 |
| `user_profiles` | Сохраненные телефон, ФИО, адрес |
| `user_orders` | История заказов для "Повторить заказ" |
| `user_mode` | AI/обычный режим |
| `chat_history` | История чата с AI-менеджером |
| `crm_events` | CRM-события (add_to_cart, checkout, order) |
| `crm_messages` | CRM-сообщения пользователей |

## Стилизация

- Tailwind CSS с кастомными цветами в `tailwind.config.js`
- Адаптивный дизайн (mobile-first)
- CSS-переменные для цветовой схемы

## Тестирование

### Запуск тестов (Shop Bot)

```bash
# Все тесты (~255 тестов)
uv run pytest tests/ -v

# С покрытием
uv run pytest tests/ --cov=app --cov-report=term-missing
```

### Запуск тестов (Owner Bot)

```bash
cd owner_bot

# Все тесты
uv run pytest tests/ -v

# С покрытием
uv run pytest tests/ --cov=app --cov-report=term-missing
```

### Изоляция тестов

Каждый тест использует собственную временную SQLite-базу через фикстуру `isolate_test_database` (см. `tests/conftest.py`). Это гарантирует независимость тестов.

### Ручные тест-кейсы (Shop Bot)

| Сценарий | Ожидание |
|----------|----------|
| Товар в наличии (stock > 0) | Кнопка "Получить прайс" |
| Товар не в наличии (stock = 0) | Бейдж в каталоге, "Нет в наличии" на сайте |
| Повторить заказ (есть история) | Товары из последнего заказа добавляются в корзину |
| Повторить заказ (нет истории) | Сообщение "У вас пока нет заказов" |
| Повторить заказ (товар закончился) | Товар пропущен, предупреждение показано |
| Сохраненный телефон при чекауте | Предлагает кнопку с прошлым номером |
| Невалидный телефон (не РФ) | Ошибка с примером формата |
| Уведомление управляющему | Заказ приходит в бот управляющего |
| Товар с тегом #hit | Бейдж "хит" в каталоге |
| Товар с тегом #sale | Бейдж "скидка" в каталоге (приоритет над #hit) |
| Товар с тегом #new | Бейдж "новинка" в каталоге |
| Товар с весом упаковки | Вес отображается в кнопке |
| Неактивный товар | Не отображается |
| Ошибка загрузки | Сообщение + кнопка "Попробовать снова" |
| Пустой каталог | "Товары скоро появятся" |
| Битая ссылка на фото | Placeholder изображение |

### Ручные тест-кейсы (Owner Bot)

| Сценарий | Ожидание |
|----------|----------|
| Приход товара: "Товар 500 10" | Парсинг: название, цена 500 руб, 10 шт. |
| Приход с весом: ввод "500" | Вес 500г сохраняется |
| Приход с весом: ввод "500г" | Вес 500г (суффикс удаляется) |
| Приход с весом > 100000 | Ошибка валидации (макс. 100кг) |
| Приход без веса: кнопка "Пропустить" | Вес = None |
| Списание 5 шт. | Остаток уменьшается, лог в "Списание" |
| Корректировка остатка | Лог во "Внесение" или "Списание" |
| Архивация с обнулением | Остаток -> 0, товар скрыт |
| Загрузка фото | Фото в Cloudinary, URL в Sheets |

## Зависимости проекта

### Frontend (package.json)

**Runtime:**
- react 18.3.1
- react-dom 18.3.1
- @supabase/supabase-js 2.57.4
- lucide-react 0.344.0

**DevDependencies:**
- vite 5.4.2
- typescript 5.5.3
- eslint 9.9.1
- tailwindcss 3.4.1
- autoprefixer 10.4.18
- postcss 8.4.35

### Python (requirements.txt)

**Shop Bot:**
- aiogram 3.6.0
- pydantic 2.7.4 + pydantic-settings 2.4.0
- google-api-python-client 2.139.0
- google-auth 2.33.0
- reportlab 4.2.2
- openai (опционально)
- httpx (для СДЭК)
- aiosqlite 0.20.0
- pytest 8+ / pytest-asyncio 0.23+

**Owner Bot:**
- aiogram 3.x
- google-api-python-client
- cloudinary
- pillow (обработка изображений)
- aiosqlite

## Конвенции кода

### Python
- Линтер: ruff (конфигурация в `pyproject.toml`)
- Формат: ruff format (двойные кавычки, пробелы)
- Длина строки: 100 символов
- Асинхронные тесты: `asyncio_mode = "auto"`
- Типы: аннотации из `__future__` (`from __future__ import annotations`)

### TypeScript
- Строгий режим (`tsconfig.app.json`)
- ESLint с плагинами react-hooks и react-refresh
- Стиль: Tailwind CSS utility classes
