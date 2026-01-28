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
- **Поиск товаров** — по SKU или названию
- **Управление фото** — загрузка, анализ качества, улучшение
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

## Google Sheets — Структура

Таблица должна содержать лист **"Склад"** с колонками:

| Колонка | Обязательно | Описание |
|---------|-------------|----------|
| SKU | Да | Уникальный ID товара |
| Наименование | Да | Название |
| Цена_руб | Да | Цена |
| Остаток_расчет | Да | Текущий остаток |
| Фото_URL | Да | Ссылка на фото |
| Активен | Да | да/нет |
| Теги | Нет | Для категорий |
| Описание_кратко | Нет | Краткое описание |

---

## Docker

```bash
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
