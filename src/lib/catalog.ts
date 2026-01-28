// Типы данных для каталога товаров

export interface Product {
  sku: string;
  name: string;
  descriptionShort: string;
  descriptionFull: string;
  priceRub: number;
  stock: number;
  photoUrl: string;
  tags: string[];
}

export interface CatalogResponse {
  generated_at: string;
  error?: string;
  items: Product[];
}

interface CacheEntry {
  data: CatalogResponse;
  cachedAt: number;
}

const CACHE_KEY = 'catalog_cache_v1';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 минут

export const PLACEHOLDER_IMAGE = `${import.meta.env.BASE_URL}placeholder.webp`;

/**
 * Проверяет, является ли URL безопасным для использования в img src
 */
function isValidImageUrl(url: string): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return ['http:', 'https:', 'data:'].includes(parsed.protocol);
  } catch {
    // Разрешаем относительные пути (начинающиеся с / или не содержащие :)
    return !url.includes(':') || url.startsWith('/');
  }
}

/**
 * Проверяет, есть ли товар в наличии
 */
export function isInStock(product: Product): boolean {
  return product.stock > 0;
}

/**
 * Возвращает текст CTA-кнопки в зависимости от наличия
 */
export function getCtaText(product: Product): string {
  return isInStock(product) ? 'Получить прайс' : 'Уточнить в Telegram';
}

/**
 * Генерирует deep link для Telegram бота с SKU товара
 */
export function getTelegramDeepLink(sku: string): string {
  return `https://t.me/agrosna1b_bot?start=${encodeURIComponent(`sku_${sku}`)}`;
}

/**
 * Парсит число из строки (поддержка запятой как десятичного разделителя)
 */
function parseNum(val: unknown): number {
  return parseFloat(String(val).replace(',', '.')) || 0;
}

/**
 * Валидирует и нормализует данные продукта
 */
function normalizeProduct(raw: Record<string, unknown>): Product {
  const photoUrlRaw = String(raw.photoUrl || '').trim();
  const photoUrl = isValidImageUrl(photoUrlRaw) ? photoUrlRaw : PLACEHOLDER_IMAGE;
  const tagsRaw = String(raw.tags || '');

  return {
    sku: String(raw.sku || ''),
    name: String(raw.name || ''),
    descriptionShort: String(raw.descriptionShort || ''),
    descriptionFull: String(raw.descriptionFull || ''),
    priceRub: parseNum(raw.priceRub),
    stock: parseNum(raw.stock),
    photoUrl: photoUrl || PLACEHOLDER_IMAGE,
    tags: tagsRaw
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean),
  };
}

/**
 * Получает кеш из sessionStorage
 */
function getCache(): CacheEntry | null {
  try {
    const cached = sessionStorage.getItem(CACHE_KEY);
    if (!cached) return null;

    const entry: CacheEntry = JSON.parse(cached);
    const age = Date.now() - entry.cachedAt;

    if (age > CACHE_TTL_MS) {
      sessionStorage.removeItem(CACHE_KEY);
      return null;
    }

    return entry;
  } catch {
    return null;
  }
}

/**
 * Сохраняет данные в кеш
 */
function setCache(data: CatalogResponse): void {
  try {
    const entry: CacheEntry = {
      data,
      cachedAt: Date.now(),
    };
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(entry));
  } catch {
    // Игнорируем ошибки записи (quota exceeded, private mode, etc)
  }
}

/**
 * Загружает каталог товаров из Google Apps Script
 */
export async function fetchCatalog(): Promise<CatalogResponse> {
  // Проверяем кеш
  const cached = getCache();
  if (cached) {
    return cached.data;
  }

  const appsScriptUrl = import.meta.env.VITE_APPS_SCRIPT_URL;

  if (!appsScriptUrl) {
    console.error('VITE_APPS_SCRIPT_URL не настроен');
    return {
      generated_at: new Date().toISOString(),
      error: 'Каталог не настроен',
      items: [],
    };
  }

  try {
    const response = await fetch(appsScriptUrl, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const rawData = await response.json();

    // Проверяем наличие ошибки от Apps Script
    if (rawData.error) {
      console.error('Apps Script error:', rawData.error);
      return {
        generated_at: rawData.generated_at || new Date().toISOString(),
        error: rawData.error,
        items: [],
      };
    }

    // Нормализуем items
    const items: Product[] = Array.isArray(rawData.items)
      ? rawData.items.map((item: Record<string, unknown>) =>
          normalizeProduct(item)
        )
      : [];

    const result: CatalogResponse = {
      generated_at: rawData.generated_at || new Date().toISOString(),
      items,
    };

    // Сохраняем в кеш
    setCache(result);

    return result;
  } catch (error) {
    console.error('Ошибка загрузки каталога:', error);
    return {
      generated_at: new Date().toISOString(),
      error: 'Не удалось загрузить каталог',
      items: [],
    };
  }
}
