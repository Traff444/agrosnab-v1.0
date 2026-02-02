# Операционные процедуры (Runbook)

## GitHub Pages деплой (Сайт)

Сайт автоматически деплоится через GitHub Actions при push в `main`.

**Workflow:** `.github/workflows/deploy.yml`

**Процесс:**
1. Push в `main` → запускается GitHub Actions
2. Сборка: `npm run build`
3. Деплой: `dist/` → GitHub Pages

**Конфигурация:**
- `.env.production` содержит `VITE_APPS_SCRIPT_URL` для production
- Base path: `/agrosnab/` (настроен в `vite.config.ts`)

**Проверка статуса:**
- Actions: https://github.com/[owner]/[repo]/actions
- Сайт: https://[owner].github.io/agrosnab/

---

## CI Pipeline

Автоматическая проверка при push/PR.

**Workflow:** `.github/workflows/ci.yml`

**Проверки для обоих ботов:**
- `ruff check` — линтер Python
- `ruff format --check` — проверка форматирования
- `pytest` — запуск тестов

**Запуск локально:**
```bash
# Shop Bot (50 тестов)
ruff check app/ && ruff format --check app/ && uv run pytest app/tests/ -v

# Owner Bot
cd owner_bot
ruff check app/ && ruff format --check app/ && uv run pytest tests/ -v
```

**Ожидаемые результаты:**
- Shop Bot: 50 passed
- Owner Bot: 16+ passed (intake flow tests)

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

### Owner Bot

```bash
# Из owner_bot/
cd owner_bot
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

## Деплой (Сайт)

### Production-сборка

```bash
npm run build
```

Результат в папке `dist/`. Деплой статических файлов на хостинг.

### Vercel / Netlify

1. Подключите репозиторий
2. Build command: `npm run build`
3. Output directory: `dist`
4. Environment variables: добавьте `VITE_APPS_SCRIPT_URL`

### Ручной деплой

```bash
npm run build
# Загрузите содержимое dist/ на сервер
```

## Мониторинг

### Проверка работоспособности

1. **Сайт загружается** — откройте URL, проверьте отображение
2. **Каталог загружается** — в разделе "Ассортимент" должны быть товары
3. **Кеш работает** — повторная загрузка не делает запрос (DevTools → Network)

### Логи ошибок

Ошибки логируются в `console.error`:
- `VITE_APPS_SCRIPT_URL не настроен` — отсутствует переменная окружения
- `Apps Script error: ...` — ошибка от Google Sheets
- `Ошибка загрузки каталога: ...` — сетевая ошибка

### Логи Owner Bot

```bash
# Просмотр логов в реальном времени
docker compose logs -f owner-bot

# Уровень DEBUG для отладки
LOG_LEVEL=DEBUG docker compose up
```

**Уровни логирования:**
- `DEBUG` — детальная информация для отладки
- `INFO` — стандартные события (по умолчанию)
- `WARNING` — предупреждения
- `ERROR` — ошибки

## Частые проблемы

### Каталог не загружается

**Симптом:** Бесконечный спиннер или ошибка

**Диагностика:**
```bash
curl -sL "$VITE_APPS_SCRIPT_URL"
```

**Возможные причины:**
1. Неверный URL Apps Script → проверьте `.env`
2. Apps Script не задеплоен → передеплойте в Google Apps Script
3. CORS — Apps Script должен быть доступен "Anyone"

### Товары не отображаются

**Симптом:** "Товары скоро появятся"

**Проверьте:**
1. В Google Sheets есть товары с `Активен = TRUE`
2. Колонки называются правильно (SKU, Активен, и т.д.)
3. Apps Script возвращает `items` в JSON

### Фото не загружаются

**Симптом:** Placeholder вместо фото

**Причины:**
1. Неверный URL в колонке `Фото_URL`
2. Фото недоступно (приватный Google Drive)
3. CORS-ограничения

**Решение:** Используйте публичные URL (Cloudinary рекомендуется)

### Вес упаковки не отображается

**Симптом:** Вес не показывается в кнопке товара

**Проверьте:**
1. Колонка `Вес_упаковки` существует в листе "Склад"
2. Значение не пустое и > 0
3. Формат: число в граммах (например, 500 для 500г)

**Примечание:** weight=0 намеренно не отображается (считается как "не указан")

### Ошибка валидации веса в Owner Bot

**Симптом:** "Введите целое число (в граммах)"

**Причины:**
1. Введено не число
2. Вес <= 0
3. Вес > 100000 (100кг — максимум)

**Решение:** Введите число от 1 до 100000 или нажмите "Пропустить"

### Сессия intake истекла

**Симптом:** "Сессия истекла" при продолжении ввода

**Причина:** TTL сессии 24 часа, бот перезапустился, или SQLite база недоступна

**Решение:** Начните приход заново командой "📦 Приход товара"

## Rollback

### Откат кода

```bash
git revert HEAD
npm run build
# Деплой
```

### Откат данных

Данные в Google Sheets — используйте историю версий Google Sheets:
1. Файл → История версий → Смотреть историю версий
2. Выберите нужную версию
3. Восстановите

### Откат Owner Bot базы

SQLite база находится в `data/owner_bot.db`. Для отката:
```bash
# Остановить бот
docker compose down

# Восстановить из бэкапа
cp data/owner_bot.db.backup data/owner_bot.db

# Запустить бот
docker compose up -d
```

## Google Apps Script

### Передеплой Apps Script

1. Google Sheets → Extensions → Apps Script
2. Deploy → Manage deployments
3. Создайте новый deployment или обновите существующий
4. Скопируйте новый URL в `.env`

### Код Apps Script

Файл: `google-apps-script/Code.gs`

При изменениях в структуре Google Sheets обновите маппинг колонок в `COLUMNS`.

## Безопасность

### Проверка npm уязвимостей

```bash
npm audit
npm audit fix
```

**Текущий статус:** 3 moderate vulnerabilities (esbuild/vite) — требуют major version upgrade

### Ротация секретов

1. **Telegram Bot Token:** @BotFather → Revoke current token
2. **Google Service Account:** Google Cloud Console → IAM → Service Accounts → Keys
3. **Cloudinary:** Cloudinary Console → Settings → Security

После ротации обновите `.env` и перезапустите ботов.

## Контакты

При критических проблемах:
- Telegram-бот: @agrosna1b_bot
