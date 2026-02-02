# Исследование: Откуда берётся фото товара "Тест создания товара"

## Краткий ответ

✅ **Это НЕ заглушка в традиционном смысле**, а **placeholder изображение**, которое использует **только веб-каталог** (браузер), а не Telegram-бот.

### Что происходит:

1. **В Google Sheets таблице**: поле `Фото_URL` для товара "Тест создания товара" — **пустое**
2. **В Telegram-боте**: товар отображается **без фото** (только текст)
3. **На веб-сайте**: товар отображается **с placeholder изображением** (`public/placeholder.webp`)

## Техническая документация

### 1. Источник placeholder изображения

**Файлы:**
- `/Users/sr/Desktop/Makbookprodesktop/job/FamTeam/excel-telegram-bot-starter/public/placeholder.webp` (173 KB)
- Дубликаты: `docs/placeholder.webp`, `placeholder.webp` (в корне)

**Использование в коде:**

Файл: `src/lib/catalog.ts:71-72`

```typescript
export const PLACEHOLDER_IMAGE = `${import.meta.env.BASE_URL}placeholder.webp`;

function normalizeProduct(raw: Record<string, unknown>): Product {
  const photoUrlRaw = String(raw.photoUrl || '').trim();
  const photoUrl = isValidImageUrl(photoUrlRaw) ? photoUrlRaw : PLACEHOLDER_IMAGE;

  return {
    photoUrl: photoUrl || PLACEHOLDER_IMAGE,
    // ... остальные поля
  };
}
```

**Логика:** Если `photoUrl` пустой или невалидный → используется `PLACEHOLDER_IMAGE`

### 2. Как работает обработка фото в разных частях системы

#### A. Google Sheets → Python Backend

Файл: `app/sheets.py:78-102`

```python
def convert_photo_url(url: str) -> str:
    """
    Convert various image hosting URLs to direct links.
    Supports: Google Drive, Dropbox
    """
    if not url:
        return ""  # Возвращает пустую строку если URL пустой

    # Конвертация Google Drive, Dropbox...
    return url
```

Файл: `app/sheets.py:320`

```python
"photo_url": convert_photo_url(safe_get(r, col_photo)),
```

**Результат:** Если в таблице пусто → `photo_url` = `""`

#### B. Telegram-бот

Файл: `app/handlers/catalog.py:218-229`

```python
if product.get("photo_url"):
    try:
        await cb.message.answer_photo(
            product["photo_url"],
            caption=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb)
else:
    # Если photo_url пустой - отправляем текстовое сообщение
    await cb.message.answer(text, parse_mode="HTML", reply_markup=kb)
```

**Результат:** Товар без фото отображается как **текстовое сообщение**

#### C. Веб-каталог (Frontend)

Файл: `src/lib/catalog.ts:92-99`

```typescript
function normalizeProduct(raw: Record<string, unknown>): Product {
  const photoUrlRaw = String(raw.photoUrl || '').trim();
  const photoUrl = isValidImageUrl(photoUrlRaw) ? photoUrlRaw : PLACEHOLDER_IMAGE;

  return {
    photoUrl: photoUrl || PLACEHOLDER_IMAGE,  // Всегда есть значение!
    // ...
  };
}
```

**Результат:** Товар без фото отображается **с placeholder.webp**

### 3. Информация о товаре "Тест создания товара"

**Данные из Google Sheets** (лист "Склад"):
- **SKU:** `PRD-20260127-ADE0`
- **Наименование:** "Тест создания товара"
- **Описание:** "Автотест"
- **Цена:** 123 ₽
- **Фото_URL:** **(ПУСТО)**
- **Теги:** "тест,автоматический"

**Создан:** 27 января 2026 через owner_bot (бот для владельца магазина)

### 4. Как был создан этот товар

Owner_bot позволяет создавать товары без фото:

Файл: `owner_bot/app/handlers/intake.py:297-313`

```python
await msg.answer(
    "📷 Хотите добавить фото товара?\n\n"
    "Отправьте фото или нажмите 'Пропустить'",
    reply_markup=skip_kb(),
)
await state.set_state(IntakeState.awaiting_photo)
```

Если владелец нажимает "Пропустить", товар создаётся с `photo_url=""`.

## Сравнительная таблица

| Компонент | Товар без фото в таблице | Товар с фото в таблице |
|-----------|-------------------------|------------------------|
| **Google Sheets** | Поле `Фото_URL` пустое | URL в поле `Фото_URL` |
| **Python Backend** | `photo_url` = `""` | `photo_url` = конвертированный URL |
| **Telegram-бот** | Текстовое сообщение (без фото) | Фото + caption |
| **Веб-каталог** | `placeholder.webp` (173 KB) | Реальное фото |

## Проверка

### Проверить в Telegram-боте:

1. Откройте @agrosna1b_bot в Telegram
2. Нажмите "🗂 Каталог"
3. Найдите товар "Тест создания товара"
4. Нажмите на него
5. **Ожидаемый результат:** Текстовое сообщение без фото

### Проверить на веб-сайте:

1. Откройте веб-версию каталога в браузере
2. Найдите товар "Тест создания товара"
3. **Ожидаемый результат:** Товар с placeholder изображением

### Проверить в Google Sheets:

1. Откройте таблицу (ID: `1r9rpm7WF1tAjPud8DhpgszpPQNVhfforh1XXyKNuR9A`)
2. Лист "Склад"
3. Найдите строку с товаром "Тест создания товара" (SKU: `PRD-20260127-ADE0`)
4. **Ожидаемый результат:** Колонка `Фото_URL` пустая

## Критические файлы

### Backend (Telegram-бот):
- `app/sheets.py:78-102` - Функция `convert_photo_url()` (обработка URL)
- `app/sheets.py:242-325` - Метод `get_products()` (чтение данных)
- `app/handlers/catalog.py:218-229` - Отображение товара с/без фото

### Frontend (Веб-каталог):
- `src/lib/catalog.ts:71-72, 92-99` - Функция `normalizeProduct()` (подстановка placeholder)
- `public/placeholder.webp` - Placeholder изображение (173 KB)

### Owner Bot (Создание товаров):
- `owner_bot/app/handlers/intake.py:297-313` - Опциональная загрузка фото
- `owner_bot/app/services/intake_service.py:192` - Создание товара с `photo_url=""`
- `owner_bot/app/models.py:77` - Модель Product с дефолтным `photo_url=""`

## Вывод

Фотография, которую вы видите на веб-сайте для товара "Тест создания товара" — это **placeholder изображение** из файла `public/placeholder.webp`.

**Почему так происходит:**
1. Товар был создан через owner_bot без фото (владелец нажал "Пропустить")
2. В Google Sheets поле `Фото_URL` осталось пустым
3. Telegram-бот корректно показывает товар без фото (только текст)
4. Веб-каталог автоматически подставляет placeholder для товаров без фото

**Это нормальное поведение системы** — разные компоненты по-разному обрабатывают отсутствие фото:
- 🤖 **Telegram-бот**: текст без изображения (нативное UX для Telegram)
- 🌐 **Веб-каталог**: placeholder (лучшее UX для веба)

## Диаграмма потока данных

```
┌─────────────────┐
│ Google Sheets   │
│ Фото_URL: ""    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ app/sheets.py:convert_photo_url()   │
│ Возвращает: ""                      │
└────────┬────────────────────────────┘
         │
         ├──────────────────┬──────────────────┐
         ▼                  ▼                  ▼
┌──────────────────┐ ┌─────────────────┐ ┌────────────────────┐
│ Telegram-бот     │ │ API /products   │ │ Веб-каталог        │
│ photo_url: ""    │ │ photo_url: ""   │ │ photoUrl: ""       │
└────────┬─────────┘ └────────┬────────┘ └────────┬───────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────────┐ ┌─────────────────┐ ┌────────────────────┐
│ Проверка:        │ │ JSON response   │ │ normalizeProduct() │
│ if photo_url:    │ │ (передаёт как   │ │ Проверка:          │
│   ✗ False        │ │  есть)          │ │ isValidImageUrl()  │
│                  │ │                 │ │   ✗ False          │
└────────┬─────────┘ └─────────────────┘ └────────┬───────────┘
         │                                         │
         ▼                                         ▼
┌──────────────────┐                     ┌────────────────────┐
│ Текстовое        │                     │ photoUrl =         │
│ сообщение        │                     │ PLACEHOLDER_IMAGE  │
│ (без фото)       │                     │                    │
└──────────────────┘                     └────────┬───────────┘
                                                  │
                                                  ▼
                                         ┌────────────────────┐
                                         │ Отображение:       │
                                         │ placeholder.webp   │
                                         └────────────────────┘
```

## Дата создания документа

2026-02-02
