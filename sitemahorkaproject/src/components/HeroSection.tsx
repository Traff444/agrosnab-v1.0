
export function HeroSection() {
  return (
    <section
      id="hero"
      className="relative isolate min-h-[100vh] min-h-[100svh] w-full overflow-hidden"
    >
      {/* Background video */}
      <div className="absolute inset-0 -z-20">
        {/* Mobile Image */}
        <img
          src={`${import.meta.env.BASE_URL}hiro%20mobil1.png`}
          alt=""
          className="h-full w-full object-cover object-center md:hidden"
          draggable={false}
        />
        {/* Desktop Video */}
        <video
          autoPlay
          loop
          muted
          playsInline
          className="hidden md:block h-full w-full object-cover object-center"
          style={{ filter: 'brightness(0.7)' }}
          draggable={false}
        >
          <source src={`${import.meta.env.BASE_URL}hirovideo.mp4`} type="video/mp4" />
        </video>
        {/* общий overlay для читаемости */}
        <div className="absolute inset-0 bg-black/35" />
        {/* дополнительный градиент снизу под моб. CTA (desktop-only, чтобы mobile не усиливать) */}
        <div className="hidden md:block absolute inset-x-0 bottom-0 h-[40%] bg-gradient-to-t from-black/55 to-transparent" />
      </div>

      {/* MOBILE (<= md): H1 + 1 строка + value pills + CTA внизу */}
      <div
        className="
          md:hidden
          mx-auto flex min-h-[100svh] max-w-[520px] flex-col justify-between
          px-5
          pb-[calc(20px+env(safe-area-inset-bottom))]
          overflow-hidden
        "
      >
        {/* TOP: заголовок (под шапкой, но не прилипает) */}
        <div className="mt-[140px] md:mt-0">
          <div className="w-full max-w-[22ch] text-left">
            <h1
              className="
                font-semibold text-white
                text-[28px] leading-[1.05] tracking-[-0.02em]
                sm:text-[44px]
                md:text-[40px]
                text-balance
              "
            >
              <span 
                className="block lg:inline great-vibes-regular" 
                style={{ 
                  fontSize: '52px', 
                  marginLeft: '-8px', 
                  marginRight: '-6px', 
                  height: '56px', 
                  marginBottom: '-12px', 
                  lineHeight: '0.9', 
                  display: 'block', 
                  color: 'rgba(255, 255, 255, 1)',
                  fontFamily: '"Great Vibes", cursive'
                }}
              >
                Сельскохозяйственная
              </span>
              <br />
              <span className="block font-medium lg:inline -mt-[28px] mb-0 -ml-1 brygada-1918" style={{ fontSize: '43px', lineHeight: '1.1', fontFamily: '"Brygada 1918", serif' }}>махорка</span>
            </h1>
          </div>
        </div>

        {/* CENTER: оставляем воздух, чтобы не перекрывать картинку */}
        <div className="flex-1" />

        {/* BOTTOM: плашки + CTA у нижнего края */}
        <div className="w-full max-w-[520px]">
          {/* pills */}
          <div className="space-y-3">
            {[
              "Минимальные партии от 25 кг",
              "Работа с оптовыми компаниями и магазинами",
              "Минимальный заказ для розницы от 1000 ₽",
              "Минимальный заказ для опта от 5000 ₽",
            ].map((t) => (
              <div
                key={t}
                className="flex items-center gap-2.5 rounded-xl px-4 py-2.5 bg-white/7 backdrop-blur-sm border border-white/10 shadow-sm"
              >
                <span className="inline-flex h-[22px] w-[22px] items-center justify-center rounded-full bg-white/10 border border-white/15">
                  <svg viewBox="0 0 24 24" className="h-[15px] w-[15px]" fill="none">
                    <path
                      d="M20 6L9 17l-5-5"
                      stroke="rgba(255,255,255,0.8)"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <span className="text-[14px] leading-snug text-white/90">{t}</span>
              </div>
            ))}
          </div>

          {/* CTA под pills */}
          <div className="mt-4">
            <a
              href="https://t.me/agrosna1b_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="group inline-flex w-full items-center justify-center gap-3 rounded-2xl
                         bg-[#B55A37] px-6 py-4 text-white text-[16px] font-medium
                         shadow-[0_12px_30px_rgba(0,0,0,0.35)]
                         transition hover:brightness-110 active:scale-[0.99]"
            >
              Получить прайс в Telegram{" "}
              <span className="transition group-hover:translate-x-0.5">→</span>
            </a>
          </div>
        </div>
      </div>

      {/* DESKTOP (md+): текущую вёрстку не трогаем */}
      <div className="hidden md:flex mx-auto min-h-[100svh] max-w-[1280px] px-4 pt-[92px] pb-8 sm:px-6 sm:pt-[108px] lg:px-10 lg:pt-[132px] lg:pb-10">
        {/* LEFT COLUMN - Grid: auto minmax(spacer) auto - уменьшённый spacer */}
        <div className="grid w-full grid-rows-[auto_minmax(40px,80px)_auto] sm:grid-rows-[auto_minmax(50px,100px)_auto] lg:w-[52%] lg:grid-rows-[auto_minmax(60px,120px)_auto]">
          {/* ZONE 1: TOP CONTENT (auto) - Заголовок + подзаголовок */}
          <div className="max-w-[620px] pt-8 sm:pt-10 lg:max-w-[600px] lg:pt-12">
            {/* Заголовок - ограничен по ширине на desktop (12-14ch) */}
            <h1
              className="
                text-white font-semibold tracking-tight
                max-w-[20ch]
                text-[clamp(30px,7.8vw,54px)] leading-[1.14]
                lg:text-[clamp(56px,4.2vw,72px)] lg:leading-[1.05] lg:max-w-[14ch]
              "
            >
              <span className="block lg:inline great-vibes-regular" style={{ fontSize: '80px', marginLeft: '-8px', marginRight: '-6px', height: '60px', marginBottom: '-12px', lineHeight: '0.9', display: 'block', color: 'rgba(255, 255, 255, 1)' }}>
                Сельскохозяйственная
              </span>
              <span className="block font-medium lg:inline -mt-[28px] lg:-mt-[28px] mb-0 -ml-1 brygada-1918" style={{ fontSize: '45px', lineHeight: '1.1' }}>махорка оптом</span>
            </h1>

            {/* Подзаголовок - слабее визуально (opacity), правильный spacing (12-16px) */}
            <p
              className="
                mt-3 lg:mt-4
                text-white/80
                text-[15px] leading-6
                max-w-[46ch]
                line-clamp-2
                sm:line-clamp-none
                lg:text-[18px] lg:leading-7 lg:max-w-[46ch]
              "
            >
              АгроСнаб дистрибьютор натурального растительного сырья из Аргентины, Инди, Крыма и РФ
            </p>

            {/* Desktop: 3 преимущества остаются рядом с текстом (в верхней зоне) */}
            <ul className="hidden lg:block mt-5 space-y-3">
              {[
                "Минимальные партии от 25 кг",
                "Работа с оптовыми компаниями и магазинами",
                "Минимальный заказ для розницы от 1000 ₽",
                "Минимальный заказ для опта от 5000 ₽",
              ].map((t) => (
                <li key={t} className="flex items-start gap-3 text-white/90">
                  <span className="mt-[2px] inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/35 bg-white/5">
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
                      <path
                        d="M20 6L9 17l-5-5"
                        stroke="currentColor"
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                  <span className="text-[16px] leading-6">{t}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* ZONE 2: VISUAL SPACE (1fr) - растягивается автоматически, создаёт визуальный воздух между контентом и CTA */}
          <div></div>

          {/* ZONE 3: Bottom CTA group (mobile) + CTA (desktop) */}
          <div className="max-w-[520px] pb-6 lg:pb-8">
            {/* Mobile: 2 преимущества рядом с CTA */}
            <ul className="mb-3 space-y-2 lg:hidden">
              {[
                "Минимальные партии от 25 кг",
                "Работа с оптовыми компаниями и магазинами",
                "Минимальный заказ для розницы от 1000 ₽",
                "Минимальный заказ для опта от 5000 ₽",
              ].map((t) => (
                <li key={t} className="flex items-start gap-3 text-white/90">
                  <span className="mt-[2px] inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/35 bg-white/5">
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
                      <path
                        d="M20 6L9 17l-5-5"
                        stroke="currentColor"
                        strokeWidth="2.2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                  <span className="text-[14px] leading-6">{t}</span>
                </li>
              ))}
            </ul>

            <a
              href="https://t.me/agrosna1b_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="group inline-flex w-full items-center justify-center gap-3 rounded-2xl
                         bg-[#B55A37] px-5 py-4 text-white
                         shadow-[0_12px_30px_rgba(0,0,0,0.35)]
                         transition hover:brightness-110 active:scale-[0.99]
                         sm:w-auto sm:px-6"
            >
              <span className="text-[16px] font-medium">
                Получить прайс в Telegram
              </span>
              <span className="transition group-hover:translate-x-0.5">→</span>
            </a>
          </div>
        </div>

        {/* Right product pack layer (optional overlay) - Desktop only */}
        <div className="relative hidden flex-1 lg:block">
          {/* Опционально: раскомментировать, если есть файл /Hero1.webp или /pack.webp */}
          {/* <img
            src="/Hero1.webp"
            alt="Махорка Золотая"
            className="pointer-events-none absolute bottom-[-2%] right-[-2%]
                       w-[640px] max-w-none drop-shadow-[0_30px_60px_rgba(0,0,0,0.45)]"
          /> */}
        </div>
      </div>

      {/* Scroll indicator only on desktop */}
      <div className="pointer-events-none absolute bottom-6 left-1/2 hidden -translate-x-1/2 lg:block">
        <div className="flex flex-col items-center gap-2 text-white/60">
          <div className="relative h-10 w-6 rounded-full border border-white/35">
            <span className="absolute left-1/2 top-2 h-2 w-1 -translate-x-1/2 rounded-full bg-white/60 animate-[scrollDot_1.2s_infinite]" />
          </div>
          <div className="text-[12px]">листай вниз</div>
        </div>
      </div>

      <style>{`
        @keyframes scrollDot {
          0% { transform: translate(-50%, 0); opacity: 0.25; }
          50% { transform: translate(-50%, 10px); opacity: 1; }
          100% { transform: translate(-50%, 0); opacity: 0.25; }
        }
      `}</style>
    </section>
  );
}
