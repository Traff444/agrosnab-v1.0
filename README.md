# АгроСнаб - Сайт каталога сельскохозяйственной продукции

React-приложение для отображения каталога товаров с интеграцией Google Sheets.

## Архитектура

```
┌─────────────────┐     fetch JSON      ┌──────────────────┐
│   React App     │ ◄────────────────── │  Apps Script     │
│   (Vite)        │                     │  Web App         │
└─────────────────┘                     └────────┬─────────┘
                                                 │ читает
                                                 ▼
                                        ┌──────────────────┐
                                        │  Google Sheets   │
                                        │  лист "Склад"    │
                                        └──────────────────┘
```

## Быстрый старт

```bash
# Установка зависимостей
npm install

# Настройка окружения
cp .env.example .env
# Добавьте VITE_APPS_SCRIPT_URL в .env

# Запуск dev-сервера
npm run dev
```

## Скрипты

| Команда | Описание |
|---------|----------|
| `npm run dev` | Запуск dev-сервера Vite |
| `npm run build` | Сборка для production |
| `npm run preview` | Предпросмотр production-сборки |
| `npm run lint` | Проверка кода ESLint |
| `npm run typecheck` | Проверка типов TypeScript |

## Переменные окружения

| Переменная | Описание | Формат |
|------------|----------|--------|
| `VITE_APPS_SCRIPT_URL` | URL Google Apps Script Web App | `https://script.google.com/macros/s/xxx/exec` |

## Стек технологий

- **React 18** + TypeScript
- **Vite** — сборщик
- **Tailwind CSS** — стили
- **Lucide React** — иконки

## Структура проекта

```
src/
├── components/       # React-компоненты
│   ├── Header.tsx
│   ├── Footer.tsx
│   ├── HeroSection.tsx
│   ├── ProductCard.tsx
│   └── CountUp.tsx
├── lib/
│   └── catalog.ts    # Загрузка данных из Google Sheets
├── App.tsx           # Главный компонент
└── main.tsx          # Точка входа
```

## Документация

- [CONTRIB.md](docs/CONTRIB.md) — руководство для разработчиков
- [RUNBOOK.md](docs/RUNBOOK.md) — операционные процедуры
