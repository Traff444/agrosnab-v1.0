# Операционные процедуры (Runbook)

## Деплой

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

**Решение:** Используйте публичные URL или настройте Google Drive sharing

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

## Google Apps Script

### Передеплой Apps Script

1. Google Sheets → Extensions → Apps Script
2. Deploy → Manage deployments
3. Создайте новый deployment или обновите существующий
4. Скопируйте новый URL в `.env`

### Код Apps Script

Файл: `google-apps-script/Code.gs`

При изменениях в структуре Google Sheets обновите маппинг колонок в `COLUMNS`.

## Контакты

При критических проблемах:
- Telegram-бот: @agrosna1b_bot
