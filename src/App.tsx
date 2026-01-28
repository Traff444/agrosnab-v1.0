import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { ProductCard } from './components/ProductCard';
import { HeroSection } from './components/HeroSection';
import { CountUp } from './components/CountUp';
import { fetchCatalog, Product } from './lib/catalog';
import {
  CheckCircle2,
  Package,
  TrendingUp,
  Users,
  MessageSquare,
  FileCheck,
  Truck,
  MapPin,
  Shield,
  Leaf,
  ArrowRight,
  ChevronDown,
  Loader2,
  RefreshCw
} from 'lucide-react';

function App() {
  const [showAllProducts, setShowAllProducts] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchCatalog()
      .then((res) => {
        if (res.error) {
          setError(res.error);
        }
        setProducts(res.items);
      })
      .catch(() => setError('Каталог временно недоступен'))
      .finally(() => setLoading(false));
  }, [reloadKey]);

  const handleRetry = () => setReloadKey((k) => k + 1);

  const visibleProducts = showAllProducts ? products : products.slice(0, 6);

  return (
    <div className="min-h-screen bg-textured-dark">
      <Header />

      {/* Hero Section */}
      <HeroSection />

      {/* Trust Block */}
      <section className="py-12 md:py-16 lg:py-24 px-4 md:px-6 bg-textured-light">
        <div className="max-w-[1200px] mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-6 md:gap-8">
            <div className="text-center surface-card-light rounded-lg p-6 transition-all duration-300 hover:shadow-lg">
              <Package className="w-9 h-9 md:w-10 md:h-10 text-color-accent-2 mx-auto mb-3 md:mb-4 opacity-80" strokeWidth={1.5} />
              <p className="font-heading font-bold text-2xl md:text-3xl mb-1 md:mb-2 text-color-accent">
                <CountUp to={20} suffix="+" />
              </p>
              <p className="text-xs md:text-base text-subtext-on-light">сортов в ассортименте</p>
            </div>
            <div className="text-center surface-card-light rounded-lg p-6 transition-all duration-300 hover:shadow-lg">
              <TrendingUp className="w-9 h-9 md:w-10 md:h-10 text-color-accent-2 mx-auto mb-3 md:mb-4 opacity-80" strokeWidth={1.5} />
              <p className="font-heading font-bold text-2xl md:text-3xl mb-1 md:mb-2 text-color-accent">
                <CountUp to={7} /> <span aria-hidden="true">лет</span>
              </p>
              <p className="text-xs md:text-base text-subtext-on-light">на рынке</p>
            </div>
            <div className="text-center surface-card-light rounded-lg p-6 transition-all duration-300 hover:shadow-lg">
              <Users className="w-9 h-9 md:w-10 md:h-10 text-color-accent-2 mx-auto mb-3 md:mb-4 opacity-80" strokeWidth={1.5} />
              <p className="font-heading font-bold text-2xl md:text-3xl mb-1 md:mb-2 text-color-accent">
                <CountUp to={200} suffix="+" />
              </p>
              <p className="text-xs md:text-base text-subtext-on-light">постоянных клиентов</p>
            </div>
            <div className="text-center surface-card-light rounded-lg p-6 transition-all duration-300 hover:shadow-lg">
              <Shield className="w-9 h-9 md:w-10 md:h-10 text-color-accent-2 mx-auto mb-3 md:mb-4 opacity-80" strokeWidth={1.5} />
              <p className="font-heading font-bold text-2xl md:text-3xl mb-1 md:mb-2 text-color-accent">
                <CountUp to={100} suffix="%" />
              </p>
              <p className="text-xs md:text-base text-subtext-on-light">контроль качества</p>
            </div>
          </div>
        </div>
      </section>

      {/* Product Catalog */}
      <section id="catalog" className="fon-bg py-12 md:py-16 lg:py-24 px-4 md:px-6">
        <div className="max-w-[1200px] mx-auto">
          <h2 className="font-heading font-bold text-2xl md:text-3xl lg:text-4xl mb-3 md:mb-4 text-text-on-dark">Ассортимент и цены</h2>
          <p className="text-sm md:text-base text-subtext-on-dark mb-8 md:mb-12 max-w-2xl">
            Широкий выбор сортов сельскохозяйственного сырья с гибкими условиями поставки
          </p>

          {/* Loading state */}
          {loading && (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="w-10 h-10 text-white animate-spin mb-4" />
              <p className="text-subtext-on-dark">Загрузка каталога...</p>
            </div>
          )}

          {/* Error state */}
          {!loading && error && (
            <div className="flex flex-col items-center justify-center py-16">
              <p className="text-white mb-4">{error}</p>
              <button
                onClick={handleRetry}
                className="inline-flex items-center gap-2 border-2 border-white text-white hover:bg-white/10 transition-colors px-6 py-2.5 rounded-lg font-medium text-sm"
              >
                <RefreshCw className="w-4 h-4" />
                Попробовать снова
              </button>
            </div>
          )}

          {/* Empty state */}
          {!loading && !error && products.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16">
              <Package className="w-12 h-12 text-white/50 mb-4" />
              <p className="text-subtext-on-dark">Товары скоро появятся</p>
            </div>
          )}

          {/* Products grid */}
          {!loading && !error && products.length > 0 && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6 mb-6 md:mb-8">
                {visibleProducts.map((product) => (
                  <ProductCard key={product.sku} product={product} />
                ))}
              </div>

              {products.length > 6 && (
                <div className="text-center">
                  {!showAllProducts ? (
                    <button
                      onClick={() => setShowAllProducts(true)}
                      className="inline-flex items-center gap-2 border-2 border-white text-white hover:bg-white/10 transition-colors px-6 py-2.5 md:px-8 md:py-3 rounded-lg font-medium text-sm md:text-base"
                    >
                      Показать весь ассортимент ({products.length - 6} ещё)
                      <ChevronDown className="w-4 h-4 md:w-5 md:h-5" />
                    </button>
                  ) : (
                    <button
                      onClick={() => setShowAllProducts(false)}
                      className="inline-flex items-center gap-2 border-2 border-white text-white hover:bg-white/10 transition-colors px-6 py-2.5 md:px-8 md:py-3 rounded-lg font-medium text-sm md:text-base"
                    >
                      Свернуть ассортимент
                      <ChevronDown className="w-4 h-4 md:w-5 md:h-5 rotate-180" />
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {/* How to Order */}
      <section id="how-to-order" className="py-12 md:py-16 lg:py-24 px-4 md:px-6 bg-textured-light">
        <div className="max-w-[1200px] mx-auto">
          <h2 className="font-heading font-bold text-2xl md:text-3xl lg:text-4xl mb-8 md:mb-12 text-text-on-light">Как заказать</h2>

          <div className="relative">
            <div className="hidden lg:block absolute top-14 left-0 right-0 h-0.5 bg-gradient-to-r from-color-accent/20 via-color-accent/40 to-color-accent/20" style={{ marginLeft: '10%', marginRight: '10%' }}></div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 md:gap-8 relative">
              <div className="surface-card-light rounded-lg p-6 flex flex-col h-full transition-all duration-300 hover:shadow-lg animate-fade-in opacity-0">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 bg-color-accent rounded-full flex items-center justify-center font-heading font-bold text-xl text-text-on-dark flex-shrink-0 shadow-md">
                    1
                  </div>
                  <h3 className="font-heading font-semibold text-lg text-text-on-light">Выбор сорта</h3>
                </div>
                <p className="text-sm text-subtext-on-light leading-relaxed">
                  Ознакомьтесь с ассортиментом и выберите подходящий сорт
                </p>
              </div>

              <div className="surface-card-light rounded-lg p-6 flex flex-col h-full transition-all duration-300 hover:shadow-lg animate-fade-in opacity-0 delay-100">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 bg-color-accent rounded-full flex items-center justify-center font-heading font-bold text-xl text-text-on-dark flex-shrink-0 shadow-md">
                    2
                  </div>
                  <h3 className="font-heading font-semibold text-lg text-text-on-light">Уточнение объёма</h3>
                </div>
                <p className="text-sm text-subtext-on-light leading-relaxed">
                  Свяжитесь через Telegram-бота и укажите требуемый объём
                </p>
              </div>

              <div className="surface-card-light rounded-lg p-6 flex flex-col h-full transition-all duration-300 hover:shadow-lg animate-fade-in opacity-0 delay-200">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 bg-color-accent rounded-full flex items-center justify-center font-heading font-bold text-xl text-text-on-dark flex-shrink-0 shadow-md">
                    3
                  </div>
                  <h3 className="font-heading font-semibold text-lg text-text-on-light">Связь с менеджером</h3>
                </div>
                <p className="text-sm text-subtext-on-light leading-relaxed">
                  Наш менеджер свяжется для уточнения деталей заказа
                </p>
              </div>

              <div className="surface-card-light rounded-lg p-6 flex flex-col h-full transition-all duration-300 hover:shadow-lg animate-fade-in opacity-0 delay-300">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 bg-color-accent rounded-full flex items-center justify-center font-heading font-bold text-xl text-text-on-dark flex-shrink-0 shadow-md">
                    4
                  </div>
                  <h3 className="font-heading font-semibold text-lg text-text-on-light">Согласование и отгрузка</h3>
                </div>
                <p className="text-sm text-subtext-on-light leading-relaxed">
                  Оформление документов и организация доставки
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Wholesale Terms */}
      <section id="terms" className="terms-bg py-12 md:py-16 lg:py-24 px-4 md:px-6">
        <div className="max-w-[1200px] mx-auto">
          <h2 className="font-heading font-bold text-2xl md:text-3xl lg:text-4xl mb-8 md:mb-12 text-text-on-dark">
            Условия оптовых поставок
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
            <div className="surface-card terms-card rounded-lg p-6 md:p-8 flex flex-col h-full transition-all duration-300 hover:shadow-lg border border-white/35">
              <div className="flex items-center gap-4 mb-4 min-h-[64px] md:min-h-[72px]">
                <MessageSquare className="w-10 h-10 md:w-12 md:h-12 text-white flex-shrink-0" strokeWidth={1.5} />
                <div className="flex-1">
                  <h3 className="font-heading font-semibold text-lg md:text-xl text-text-on-dark leading-tight">Гибкая система скидок</h3>
                </div>
              </div>
              <p className="text-subtext-on-dark leading-relaxed mb-4 text-sm md:text-base min-h-[48px]">
                Индивидуальные условия для постоянных клиентов и крупных объёмов
              </p>
              <ul className="space-y-2.5 text-subtext-on-dark text-sm md:text-base">
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-white flex-shrink-0 mt-0.5" strokeWidth={2} />
                  <span><strong className="text-text-on-dark">Скидки от 500 кг</strong></span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-white flex-shrink-0 mt-0.5" strokeWidth={2} />
                  <span>Специальные условия для региональных компаний</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-white flex-shrink-0 mt-0.5" strokeWidth={2} />
                  <span>Бонусы для постоянных клиентов</span>
                </li>
              </ul>
            </div>

            <div className="surface-card terms-card rounded-lg p-6 md:p-8 flex flex-col h-full transition-all duration-300 hover:shadow-lg border border-white/35">
              <div className="flex items-center gap-4 mb-4 min-h-[64px] md:min-h-[72px]">
                <FileCheck className="w-10 h-10 md:w-12 md:h-12 text-white flex-shrink-0" strokeWidth={1.5} />
                <div className="flex-1">
                  <h3 className="font-heading font-semibold text-lg md:text-xl text-text-on-dark leading-tight">Удобная оплата</h3>
                </div>
              </div>
              <p className="text-subtext-on-dark leading-relaxed mb-4 text-sm md:text-base min-h-[48px]">
                Несколько вариантов оплаты и работа по договору
              </p>
              <ul className="space-y-2.5 text-subtext-on-dark text-sm md:text-base">
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-white flex-shrink-0 mt-0.5" strokeWidth={2} />
                  <span><strong className="text-text-on-dark">Безналичный расчёт</strong></span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-white flex-shrink-0 mt-0.5" strokeWidth={2} />
                  <span>Отсрочка для проверенных партнёров</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-white flex-shrink-0 mt-0.5" strokeWidth={2} />
                  <span>Полный пакет документов</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Delivery */}
      <section id="delivery" className="py-12 md:py-16 lg:py-24 px-4 md:px-6 bg-textured-light">
        <div className="max-w-[1200px] mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 md:gap-12 items-center">
            <div>
              <h2 className="font-heading font-bold text-2xl md:text-3xl lg:text-4xl mb-5 md:mb-6 text-text-on-light">
                Доставка <span style={{ color: '#7A8B6C' }}>и география</span>
              </h2>
              <p className="text-sm md:text-base text-subtext-on-light leading-relaxed mb-4 md:mb-6">
                Организуем доставку по всей территории России. Работаем с проверенными транспортными
                компаниями, гарантируем сохранность груза.
              </p>
              <div className="space-y-3 md:space-y-4">
                <div className="flex items-start gap-3 md:gap-4 card-soft p-4 md:p-5 rounded-xl transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                  <div className="w-10 h-10 md:w-11 md:h-11 rounded-lg bg-color-accent/10 flex items-center justify-center flex-shrink-0">
                    <Truck className="w-5 h-5 md:w-6 md:h-6 text-color-accent" strokeWidth={1.8} />
                  </div>
                  <div>
                    <p className="font-semibold mb-1 text-text-on-light text-sm md:text-base">Доставка по России</p>
                    <p className="text-xs md:text-sm text-subtext-on-light leading-relaxed">
                      Транспортными компаниями в любой регион
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3 md:gap-4 card-soft p-4 md:p-5 rounded-xl transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                  <div className="w-10 h-10 md:w-11 md:h-11 rounded-lg bg-color-accent/10 flex items-center justify-center flex-shrink-0">
                    <MapPin className="w-5 h-5 md:w-6 md:h-6 text-color-accent" strokeWidth={1.8} />
                  </div>
                  <div>
                    <p className="font-semibold mb-1 text-text-on-light text-sm md:text-base">Самовывоз</p>
                    <p className="text-xs md:text-sm text-subtext-on-light leading-relaxed">
                      Со склада в Краснодарском крае
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3 md:gap-4 card-soft p-4 md:p-5 rounded-xl transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                  <div className="w-10 h-10 md:w-11 md:h-11 rounded-lg bg-color-accent/10 flex items-center justify-center flex-shrink-0">
                    <Package className="w-5 h-5 md:w-6 md:h-6 text-color-accent" strokeWidth={1.8} />
                  </div>
                  <div>
                    <p className="font-semibold mb-1 text-text-on-light text-sm md:text-base">Надёжная упаковка</p>
                    <p className="text-xs md:text-sm text-subtext-on-light leading-relaxed">
                      Защита от влаги и повреждений при транспортировке
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="card-soft rounded-xl p-6 md:p-8 border border-color-accent-2/30">
              <h3 className="font-heading font-semibold text-lg md:text-xl mb-5 md:mb-6 text-text-on-light">
                Основные регионы поставок
              </h3>
              <div className="grid grid-cols-2 gap-3 md:gap-4">
                {[
                  'Москва и МО',
                  'Санкт-Петербург',
                  'Краснодар',
                  'Ростов-на-Дону',
                  'Екатеринбург',
                  'Новосибирск',
                  'Казань',
                  'Нижний Новгород',
                ].map((city) => (
                  <div key={city} className="flex items-center gap-2.5 transition-all duration-300 hover:translate-x-1">
                    <div className="w-1.5 h-1.5 bg-color-accent rounded-full shadow-sm"></div>
                    <span className="text-xs md:text-sm text-text-on-light">{city}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs md:text-sm text-subtext-on-light mt-5 md:mt-6 leading-relaxed">
                И другие города России — уточните у менеджера
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Quality Section */}
      <section className="fon-bg quality-bg py-12 md:py-16 lg:py-24 px-4 md:px-6">
        <div className="max-w-[1200px] mx-auto">
          <h2 className="font-heading font-bold text-2xl md:text-3xl lg:text-4xl mb-8 md:mb-12 text-text-on-dark">
            Качество и происхождение сырья
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
            <div className="surface-card quality-card rounded-lg p-6 md:p-8 flex flex-col h-full transition-all duration-300 hover:shadow-lg border border-white/35">
              <div className="flex items-center gap-4 mb-4">
                <Leaf className="w-10 h-10 md:w-12 md:h-12 text-white flex-shrink-0" strokeWidth={1.5} />
                <div className="flex-1">
                  <h3 className="font-heading font-semibold text-base md:text-lg text-text-on-dark">
                    Натуральное сырьё
                  </h3>
                </div>
              </div>
              <p className="text-subtext-on-dark text-sm leading-relaxed">
                Выращивается в <strong className="text-text-on-dark">экологически чистых регионах</strong> с соблюдением агротехнических норм
              </p>
            </div>

            <div className="surface-card quality-card rounded-lg p-6 md:p-8 flex flex-col h-full transition-all duration-300 hover:shadow-lg border border-white/35">
              <div className="flex items-center gap-4 mb-4">
                <Shield className="w-10 h-10 md:w-12 md:h-12 text-white flex-shrink-0" strokeWidth={1.5} />
                <div className="flex-1">
                  <h3 className="font-heading font-semibold text-base md:text-lg text-text-on-dark">
                    Контроль качества
                  </h3>
                </div>
              </div>
              <p className="text-subtext-on-dark text-sm leading-relaxed">
                <strong className="text-text-on-dark">Многоступенчатая проверка</strong> на всех этапах — от сбора до упаковки
              </p>
            </div>

            <div className="surface-card quality-card rounded-lg p-6 md:p-8 flex flex-col h-full transition-all duration-300 hover:shadow-lg border border-white/35">
              <div className="flex items-center gap-4 mb-4">
                <FileCheck className="w-10 h-10 md:w-12 md:h-12 text-white flex-shrink-0" strokeWidth={1.5} />
                <div className="flex-1">
                  <h3 className="font-heading font-semibold text-base md:text-lg text-text-on-dark">
                    Сертификация
                  </h3>
                </div>
              </div>
              <p className="text-subtext-on-dark text-sm leading-relaxed">
                Вся продукция имеет <strong className="text-text-on-dark">необходимые документы</strong> и сертификаты соответствия
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-16 md:py-20 lg:py-28 px-4 md:px-6 bg-textured-light">
        <div className="max-w-[1200px] mx-auto">
          <div className="card-soft rounded-2xl p-8 md:p-12 lg:p-16 text-center border border-color-accent-2/20">
            <h2 className="font-heading font-bold text-2xl md:text-3xl lg:text-4xl mb-4 md:mb-5 text-text-on-light leading-tight">
              Готовы начать <span style={{ color: '#7A8B6C' }}>сотрудничество?</span>
            </h2>
            <p className="text-base md:text-lg text-subtext-on-light mb-2 md:mb-3 max-w-2xl mx-auto leading-relaxed">
              Свяжитесь с нами через Telegram для уточнения условий и оформления заказа
            </p>
            <p className="text-sm md:text-base text-color-accent font-medium mb-8 md:mb-10 max-w-xl mx-auto">
              Получите прайс и условия за 1 минуту
            </p>
            <a
              href="https://t.me/agrosna1b_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 bg-color-accent text-white px-8 py-3.5 md:px-10 md:py-4 font-heading font-semibold text-base md:text-lg transition-all duration-300 hover:-translate-y-1 w-full sm:w-auto max-w-sm sm:max-w-none shadow-lg"
              style={{
                borderRadius: '12px',
                boxShadow: '0 4px 16px rgba(194, 68, 28, 0.25)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = '0 8px 24px rgba(194, 68, 28, 0.35)';
                e.currentTarget.style.backgroundColor = '#A83A18';
                e.currentTarget.style.transform = 'translateY(-3px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = '0 4px 16px rgba(194, 68, 28, 0.25)';
                e.currentTarget.style.backgroundColor = '#C2441C';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              Открыть Telegram
              <ArrowRight className="w-4 h-4 md:w-5 md:h-5" />
            </a>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}

export default App;
