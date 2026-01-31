# CRM Implementation Summary (v1.1 → v1.3)

**Дата реализации:** 2026-01-27

---

## Обзор

Реализована CRM-система для отслеживания клиентов через воронку продаж с интеграцией в Shop Bot и Owner Bot.

---

## Phase 1: Leads + Events + Funnel (v1.1)

### Что реализовано

**SQLite таблица `crm_events`:**
- Логирование всех событий пользователей
- Индексы для быстрого поиска по user_id и event_type
- Payload в JSON формате

**Функции в `app/cart_store.py`:**
- `log_crm_event()` — запись события
- `get_user_events()` — получение событий с фильтрами
- `get_user_stage()` — вычисление текущей стадии
- `compute_stage()` — логика повышения стадии (только вверх)
- `get_user_orders_count()` — подсчёт заказов
- `get_daily_stats()` — статистика за день
- `get_first_seen()` / `get_last_seen()` — временные метки

**Google Sheets интеграция в `app/sheets.py`:**
- `upsert_lead()` — создание/обновление лида
- `get_lead()` — получение лида по user_id
- `search_leads()` — поиск по запросу

**Интеграция в хендлеры Shop Bot:**
- `app/handlers/start.py` — событие `start`, создание лида
- `app/handlers/catalog.py` — события `catalog_view`, `product_view`, `search`
- `app/handlers/cart.py` — события `add_to_cart`, `checkout_started`, `order_created`

### Файлы изменены
- `app/cart_store.py` (CRM таблица и функции)
- `app/sheets.py` (Leads методы)
- `app/handlers/start.py`
- `app/handlers/catalog.py`
- `app/handlers/cart.py`
- `app/main.py` (передача sheets_client)

---

## Phase 2: Metrics + Lead Cards (v1.2)

### Что реализовано

**Owner Bot Sheets методы в `owner_bot/app/sheets.py`:**
- `get_leads()` — список лидов
- `get_lead_by_user_id()` — лид по ID
- `search_leads()` — поиск
- `update_lead_notes()` — обновление заметок
- `update_lead_tags()` — обновление тегов
- `get_funnel_stats()` — статистика воронки
- `get_orders_summary()` — сводка заказов

**CRM хендлер `owner_bot/app/handlers/crm.py`:**
- Главное меню CRM с 4 опциями
- Визуализация воронки с конверсиями
- Список последних лидов
- Карточка клиента с детальной информацией
- Поиск клиентов (FSM)
- Добавление заметок с таймстампом
- Управление тегами (toggle кнопки)
- Ежедневный отчёт

**Клавиатуры `owner_bot/app/keyboards.py`:**
- Добавлена кнопка "📊 CRM" в главное меню

### Файлы созданы/изменены
- `owner_bot/app/sheets.py` (CRM методы)
- `owner_bot/app/handlers/crm.py` (новый ~400 строк)
- `owner_bot/app/handlers/__init__.py` (регистрация роутера)
- `owner_bot/app/handlers/start.py` (welcome text)
- `owner_bot/app/keyboards.py` (CRM кнопка)

---

## Phase 3: Conversation Logging + AI Summaries (v1.3)

### Что реализовано

**SQLite таблица `crm_messages`:**
- Хранение сообщений с направлением (in/out)
- Тип сообщения (text, ai_response)
- Автоматическая обрезка до 2000 символов
- Индекс по user_id

**Функции в `app/cart_store.py`:**
- `log_crm_message()` — запись сообщения
- `get_user_messages()` — получение с фильтрами
- `get_user_messages_count()` — подсчёт
- `has_user_consent()` — проверка согласия
- `format_messages_for_ai()` — форматирование для контекста

**Интеграция в AI хендлер `app/handlers/ai.py`:**
- Логирование входящих сообщений (direction='in')
- Логирование исходящих AI-ответов (direction='out')
- Проверка согласия перед записью

**Owner Bot модуль `owner_bot/app/crm_db.py`:**
- `get_user_messages()` — чтение из общей БД
- `get_user_messages_count()`
- `format_messages_for_display()` — форматирование для Telegram
- `generate_ai_summary()` — генерация сводки через OpenAI

**Owner Bot CRM расширения:**
- Кнопка "📜 История" в карточке клиента
- Просмотр переписки с хронологией
- Кнопка "🧠 AI-сводка" (если настроен OpenAI)
- Генерация анализа через GPT-4o-mini

**Конфигурация `owner_bot/app/config.py`:**
- Добавлены `openai_api_key` и `openai_model`

### Файлы созданы/изменены
- `app/cart_store.py` (crm_messages таблица и функции)
- `app/handlers/ai.py` (логирование сообщений)
- `owner_bot/app/crm_db.py` (новый модуль)
- `owner_bot/app/handlers/crm.py` (история и AI-сводка)
- `owner_bot/app/config.py` (OpenAI настройки)

---

## Тестирование

### Тесты CRM (18 тестов)
```
tests/test_crm.py::test_log_crm_event
tests/test_crm.py::test_get_user_events_with_filter
tests/test_crm.py::test_get_user_stage
tests/test_crm.py::test_compute_stage_only_increases
tests/test_crm.py::test_get_user_orders_count
tests/test_crm.py::test_get_daily_stats
tests/test_crm.py::test_get_first_last_seen
tests/test_crm.py::test_full_customer_journey
tests/test_crm.py::test_crm_events_isolation
tests/test_crm.py::test_crm_events_table_created
tests/test_crm.py::test_crm_messages_table_created
tests/test_crm.py::test_log_crm_message
tests/test_crm.py::test_get_user_messages_with_direction_filter
tests/test_crm.py::test_get_user_messages_count
tests/test_crm.py::test_has_user_consent
tests/test_crm.py::test_format_messages_for_ai
tests/test_crm.py::test_crm_messages_isolation
tests/test_crm.py::test_crm_message_truncation
```

**Результат:** Все тесты пройдены

### CI Pipeline

Тесты автоматически запускаются через GitHub Actions:
- `.github/workflows/ci.yml` — lint + test для обоих ботов
- Запускается при push и PR

**Локальный запуск:**
```bash
# Shop Bot (из корня)
pytest tests/test_crm.py -v

# Owner Bot
cd owner_bot && pytest tests/ -v
```

---

## Воронка продаж

```
        🆕 new (1)
           │
           ▼ catalog_view / product_view / search
        👀 engaged (2)
           │
           ▼ add_to_cart
        🛒 cart (3)
           │
           ▼ checkout_started
        📝 checkout (4)
           │
           ▼ order_created (первый заказ)
        ✅ customer (5)
           │
           ▼ order_created (2+ заказов)
        🌟 repeat (6)
```

**Правило:** стадия только повышается, никогда не понижается.

---

## Настройка

### Переменные окружения (.env)

```env
# Уже настроено для Shop Bot:
OPENAI_API_KEY=sk-...

# Автоматически используется Owner Bot для AI-сводок
```

### Google Sheets

Создать лист "Leads" с колонками:
```
user_id | username | first_seen_at | last_seen_at | stage | orders_count | lifetime_value | last_order_id | consent_at | consent_version | phone | tags | notes
```

---

## Использование

### Shop Bot (клиенты)
1. Клиент нажимает /start → создаётся лид, логируется событие `start`
2. Просматривает каталог → событие `catalog_view`, стадия `engaged`
3. Добавляет в корзину → событие `add_to_cart`, стадия `cart`
4. Оформляет заказ → событие `order_created`, стадия `customer`
5. Все сообщения AI-режима логируются (при согласии)

### Owner Bot (владелец)
1. Нажать "📊 CRM" в главном меню
2. "📈 Воронка" — посмотреть конверсии
3. "👥 Последние лиды" — список клиентов
4. Нажать на клиента → карточка с действиями
5. "📜 История" → переписка
6. "🧠 AI-сводка" → анализ клиента

---

## Архитектура данных

```
┌─────────────────────────────────────────────────────────────┐
│                      SQLite (bot.sqlite3)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ crm_events  │  │ crm_messages│  │ cart_items, etc.    │  │
│  │ - user_id   │  │ - user_id   │  │                     │  │
│  │ - event_type│  │ - direction │  │                     │  │
│  │ - payload   │  │ - text      │  │                     │  │
│  │ - timestamp │  │ - timestamp │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ sync (при upsert_lead)
┌─────────────────────────────────────────────────────────────┐
│                   Google Sheets: "Leads"                     │
│  user_id | username | stage | orders_count | tags | notes   │
└─────────────────────────────────────────────────────────────┘
```

---

## Следующие шаги (опционально)

- [ ] Автоматические напоминания для брошенных корзин
- [ ] Сегментация клиентов по тегам
- [ ] Экспорт отчётов в Excel
- [ ] Интеграция с email/SMS рассылками
- [ ] Расширенная аналитика (LTV, retention)
