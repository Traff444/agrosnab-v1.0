## Overview
- Проект: Vite + React + TypeScript + TailwindCSS (лендинг).
- Основной рендер: `src/main.tsx` → `src/App.tsx`.
- Деплой GitHub Pages настроен через GitHub Actions workflow `.github/workflows/deploy.yml` (build → upload artifact → deploy pages).

## Key Components
- `src/components/Header.tsx`: фиксированная “плавающая капсула” (CSS класс `.header`), меняет состояние `scrolled` после 40px скролла.
- `src/components/HeroSection.tsx`: hero с фоном **desktop видео** `/1234.mp4` и **mobile картинкой** `/mobilHero.webp`; на mobile разметка разведена на «H1 сверху» и «плашки+CTA снизу», чтобы центр кадра был чистым.
- `src/App.tsx`: собирает главную страницу из секций (`Hero`, `Trust Block`, каталог, и т.д.).
- `src/components/CountUp.tsx`: анимированный счётчик (0 → target) при появлении в viewport.

## Sections (App)
- Hero: `<HeroSection />`
- Trust Block: 4 карточки со статистикой (первый блок: `20+ сортов в ассортименте`, с анимацией счётчиков)
- Product Catalog, How to Order, Wholesale Terms, Delivery, Quality, Final CTA, Footer

## Patterns / UX
- Hero background: desktop использует видео `/1234.mp4`; mobile использует статичную картинку `/hiro mobil1.png`.
- Тексты преимуществ в Hero/desktop: «Минимальные партии от 25 кг», «Работа с оптовыми компаниями и магазинами».
- Подзаголовок Hero (desktop): «АгроСнаб дистрибьютор натурального растительного сырья из Аргентины, Инди, Крыма и РФ».
- Карточки ассортимента (`ProductCard` в секции `#catalog`) используют локальные обложки `public/tovar1.webp`…`tovar9.webp` (циклически по списку продуктов).
- `ProductCard`: изображение в карточке рендерится как `object-contain` внутри блока с фоном `#FFF8F0` и внутренним `p-2` (чтобы весь товар влезал без белых зазоров).
- Для счетчиков используется IntersectionObserver (запуск один раз при появлении) + requestAnimationFrame (плавный count-up).
- Уважает `prefers-reduced-motion` (в таком режиме сразу показывает target без анимации).
- Header capsule (CSS): `.header { width: calc(100% - 48px); max-width: 1200px; top: 16px; }`, в состоянии `.scrolled` расширяется на `width: 100%`.
- Hero text block: `.hero-content { max-width: 560px; }` + микро-сдвиг `translateX(-12px)` на desktop.
- Desktop Hero H1: акцентная строка `махорка оптом` в `HeroSection` использует **Inter Medium** (`font-medium`, weight 500). Первая строка заголовка "Сельскохозяйственная" использует шрифт **Great Vibes** (подключён через Google Fonts в `index.html`, CSS-класс `.great-vibes-regular` в `src/index.css`) с обычным регистром (первая буква заглавная, остальные прописные).
- Фон секции `#terms` (“Условия оптовых поставок”): класс `.terms-bg` задаёт `background-image: url('/fon.webp')` и мягкий тёмный overlay через `::before`.
- Карточки в `#terms`: используются классы `terms-card` + `border border-white/35`; в `src/index.css` под `.terms-bg .terms-card` повышена читаемость текста (белые оттенки для h3/p/ul/strong) и добавлена мягкая тень.
- Общий фон секций через `fon.webp`: класс `.fon-bg` (в `src/index.css`) задаёт `background-image: url('/fon.webp')` + overlay `::before`; применён к секциям `#catalog` и “Качество и происхождение сырья”.
- Карточки в секции “Качество и происхождение сырья”: маркер `quality-card` + `border border-white/35`; в `src/index.css` стили под `.quality-bg .quality-card` делают текст чуть ярче (h3/p/strong) и добавляют мягкую тень.
- Hero (главный экран) реализован в `src/components/HeroSection.tsx`: разделён на две ветки разметки. **Mobile (<= md)**: отдельный контейнер `md:hidden` на ровно `100svh` (fallback `100vh`), остаются только H1 → glass-pills → CTA (без подзаголовка). Контейнер текста `max-w-[320px]` + `pr-6`, выравнивание по левому краю. Pills оформлены как лёгкий glass: `rounded-xl`, `bg-white/7`, `backdrop-blur-sm`, `border-white/10`, `shadow-sm`, `gap-2.5`, `text-[14px]`. CTA идёт сразу под pills (`mt-6`), без текста под кнопкой. **Desktop (md+)**: `hidden md:flex` сохраняет текущую вёрстку без изменений. Фон: mobile `/mobilHero.webp`, desktop видео `/1234.mp4`; overlay не усиливается (остался общий `bg-black/35`), mobile-градиенты убраны.
- Hero (главный экран) реализован в `src/components/HeroSection.tsx`: разделён на две ветки разметки. **Mobile (<= md)**: контейнер `md:hidden` на `min-h-[100svh]` + `flex-col justify-between` — **H1 сверху** с фиксированным сдвигом вниз `mt-[140px]` (чистый центр кадра), **плашки+CTA снизу** (`pb` с safe-area), а **центр остаётся пустым** (spacer `flex-1`) — так картинка в середине не перекрывается текстом. H1: основной вес `font-semibold`, трекинг `tracking-[-0.02em]`, размеры по брейкпоинтам: mobile `text-[28px] leading-[1.05]`, `sm:text-[44px]`, `md:text-[40px]`. Акцентная строка "махорка оптом" использует **Inter Medium** (`font-medium`, weight 500). **Desktop (md+)**: `hidden md:flex` сохраняет текущую вёрстку без изменений. Фон: mobile `/mobilHero.webp`, desktop видео `/1234.mp4`; общий overlay `bg-black/35`.

## User Defined Namespaces
- frontend