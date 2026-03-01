# Операционные процедуры (Runbook)

**Обновлено:** 2026-03-01

---

## Деплой сайта (GitHub Pages)

Сайт автоматически деплоится через GitHub Actions при push в `main`.

**Workflow:** `.github/workflows/deploy.yml`

**Процесс:**
1. Push в `main` -> запускается GitHub Actions
2. Setup Node.js 18 + `npm ci`
3. Сборка: `npm run build`
4. Upload `dist/` -> GitHub Pages

**Конфигурация:**
- `.env.production` содержит `VITE_APPS_SCRIPT_URL` для production
- Base path: `/` (настроен в `vite.config.ts`)
- Dev-сервер: порт 8300

**Проверка статуса:**
- Actions: `https://github.com/[owner]/[repo]/actions`
- Сайт: `https://[owner].github.io/[repo]/`

### Netlify (альтернатива)

Конфигурация в `netlify.toml`:
- Build command: `npm run build`
- Publish directory: `dist`
- SPA fallback: `/* -> /index.html` (status 200)

### Ручной деплой

```bash
npm run build
# Загрузите содержимое dist/ на хостинг
```

---

## CI Pipeline

Автоматическая проверка при push/PR в `main`/`master`.

**Workflow:** `.github/workflows/ci.yml`

**Jobs:**

| Job | Описание |
|-----|----------|
| `lint-shop-bot` | ruff check + format для `app/` и `tests/` |
| `lint-owner-bot` | ruff check + format для `owner_bot/app/` и `owner_bot/tests/` |
| `test-shop-bot` | pytest для Shop Bot (~255 тестов) |
| `test-owner-bot` | pytest для Owner Bot |

**Запуск локально:**
```bash
# Shop Bot
ruff check app/ && ruff format --check app/ && uv run pytest tests/ -q

# Owner Bot
cd owner_bot
ruff check app/ && ruff format --check app/ && uv run pytest tests/ -q
```

---

## Деплой ботов (Docker)

### Shop Bot

```bash
# Из корня проекта
docker compose up --build -d

# Логи
docker compose logs -f bot

# Остановка
docker compose down
```

**Docker-образ:** Python 3.11-slim + fonts-dejavu-core (для русского текста в PDF).

**Volumes:**
- `./secrets:/run/secrets:ro` -- сервисный аккаунт Google (read-only)
- `./data:/app/data` -- SQLite база + PDF-счета

**Перезапуск:** `restart: unless-stopped` (автоматический)

### Owner Bot

```bash
cd owner_bot

# Запуск
docker compose up --build -d

# Логи
docker compose logs -f owner-bot

# Остановка
docker compose down
```

### Оба бота одновременно

```bash
# Терминал 1 (корень)
docker compose up --build -d

# Терминал 2 (owner_bot)
cd owner_bot && docker compose up --build -d
```

---

## Мониторинг

### Проверка работоспособности сайта

1. **Сайт загружается** -- откройте URL, проверьте отображение
2. **Каталог загружается** -- в разделе "Ассортимент" должны быть товары
3. **Кеш работает** -- повторная загрузка не делает запрос (DevTools -> Network)

### Логи ошибок (фронтенд)

Ошибки логируются в `console.error`:
- `VITE_APPS_SCRIPT_URL не настроен` -- отсутствует переменная окружения
- `Apps Script error: ...` -- ошибка от Google Sheets
- `Ошибка загрузки каталога: ...` -- сетевая ошибка

### Логи Shop Bot

```bash
# Просмотр логов в реальном времени
docker compose logs -f bot

# Поиск ошибок
docker compose logs bot 2>&1 | grep ERROR
```

Формат логов: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

Подавлены шумные логи от `httpx` и `httpcore` (уровень WARNING).

### Логи Owner Bot

```bash
# Просмотр логов в реальном времени
docker compose logs -f owner-bot

# Уровень DEBUG для отладки
LOG_LEVEL=DEBUG docker compose up
```

**Уровни логирования:**
- `DEBUG` -- детальная информация для отладки
- `INFO` -- стандартные события (по умолчанию)
- `WARNING` -- предупреждения
- `ERROR` -- ошибки

### Sentry (Owner Bot)

Если настроен `SENTRY_DSN`, ошибки автоматически отправляются в Sentry.
Переменная `ENVIRONMENT` определяет окружение (`production`/`staging`/`development`).

---

## Частые проблемы

### Каталог не загружается

**Симптом:** Бесконечный спиннер или ошибка на сайте.

**Диагностика:**
```bash
curl -sL "$VITE_APPS_SCRIPT_URL" | head -200
```

**Возможные причины:**
1. Неверный URL Apps Script -> проверьте `.env` / `.env.production`
2. Apps Script не задеплоен -> передеплойте в Google Apps Script
3. CORS -> Apps Script должен быть доступен "Anyone" (не "Anyone with Google Account")

### Товары не отображаются

**Симптом:** "Товары скоро появятся"

**Проверьте:**
1. В Google Sheets есть товары с `Активен = TRUE`
2. Колонки называются правильно (SKU, Наименование, Цена_руб и т.д.)
3. Apps Script возвращает `items` в JSON

### Фото не загружаются

**Симптом:** Placeholder вместо фото

**Причины:**
1. Неверный URL в колонке `Фото_URL`
2. Фото недоступно (приватный Google Drive)
3. CORS-ограничения

**Решение:** Используйте публичные URL. Cloudinary рекомендуется для Owner Bot.

### Вес упаковки не отображается

**Симптом:** Вес не показывается в кнопке товара.

**Проверьте:**
1. Колонка `Вес_упаковки` существует в листе "Склад"
2. Значение не пустое и > 0
3. Формат: число в граммах (например, 500 для 500г)

**Примечание:** weight=0 намеренно не отображается (считается как "не указан").

### Бот не запускается

**Симптом:** Контейнер перезапускается в цикле.

**Диагностика:**
```bash
docker compose logs bot | tail -50
```

**Частые причины:**
1. Невалидный `TELEGRAM_BOT_TOKEN` -> проверьте через `curl https://api.telegram.org/bot<TOKEN>/getMe`
2. Файл `service-account.json` не найден -> проверьте путь в `GOOGLE_SERVICE_ACCOUNT_JSON_PATH`
3. Неверный `GOOGLE_SHEETS_ID` -> проверьте ID или URL таблицы

### Ошибка валидации веса в Owner Bot

**Симптом:** "Введите целое число (в граммах)"

**Причины:**
1. Введено не число
2. Вес <= 0
3. Вес > 100000 (100кг -- максимум)

**Решение:** Введите число от 1 до 100000 или нажмите "Пропустить".

### Сессия intake истекла

**Симптом:** "Сессия истекла" при продолжении ввода.

**Причина:** TTL сессии 24 часа, бот перезапустился, или SQLite база недоступна.

**Решение:** Начните приход заново.

### Уведомления о заказах не приходят

**Симптом:** Управляющий не получает уведомления о новых заказах.

**Проверьте:**
1. `OWNER_BOT_TOKEN` указан в `.env` Shop Bot
2. `OWNER_TELEGRAM_IDS` содержит правильные ID через запятую
3. Управляющий ранее писал `/start` в бот управляющего

**Логи:**
```bash
docker compose logs bot 2>&1 | grep "notify"
```

### Счет-фактура не отправляется

**Симптом:** Заказ оформлен, но PDF не приходит.

**Причина:** Директория `/app/data/invoices/` не создалась или нет прав на запись.

**Решение:** Проверьте Docker volume `./data:/app/data`. Директория создается автоматически через `os.makedirs`.

### "Повторить заказ" не работает

**Симптом:** "У вас пока нет заказов"

**Причина:** История заказов сохраняется с момента добавления фичи. Предыдущие заказы не в `user_orders`.

**Решение:** Оформите новый заказ -- он сохранится для повторения.

---

## SQLite (Shop Bot)

База: `data/bot.sqlite3` (автосоздается при первом запуске).

**Таблицы:**

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

**Просмотр содержимого (через Docker):**
```bash
docker compose exec bot python -c "
import sqlite3; db=sqlite3.connect('/app/data/bot.sqlite3')
for t in db.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall():
    print(t[0], db.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0])
"
```

**Просмотр локально:**
```bash
sqlite3 data/bot.sqlite3 ".tables"
sqlite3 data/bot.sqlite3 "SELECT COUNT(*) FROM cart_items"
```

---

## Rollback

### Откат кода (сайт)

```bash
git revert HEAD
git push origin main
# GitHub Actions автоматически задеплоит
```

### Откат кода (боты)

```bash
git revert HEAD
docker compose up --build -d
```

### Откат данных Google Sheets

Данные в Google Sheets -- используйте историю версий:
1. Файл -> История версий -> Смотреть историю версий
2. Выберите нужную версию
3. Восстановите

### Откат SQLite (Shop Bot)

```bash
# Остановить бот
docker compose down

# Восстановить из бэкапа (если есть)
cp data/bot.sqlite3.backup data/bot.sqlite3

# Запустить бот
docker compose up -d
```

### Откат Owner Bot базы

```bash
cd owner_bot

# Остановить бот
docker compose down

# Восстановить из бэкапа
cp data/owner_bot.db.backup data/owner_bot.db

# Запустить бот
docker compose up -d
```

---

## Google Apps Script

### Передеплой Apps Script

1. Google Sheets -> Extensions -> Apps Script
2. Deploy -> Manage deployments
3. Создайте новый deployment или обновите существующий
4. Скопируйте новый URL в `.env` / `.env.production`
5. Для GitHub Pages: закоммитьте `.env.production` и push в `main`

### Код Apps Script

Файл: `google-apps-script/Code.gs`

При изменениях в структуре Google Sheets обновите маппинг колонок в `COLUMNS`.

---

## Безопасность

### Проверка npm-уязвимостей

```bash
npm audit
npm audit fix
```

### Ротация секретов

| Секрет | Где обновить |
|--------|-------------|
| Telegram Bot Token | @BotFather -> Revoke current token; обновить `.env` |
| Google Service Account | Google Cloud Console -> IAM -> Service Accounts -> Keys |
| Cloudinary | Cloudinary Console -> Settings -> Security |
| OpenAI API Key | OpenAI Platform -> API Keys |

После ротации:
1. Обновите `.env`
2. Перезапустите ботов: `docker compose up --build -d`

### Файлы, которые не должны попасть в Git

Проверьте `.gitignore`:
- `.env` (все кроме `.env.example` и `.env.production`)
- `secrets/` (все кроме `README.txt`)
- `data/` (все кроме `README.txt`)
- `*.sqlite3`, `*.db`

---

## Бэкапы

### Google Sheets
Автоматическая история версий Google. Дополнительно рекомендуется периодический экспорт.

### SQLite базы
```bash
# Shop Bot
cp data/bot.sqlite3 data/bot.sqlite3.backup

# Owner Bot
cp owner_bot/data/owner_bot.db owner_bot/data/owner_bot.db.backup
```

Рекомендуется автоматизировать через cron на production-сервере.

---

## Контакты

При критических проблемах:
- Shop Bot: @mahoorka_bot
- Owner Bot: @tophitboss_bot
