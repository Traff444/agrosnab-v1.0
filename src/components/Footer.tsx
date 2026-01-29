import { Sprout } from 'lucide-react';

export function Footer() {
  const openTelegram = () => {
    window.open('https://t.me/agrosna1b_bot', '_blank', 'noopener,noreferrer');
  };

  return (
    <footer id="contacts" className="py-14 md:py-18 px-4 md:px-6 bg-color-footer border-t border-white/5">
      <div className="max-w-[1200px] mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 md:gap-14 mb-12 md:mb-14">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Sprout className="w-7 h-7 text-color-accent" strokeWidth={1.8} />
              <span className="font-heading font-bold text-xl text-text-on-dark">АгроСнаб</span>
            </div>
            <p className="text-sm text-subtext-on-dark leading-relaxed">
              Оптовые поставки сельскохозяйственного растительного сырья
            </p>
          </div>

          <div>
            <h3 className="font-heading font-semibold text-base mb-4 text-text-on-dark">Навигация</h3>
            <nav className="flex flex-col gap-2.5">
              <button
                onClick={openTelegram}
                className="text-sm text-subtext-on-dark hover:text-text-on-dark hover:translate-x-1 transition-all duration-300 text-left"
              >
                Ассортимент
              </button>
              <button
                onClick={openTelegram}
                className="text-sm text-subtext-on-dark hover:text-text-on-dark hover:translate-x-1 transition-all duration-300 text-left"
              >
                Как заказать
              </button>
              <button
                onClick={openTelegram}
                className="text-sm text-subtext-on-dark hover:text-text-on-dark hover:translate-x-1 transition-all duration-300 text-left"
              >
                Условия
              </button>
              <button
                onClick={openTelegram}
                className="text-sm text-subtext-on-dark hover:text-text-on-dark hover:translate-x-1 transition-all duration-300 text-left"
              >
                Доставка
              </button>
              <button
                onClick={openTelegram}
                className="text-sm text-subtext-on-dark hover:text-text-on-dark hover:translate-x-1 transition-all duration-300 text-left"
              >
                Контакты
              </button>
            </nav>
          </div>

          <div>
            <h3 className="font-heading font-semibold text-base mb-4 text-text-on-dark">Контакты</h3>
            <div className="flex flex-col gap-2.5">
              <a
                href="https://t.me/agrosna1b_bot"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-subtext-on-dark hover:text-color-accent hover:translate-x-1 transition-all duration-300 inline-block"
              >
                Telegram
              </a>
              <a
                href="tel:+79164810769"
                className="text-sm text-subtext-on-dark hover:text-color-accent hover:translate-x-1 transition-all duration-300 inline-block"
              >
                +7 (916) 481-07-69
              </a>
            </div>
          </div>

          <div>
            <h3 className="font-heading font-semibold text-base mb-4 text-text-on-dark">Реквизиты</h3>
            <div className="flex flex-col gap-2 text-sm text-subtext-on-dark leading-relaxed">
              <span>ООО &quot;ТОПХИТ&quot;</span>
              <span>ИНН 5029270376</span>
              <span>КПП 502901001</span>
              <span>Юр. адрес: г. Москва, ул. Складочная, д. 1, стр. 18, офис 102</span>
            </div>
          </div>
        </div>

        <div className="border-t border-white/5 pt-8 space-y-3 md:space-y-4">
          <p className="text-xs md:text-sm text-subtext-on-dark leading-relaxed text-center max-w-3xl mx-auto">
            Информация на сайте предназначена для оптовых клиентов.
            Продукция реализуется как сельскохозяйственное сырьё
            для хозяйственных и технических целей.
          </p>
          <p className="text-xs md:text-sm text-subtext-on-dark text-center opacity-60">
            © 2026 АгроСнаб. Все права защищены.
          </p>
          <p className="text-xs md:text-sm text-subtext-on-dark text-center opacity-60">
            Сайт разработан командой{' '}
            <a
              href="https://fanteam.pro"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-on-dark hover:text-color-accent transition-colors"
            >
              FanTeam.pro
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}
