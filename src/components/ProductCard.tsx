interface ProductCardProps {
  name: string;
  weight: string;
  imageUrl: string;
}

export function ProductCard({ name, weight, imageUrl }: ProductCardProps) {
  return (
    <div className="rounded-xl overflow-hidden transition-all duration-300 hover:shadow-xl hover:-translate-y-1 flex flex-col h-full group border-2 border-white/80" style={{ backgroundColor: '#FFF8F0' }}>
      <div className="relative w-full h-48 md:h-56 bg-[#FFF8F0] flex-shrink-0 overflow-hidden p-2">
        <img
          src={imageUrl}
          alt={name}
          className="w-full h-full object-contain transition-transform duration-500"
        />
      </div>

      <div className="p-5 md:p-6 flex flex-col flex-grow justify-between">
        <div className="mb-4 min-h-[72px] flex flex-col justify-start">
          <h3 className="font-heading font-semibold text-base md:text-lg text-text-on-light leading-tight mb-2">
            {name}
          </h3>
          <p className="text-sm text-subtext-on-light">{weight}</p>
        </div>

        <a
          href="https://t.me/agrosna1b_bot"
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full bg-[#6A7758] text-white border border-[#6A7758] hover:bg-color-accent hover:border-color-accent transition-all duration-300 py-2.5 md:py-3 rounded-lg text-center font-medium text-sm shadow-sm"
        >
          Получить прайс
        </a>
      </div>
    </div>
  );
}
