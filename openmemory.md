## Overview
- **Project**: `excel-telegram-bot-starter` — Telegram-магазин на `aiogram 3` с каталогом из Google Sheets, корзиной в SQLite и генерацией PDF-счёта.
- **Key flows**:
  - Каталог/поиск → добавление в корзину
  - Корзина → оформление (телефон + доставка) → PDF → запись заказа в Google Sheets (+ опционально списание)
  - Опционально: AI-менеджер (OpenAI tool calling) для поиска/добавления/подсказок
- **Docs**:
  - `BUSINESS_LOGIC.md` — подробное описание бизнес‑логики и сценариев

## Architecture (high level)
- **Entry point**: `app/main.py` (инициализация `Bot`, `Dispatcher`, сервисов, DB, регистрация хендлеров).
- **Handlers**: `app/handlers/*`
  - `catalog.py`: каталог, категории, поиск (FSM только для запроса поиска)
  - `cart.py`: корзина + checkout (FSM для телефона/СДЭК/ручной доставки)
  - `ai.py`: AI-режим (catch-all message handler — регистрируется последним)
- **Storage**:
  - SQLite: `app/cart_store.py` (`/app/data/bot.sqlite3`) — корзина, режим AI, история чата, checkout sessions (идемпотентность)
  - Google Sheets: `app/sheets.py` — чтение каталога/настроек, запись заказов, списание, batch-update остатков
- **Services**:
  - `app/services/product_service.py`: кеш TTL для товаров/настроек/категорий
  - `app/services/cart_service.py`: бизнес-логика корзины + форматирование
- **Docs**: `README.md`, `DOCUMENTATION.md`

## CDEK delivery selection (current implementation)
- **Client**: `app/cdek.py`
  - OAuth token cache
  - `search_cities(query)`
  - `get_pvz_list(city_code)`
- **Keyboards**: `app/keyboards.py`
  - `city_select_kb`, `pvz_select_kb` (пагинация), `delivery_confirm_kb`
- **Checkout FSM**: `app/handlers/cart.py`
  - `phone` → (если CDEK включен) `city_input` → `city_select` → `pvz_select` → `cdek:confirm` → финализация
  - fallback: `delivery_manual` (если CDEK выключен/ошибка/пользователь выбрал вручную)
- **Demo mode**: `CDEK_DEMO_MODE=true` — включает демо‑заглушку без реальных запросов (работает даже без `CDEK_CLIENT_ID/SECRET`).
  - Демо флоу: ввод города → выбор города кнопками → список ПВЗ с пагинацией → выбор ПВЗ → подтверждение → оформление
  - Доставка сохраняется строкой: `ПВЗ СДЭК: <адрес> (<код>)`
- **Env vars** (optional): `CDEK_CLIENT_ID`, `CDEK_CLIENT_SECRET`, `CDEK_TEST_MODE`, `CDEK_DEMO_MODE`

## User Defined Namespaces
- [Leave blank - user populates]
