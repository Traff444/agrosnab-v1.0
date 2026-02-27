import { useState, useEffect } from 'react';
import { Sprout, Menu, X } from 'lucide-react';

const NAV_ITEMS = [
  { label: 'Ассортимент', href: '#catalog' },
  { label: 'Как заказать', href: '#how-to-order' },
  { label: 'Условия', href: '#terms' },
  { label: 'Доставка', href: '#delivery' },
  { label: 'Контакты', href: '#contacts' },
];

export function Header() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 40);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (href: string) => {
    setMenuOpen(false);
    const el = document.querySelector(href);
    if (el) {
      const headerOffset = 90;
      const top = el.getBoundingClientRect().top + window.pageYOffset - headerOffset;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  };

  return (
    <header
      className={`header ${scrolled ? 'scrolled' : ''}`}
    >
      <div className="header-container max-w-[1200px] mx-auto px-4 md:px-6 py-3.5 md:py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sprout className="w-7 h-7 md:w-8 md:h-8 text-color-accent" strokeWidth={1.8} />
          <span className="header-logo font-heading font-bold text-lg md:text-xl">ТопХит</span>
        </div>

        <nav className="hidden md:flex items-center gap-6 lg:gap-8">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.href}
              onClick={() => scrollToSection(item.href)}
              className="nav-link text-sm font-medium transition-colors duration-200"
            >
              {item.label}
            </button>
          ))}
        </nav>

        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="header-menu-btn md:hidden p-1"
        >
          {menuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {menuOpen && (
        <nav className="md:hidden px-4 pb-4 flex flex-col gap-3">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.href}
              onClick={() => scrollToSection(item.href)}
              className="nav-link text-sm font-medium transition-colors duration-200 text-left"
            >
              {item.label}
            </button>
          ))}
        </nav>
      )}
    </header>
  );
}
