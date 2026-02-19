import { Product, isInStock, getCtaText, getTelegramDeepLink, PLACEHOLDER_IMAGE } from '../lib/catalog';

interface ProductCardProps {
  product: Product;
}

export function ProductCard({ product }: ProductCardProps) {
  const { sku, name, descriptionShort, priceRub, stock, photoUrl } = product;
  const inStock = isInStock(product);
  const ctaText = getCtaText(product);
  const telegramLink = getTelegramDeepLink(sku);

  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.src = PLACEHOLDER_IMAGE;
  };

  return (
    <div className="rounded-xl overflow-hidden transition-all duration-300 hover:shadow-xl hover:-translate-y-1 flex flex-col h-full group border-2 border-white/80" style={{ backgroundColor: '#FFF8F0' }}>
      <div className="relative w-full h-64 md:h-72 flex-shrink-0 overflow-hidden" style={{ backgroundColor: '#FFF8F0' }}>
        {!inStock && (
          <div className="absolute top-3 right-3 z-10 bg-gray-600 text-white text-xs font-medium px-2.5 py-1 rounded-full shadow-md">
            Нет в наличии
          </div>
        )}
        <img
          src={photoUrl}
          alt={name}
          className="w-full h-full object-contain transition-transform duration-500 group-hover:scale-105"
          onError={handleImageError}
        />
      </div>

      <div className="px-4 pt-3 pb-4 flex flex-col flex-grow justify-between">
        <div className="mb-3 flex flex-col justify-start">
          <h3 className="font-heading font-semibold text-sm md:text-base text-text-on-light leading-tight mb-1">
            {name}
          </h3>
          {descriptionShort && (
            <p className="text-xs text-subtext-on-light mb-1">{descriptionShort}</p>
          )}
          <div className="flex items-center gap-3">
            {priceRub > 0 && (
              <span className="text-sm font-medium text-color-accent">
                {priceRub.toLocaleString('ru-RU')} ₽
              </span>
            )}
            {stock > 0 && (
              <span className="text-xs text-subtext-on-light">
                В наличии: {stock} шт
              </span>
            )}
          </div>
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
