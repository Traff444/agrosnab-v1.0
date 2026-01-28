# Руководство для разработчиков

## Требования

- Node.js 18+
- npm 9+

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
| `npm run typecheck` | Проверка типов TypeScript |

### Workflow перед коммитом

```bash
npm run typecheck && npm run lint && npm run build
```

## Переменные окружения

| Переменная | Обязательная | Описание |
|------------|--------------|----------|
| `VITE_APPS_SCRIPT_URL` | Да | URL Google Apps Script Web App для загрузки каталога |

**Формат URL:** `https://script.google.com/macros/s/{DEPLOYMENT_ID}/exec`

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

## Стилизация

- Tailwind CSS с кастомными цветами в `tailwind.config.js`
- Адаптивный дизайн (mobile-first)
- CSS-переменные для цветовой схемы

## Тестирование

### Ручные тест-кейсы

| Сценарий | Ожидание |
|----------|----------|
| Товар в наличии (stock > 0) | Кнопка "Получить прайс" |
| Товар не в наличии (stock = 0) | Бейдж "Нет в наличии", кнопка "Уточнить в Telegram" |
| Неактивный товар | Не отображается |
| Ошибка загрузки | Сообщение + кнопка "Попробовать снова" |
| Пустой каталог | "Товары скоро появятся" |
| Битая ссылка на фото | Placeholder изображение |
