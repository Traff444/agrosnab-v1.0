# 📦 Telegram Бот Оптового Магазина

## Техническая документация

### Обзор системы

Telegram-бот для оптовой торговли с интеграцией Google Sheets и AI-ассистентом на базе OpenAI GPT-4o.

---

## 🏗️ Архитектура

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Telegram      │────▶│   Bot (Python)  │────▶│  Google Sheets  │
│   Клиенты       │◀────│   aiogram 3.x   │◀────│   (Склад, Заказы)│
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ SQLite   │ │ OpenAI   │ │ PDF      │
              │ (Корзина)│ │ GPT-4o   │ │ (Счета)  │
              └──────────┘ └──────────┘ └──────────┘
```

---

## 📁 Структура проекта

```
excel-telegram-bot-starter/
├── app/
│   ├── main.py          # Главный файл бота, все хендлеры
│   ├── config.py        # Настройки из .env
│   ├── sheets.py        # Работа с Google Sheets API
│   ├── cart_store.py    # SQLite: корзина, история чата, режим AI
│   ├── keyboards.py     # Inline и Reply клавиатуры
│   ├── ai_manager.py    # OpenAI интеграция с tool calling
│   ├── invoice.py       # Генерация PDF счетов
│   ├── utils.py         # Вспомогательные функции
│   ├── handlers/        # Обработчики команд
│   │   ├── start.py     # /start и меню
│   │   ├── catalog.py   # Каталог и навигация
│   │   ├── cart.py      # Корзина и checkout
│   │   └── ai.py        # AI-менеджер
│   ├── services/        # Бизнес-логика
│   │   ├── cart_service.py    # Операции с корзиной
│   │   └── product_service.py # Операции с товарами
│   └── storage/         # Модули хранения данных
│       └── ...          # SQLite persistence
├── .github/
│   └── workflows/
│       ├── ci.yml       # CI: lint + test для обоих ботов
│       └── deploy.yml   # CD: GitHub Pages для сайта
├── docker-compose.yml   # Docker конфигурация
├── Dockerfile           # Образ Python 3.11
├── requirements.txt     # Зависимости
├── .env                 # Переменные окружения (не в git!)
└── secrets/
    └── service_account.json  # Google сервисный аккаунт
```

---

## 🔄 CI/CD

### CI Pipeline (`.github/workflows/ci.yml`)

Запускается при push и PR:
- **Shop Bot:** `ruff check`, `ruff format --check`, `pytest`
- **Owner Bot:** `ruff check`, `ruff format --check`, `pytest`

### CD Pipeline (`.github/workflows/deploy.yml`)

Автоматический деплой сайта на GitHub Pages при push в `main`.

---

## 🔧 Конфигурация (.env)

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GOOGLE_SHEETS_ID=your_google_sheets_id
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/run/secrets/service_account.json
OPENAI_API_KEY=sk-...
AUTO_WRITE_SPISANIE=true

# (опционально) СДЭК (выбор ПВЗ кнопками)
# CDEK_CLIENT_ID=...
# CDEK_CLIENT_SECRET=...
# CDEK_TEST_MODE=true
#
# Демо режим (без реальных запросов). Если включён и нет кредов — бот использует демо-данные:
# CDEK_DEMO_MODE=true
```

---

## 📊 Структура Google Sheets

### Лист "Склад"
| Колонка | Описание |
|---------|----------|
| SKU | Уникальный артикул товара (PRD-001) |
| Наименование | Название товара |
| Описание_кратко | Краткое описание |
| Цена_руб | Цена в рублях |
| Стартовый_остаток | Начальный остаток |
| Списано_всего | Списанное количество |
| Остаток_расчет | Формула: =Стартовый - Списано |
| Фото_URL | Ссылка на фото (Google Drive) |
| Активен | "да" для активных товаров |
| Теги | Категории через запятую |

### Лист "Заказы"
| Колонка | Описание |
|---------|----------|
| ID | Номер заказа (ORD-XXXXX) |
| Дата | Дата и время оформления |
| User_ID | Telegram ID покупателя |
| Телефон | Контактный телефон |
| Статус | "Счет выставлен" |
| Сумма | Итоговая сумма заказа |
| Доставка | СДЭК / ПВЗ |
| Адрес | Адрес доставки |
| Позиции | SKU:qty через ; |
| Файл | Имя PDF счета |

### Лист "Списание" (v1.1)

**Структура:** Row 1 = английские заголовки, Row 2 = русские подписи, Row 3+ = данные

| Колонка | Заголовок | Русская подпись | Описание |
|---------|-----------|-----------------|----------|
| A | date | Дата | Дата и время операции (ISO) |
| B | operation_id | ID операции | Уникальный ID |
| C | sku | Артикул | SKU товара |
| D | name | Название | Название товара |
| E | qty | Количество | Количество списано |
| F | stock_before | Было на складе | Остаток до операции |
| G | stock_after | Стало на складе | Остаток после операции |
| H | reason | Причина | order/damage/gift/correction |
| I | source | Источник | shop_order/owner_manual |
| J | actor_id | ID актора | Telegram ID |
| K | actor_username | Имя актора | Username |
| L | note | Примечание | Комментарий |

### Лист "Настройки"
| Ключ | Значение |
|------|----------|
| Мин. сумма заказа | 5000 |
| Компания | ООО "Ваша компания" |
| ИНН | 1234567890 |
| ... | ... |

---

## 🤖 AI-ассистент

### Возможности
- Понимает естественную речь ("добавь 5 золотой")
- Автоматически находит товары по частичным названиям
- Добавляет товары в корзину
- Показывает наличие и цены
- Помогает оформить заказ

### Инструменты (Tools)
| Tool | Описание |
|------|----------|
| `list_all_products` | Получить весь каталог с SKU |
| `search_products` | Поиск по названию/тегам |
| `add_to_cart` | Добавить товар в корзину |
| `show_cart` | Показать содержимое корзины |
| `checkout_hint` | Инструкция по оформлению |

### Модель
- GPT-4o (настраивается в config.py)
- История диалога: последние 20 сообщений

---

## 🗂️ SQLite База данных

Путь: `/app/data/bot.sqlite3`

### Таблицы
```sql
-- Корзина
CREATE TABLE cart_items (
    user_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL,
    PRIMARY KEY (user_id, sku)
);

-- Режим AI
CREATE TABLE user_mode (
    user_id INTEGER PRIMARY KEY,
    ai_mode INTEGER NOT NULL DEFAULT 0
);

-- История чата (для AI контекста)
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM события (Phase 1)
CREATE TABLE crm_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM сообщения (Phase 3)
CREATE TABLE crm_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    direction TEXT NOT NULL,      -- 'in' или 'out'
    message_type TEXT NOT NULL,   -- 'text', 'ai_response', etc.
    text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📊 CRM Система (v1.1-v1.3)

### Обзор
CRM-модуль для отслеживания клиентов через воронку продаж с логированием событий и сообщений.

### Архитектура
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Shop Bot      │────▶│   SQLite        │────▶│   Owner Bot     │
│   (Клиенты)     │     │   (События,     │     │   (CRM меню)    │
│                 │     │    Сообщения)   │     │                 │
└────────┬────────┘     └─────────────────┘     └────────┬────────┘
         │                                               │
         ▼                                               ▼
┌─────────────────┐                           ┌─────────────────┐
│  Google Sheets  │                           │  OpenAI GPT     │
│  (Лиды)         │                           │  (AI-сводки)    │
└─────────────────┘                           └─────────────────┘
```

### Воронка продаж (6 стадий)
```
🆕 new → 👀 engaged → 🛒 cart → 📝 checkout → ✅ customer → 🌟 repeat
```

**Правило:** стадия только повышается, никогда не понижается.

### События CRM
| Событие | Стадия | Описание |
|---------|--------|----------|
| `start` | new | Первый /start |
| `catalog_view` | engaged | Просмотр каталога |
| `product_view` | engaged | Просмотр товара |
| `search` | engaged | Поиск |
| `add_to_cart` | cart | Добавление в корзину |
| `checkout_started` | checkout | Начало оформления |
| `order_created` | customer/repeat | Заказ оформлен |

### Google Sheets: Лист "Leads"
| Колонка | Описание |
|---------|----------|
| user_id | Telegram ID |
| username | @username |
| first_seen_at | Первый визит |
| last_seen_at | Последний визит |
| stage | Текущая стадия |
| orders_count | Количество заказов |
| lifetime_value | Сумма всех заказов |
| consent_at | Дата согласия |
| phone | Телефон |
| tags | Метки (vip, problem, etc) |
| notes | Заметки менеджера |

### Owner Bot: CRM меню
- 📈 **Воронка** — визуализация с конверсиями
- 👥 **Последние лиды** — список клиентов
- 🔍 **Поиск клиента** — по ID/телефону/имени
- 📋 **Отчёт за день** — статистика
- 👤 **Карточка клиента** — детальная информация
  - 📝 Заметка — добавить заметку
  - 🏷 Теги — управление метками
  - 📜 История — просмотр переписки
  - 🧠 AI-сводка — анализ диалога через GPT

---

## 🚀 Запуск

### Docker (рекомендуется)
```bash
# Сборка и запуск
docker compose up --build -d

# Логи
docker compose logs -f bot

# Остановка
docker compose down
```

### Локально
```bash
pip install -r requirements.txt
python -m app.main
```

---

## 📱 Функциональность бота

### Главное меню (постоянные кнопки)
- 🗂 Каталог — сетка товаров (6 на странице)
- 🧺 Корзина (N) — просмотр и редактирование, счётчик позиций
- 🤖 AI Менеджер — выключен по умолчанию
- 📋 Меню — дополнительные опции

### Каталог
- Сетка товаров 6 штук (2×3) на странице
- Навигация ◀️ / ▶️ между страницами
- Кнопка "В корзину" для каждого товара
- Показ цены и остатка
- Только inline-меню (без дублирования)

### Корзина
- Список товаров с ценами
- ➕ / ➖ кнопки для изменения количества
- 🗑 Удаление товара
- Минимальная сумма заказа
- **Счётчик на кнопке:** "🧺 Корзина (3)" показывает количество позиций
- **Лимит:** максимум 20 позиций в корзине

### Оформление заказа
1. Ввод телефона
2. Ввод адреса доставки
3. **Экран подтверждения заказа** — сводка с кнопками "✅ Подтвердить" / "❌ Отменить"
4. Генерация PDF счета
5. Запись в Google Sheets
6. Автоматическое списание со склада
7. **Сообщение "Спасибо за заказ!"** после успешного оформления

---

## 🔄 Автоматическое списание

При оформлении заказа (если `AUTO_WRITE_SPISANIE=true`):
1. Запись в лист "Списание"
2. Обновление колонки "Списано_всего" в листе "Склад"
3. Остаток пересчитывается автоматически

---

## 🖼️ Фото товаров

Поддерживаемые форматы URL:
- Google Drive: автоконвертация `/file/d/.../view` → `/uc?export=view&id=...`
- Dropbox: замена `dl=0` на `dl=1`
- Прямые ссылки на изображения

---

## 📝 Логирование

Отладочные сообщения:
```
[DEBUG] any_text called, text=...
[DEBUG] ai_mode=True
[AI DEBUG] Sending request to gpt-4o with N messages
[AI DEBUG] Tool call: add_to_cart({"sku": "PRD-001", "qty": 5})
```

---

## 🛠️ Частые проблемы

### Корзина пуста после добавления через AI
- Очистите историю чата: `DELETE FROM chat_history`
- Проверьте что AI использует правильные SKU

### Фото не отображается
- Проверьте что файл в Google Drive доступен "Для всех по ссылке"

### AI не отвечает
- Проверьте `OPENAI_API_KEY` в `.env`
- Проверьте логи на ошибки

### Кнопка "След. ➡️" в каталоге не работала (исправлено v1.4)
**Причина:** При навигации сначала удалялось сообщение, потом отправлялось новое фото. Если отправка фото падала — callback оставался без ответа.

**Решение:** Изменён порядок операций — сначала отправляется новое сообщение с фото, потом удаляется старое. Fallback на edit_text если фото недоступно.

---

## 📦 Зависимости

```
aiogram==3.6.0          # Telegram Bot API
pydantic==2.7.4         # Валидация данных
aiosqlite==0.20.0       # Async SQLite
google-api-python-client # Google Sheets API
openai>=1.50.0          # OpenAI GPT
reportlab==4.2.2        # PDF генерация
```

---

## 📋 Дополнительная документация

- [Аудит проекта (2026-02-25)](./docs/plans/2026-02-25-pre-delivery-audit.md) — полный аудит перед передачей клиенту
- [Оценка проекта](./PROJECT_ASSESSMENT.md) — комплексная оценка: код, бизнес, маркетинг
- [Бизнес-логика](./BUSINESS_LOGIC.md) — описание бизнес-процессов
- [Обзор системы](./SYSTEM_OVERVIEW.md) — архитектура и конфигурация
- [CRM](./CRM_IMPLEMENTATION.md) — реализация CRM-системы
- [Руководство для клиента](./docs/CLIENT_GUIDE.md) — инструкция для клиента

---

## 📄 Лицензия

MIT License
