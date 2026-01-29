import { useState, useEffect } from 'react';
import { Sprout, Menu } from 'lucide-react';

export function Header() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 40) {
        setScrolled(true);
      } else {
        setScrolled(false);
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const openTelegram = () => {
    window.open('https://t.me/agrosna1b_bot', '_blank', 'noopener,noreferrer');
  };

  return (
    <header
      className={`header ${scrolled ? 'scrolled' : ''}`}
    >
      <div className="header-container max-w-[1200px] mx-auto px-4 md:px-6 py-3.5 md:py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sprout className="w-7 h-7 md:w-8 md:h-8 text-color-accent" strokeWidth={1.8} />
          <span className="header-logo font-heading font-bold text-lg md:text-xl">Махорка</span>
        </div>

        <nav className="hidden md:flex items-center gap-6 lg:gap-8">
          <button
            onClick={openTelegram}
            className="nav-link text-sm font-medium transition-colors duration-200"
          >
            Ассортимент
          </button>
          <button
            onClick={openTelegram}
            className="nav-link text-sm font-medium transition-colors duration-200"
          >
            Как заказать
          </button>
          <button
            onClick={openTelegram}
            className="nav-link text-sm font-medium transition-colors duration-200"
          >
            Условия
          </button>
          <button
            onClick={openTelegram}
            className="nav-link text-sm font-medium transition-colors duration-200"
          >
            Доставка
          </button>
          <button
            onClick={openTelegram}
            className="nav-link text-sm font-medium transition-colors duration-200"
          >
            Контакты
          </button>
        </nav>

        <button
          onClick={openTelegram}
          className="header-menu-btn md:hidden p-1"
        >
          <Menu className="w-6 h-6" />
        </button>
      </div>
    </header>
  );
}
