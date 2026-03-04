import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Product, isInStock, getCtaText, getTelegramDeepLink, PLACEHOLDER_IMAGE } from '../lib/catalog';

interface ProductCardProps {
  product: Product;
}

export function ProductCard({ product }: ProductCardProps) {
  const { sku, name, descriptionShort, priceRub, stock, photoUrl } = product;
  const inStock = isInStock(product);
  const ctaText = getCtaText(product);
  const telegramLink = getTelegramDeepLink(sku);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.src = PLACEHOLDER_IMAGE;
  };

  const openLightbox = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setLightboxOpen(true);
  }, []);

  const closeLightbox = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setLightboxOpen(false);
  }, []);

  useEffect(() => {
    if (!lightboxOpen) return;
    document.body.style.overflow = 'hidden';
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLightboxOpen(false);
    };
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleEscape);
    };
  }, [lightboxOpen]);

  return (
    <div className="rounded-xl overflow-hidden transition-all duration-300 hover:shadow-xl hover:-translate-y-1 flex flex-col h-full group border-2 border-white/80" style={{ backgroundColor: '#FFF8F0' }}>
      <div className="relative w-full h-64 md:h-80 bg-[#FFF8F0] flex-shrink-0 overflow-hidden">
        {!inStock && (
          <div className="absolute top-3 right-3 z-10 bg-gray-600 text-white text-xs font-medium px-2.5 py-1 rounded-full shadow-md">
            Нет в наличии
          </div>
        )}
        <img
          src={photoUrl}
          alt={`${name} — купить махорку в Махорка Маркет`}
          loading="lazy"
          className="w-full h-full object-contain transition-transform duration-500 group-hover:scale-105 p-2"
          onError={handleImageError}
        />
        <button
          onClick={openLightbox}
          className="absolute bottom-2 right-2 z-10 bg-black/50 hover:bg-black/70 text-white rounded-full w-8 h-8 flex items-center justify-center transition-colors"
          aria-label="Увеличить фото"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
        </button>
      </div>

      {lightboxOpen && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/85 p-4"
          onClick={closeLightbox}
        >
          <button
            className="absolute top-4 right-4 text-white text-4xl font-light hover:text-gray-300 transition-colors z-10 leading-none w-10 h-10 flex items-center justify-center"
            onClick={closeLightbox}
            aria-label="Закрыть"
          >
            &times;
          </button>
          <img
            src={photoUrl}
            alt={name}
            className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            onError={handleImageError}
          />
        </div>,
        document.body
      )}

      <div className="px-3 pt-3 pb-3 md:px-4 md:pt-3 md:pb-4 flex flex-col flex-grow justify-between gap-2">
        <div>
          <h3 className="font-heading font-semibold text-sm md:text-base text-text-on-light leading-snug">
            {name}
          </h3>
          {descriptionShort && (
            <p className="text-xs text-subtext-on-light mt-0.5 leading-tight">{descriptionShort}</p>
          )}
        </div>

        <div className="flex items-center justify-between">
          {priceRub > 0 && (
            <span className="text-base font-bold text-color-accent">
              {priceRub.toLocaleString('ru-RU')} ₽
            </span>
          )}
          {inStock && (
            <span className="text-xs text-subtext-on-light">
              ✔ {product.infiniteStock ? 'В наличии' : `${stock} шт`}
            </span>
          )}
        </div>

        <a
          href={telegramLink}
          target="_blank"
          rel="noopener noreferrer"
          className={`block w-full transition-all duration-300 py-2 rounded-lg text-center font-medium text-sm shadow-sm ${
            inStock
              ? 'bg-[#6A7758] text-white border border-[#6A7758] hover:bg-color-accent hover:border-color-accent'
              : 'bg-gray-500 text-white border border-gray-500 hover:bg-gray-600 hover:border-gray-600'
          }`}
        >
          {ctaText}
        </a>
      </div>
    </div>
  );
}
