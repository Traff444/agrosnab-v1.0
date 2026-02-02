# Руководство для разработчиков

## Требования

- Node.js 18+
- npm 9+
- Python 3.11+ (для ботов)
- uv (Python package manager)

## Настройка окружения

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

## Разработка

### Запуск dev-сервера

```bash
npm run dev
```

Сервер запустится на http://localhost:5173/agrosnab/

### Скрипты

| Команда | Описание |
|---------|----------|
| `npm run dev` | Запуск Vite dev-сервера с HMR |
| `npm run build` | Production-сборка в `dist/` |
| `npm run preview` | Локальный просмотр production-сборки |
| `npm run lint` | Проверка ESLint |
| `npm run typecheck` | Проверка типов TypeScript (`tsc --noEmit`) |

### Workflow перед коммитом

```bash
npm run typecheck && npm run lint && npm run build
```

### CI при PR

При создании PR автоматически запускается CI pipeline:
- **Сайт:** typecheck, lint, build
- **Shop Bot:** ruff check, ruff format, pytest
- **Owner Bot:** ruff check, ruff format, pytest

Убедитесь, что все проверки проходят перед мержем.

## Переменные окружения

### Сайт (корень проекта)

| Переменная | Обязательная | Описание |
|------------|--------------|----------|
| `VITE_APPS_SCRIPT_URL` | Да | URL Google Apps Script Web App для загрузки каталога |

**Формат URL:** `https://script.google.com/macros/s/{DEPLOYMENT_ID}/exec`

### Shop Bot (корень проекта)

| Переменная | Обязательная | Описание |
|------------|--------------|----------|
| `TELEGRAM_BOT_TOKEN` | Да | Токен бота от @BotFather |
| `GOOGLE_SHEETS_ID` | Да | ID Google Sheets или полный URL |
| `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` | Да | Путь к JSON-файлу сервисного аккаунта |
| `OPENAI_API_KEY` | Нет | Ключ OpenAI для AI-менеджера |
| `OPENAI_MODEL` | Нет | Модель OpenAI (по умолчанию: gpt-4o) |
| `AUTO_WRITE_SPISANIE` | Нет | Авто-списание после заказа (true/false) |
| `CDEK_DEMO_MODE` | Нет | Демо-режим CDEK без API (true/false) |
| `CDEK_CLIENT_ID` | Нет | ID клиента CDEK API |
| `CDEK_CLIENT_SECRET` | Нет | Секрет клиента CDEK API |
| `CDEK_TEST_MODE` | Нет | Тестовый режим CDEK API (true/false) |

### Owner Bot (owner_bot/)

| Переменная | Обязательная | Описание |
|------------|--------------|----------|
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
| `LOG_LEVEL` | Нет | Уровень логирования (по умолчанию: INFO) |
| `TIMEZONE` | Нет | Часовой пояс (по умолчанию: Europe/Vilnius) |
| `SENTRY_DSN` | Нет | DSN для Sentry мониторинга |
| `ENVIRONMENT` | Нет | Окружение: production/staging/development |

## Архитектура данных

### Загрузка каталога

Файл `src/lib/catalog.ts` отвечает за:
- Fetch данных из Google Apps Script
- Кеширование в sessionStorage (TTL: 5 минут)
- Валидацию и нормализацию данных
- Fallback при ошибках

### Типы данных

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
  packageWeight?: number; // Вес упаковки в граммах
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

## Стилизация

- Tailwind CSS с кастомными цветами в `tailwind.config.js`
- Адаптивный дизайн (mobile-first)
- CSS-переменные для цветовой схемы

## Тестирование

### Запуск тестов (Shop Bot)

```bash
# Все тесты (50 тестов)
uv run pytest app/tests/ -v

# Тесты форматирования каталога
uv run pytest app/tests/test_catalog_format.py -v

# С покрытием
uv run pytest app/tests/ --cov=app --cov-report=term-missing
```

### Запуск тестов (Owner Bot)

```bash
cd owner_bot

# Все тесты
uv run pytest tests/ -v

# Тесты intake flow (16 тестов)
uv run pytest tests/test_intake_flow.py -v

# Тесты складских операций
uv run pytest tests/test_stock_*.py -v

# С покрытием
uv run pytest tests/ --cov=app --cov-report=term-missing
```

### CI Pipeline

При push/PR автоматически запускается проверка обоих ботов:

```bash
# Shop Bot
ruff check app/ && ruff format --check app/ && pytest app/tests/

# Owner Bot
cd owner_bot && ruff check app/ && ruff format --check app/ && pytest tests/
```

### Ручные тест-кейсы (Shop Bot)

| Сценарий | Ожидание |
|----------|----------|
| Товар в наличии (stock > 0) | Кнопка "Получить прайс" |
| Товар не в наличии (stock = 0) | Бейдж ⛔️ в каталоге, "Нет в наличии" на сайте |
| Товар с тегом #hit | Бейдж 🔥 в каталоге |
| Товар с тегом #sale | Бейдж 🏷️ в каталоге (приоритет над #hit) |
| Товар с тегом #new | Бейдж 🆕 в каталоге |
| Товар с весом упаковки | Вес отображается в кнопке (например: "Товар 50г — 500 ₽") |
| Неактивный товар | Не отображается |
| Ошибка загрузки | Сообщение + кнопка "Попробовать снова" |
| Пустой каталог | "Товары скоро появятся" |
| Битая ссылка на фото | Placeholder изображение |

### Ручные тест-кейсы (Owner Bot)

| Сценарий | Ожидание |
|----------|----------|
| Приход товара: "Товар 500 10" | Парсинг: название, цена 500₽, 10 шт. |
| Приход с весом: ввод "500" | Вес 500г сохраняется |
| Приход с весом: ввод "500г" | Вес 500г (суффикс удаляется) |
| Приход с весом > 100000 | Ошибка валидации (макс. 100кг) |
| Приход без веса: кнопка "Пропустить" | Вес = None |
| Списание 5 шт. | Остаток уменьшается, лог в "Списание" |
| Корректировка остатка | Лог во "Внесение" или "Списание" |
| Архивация с обнулением | Остаток → 0, товар скрыт |
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

### Python (pyproject.toml)

**Shop Bot:**
- aiogram 3.x
- google-api-python-client
- openai (опционально)

**Owner Bot:**
- aiogram 3.x
- google-api-python-client
- cloudinary
- pillow (обработка изображений)
- aiosqlite (хранение сессий)
