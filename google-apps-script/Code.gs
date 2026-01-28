/**
 * Google Apps Script Web App для чтения каталога товаров из Google Sheets
 *
 * Деплой:
 * 1. Google Sheets → Extensions → Apps Script
 * 2. Вставить этот код в Code.gs
 * 3. Deploy → New deployment → Type: Web app
 * 4. Execute as: Me
 * 5. Who has access: Anyone
 * 6. Скопировать URL вида https://script.google.com/macros/s/.../exec
 */

const SHEET_NAME = 'Склад';
const COLUMNS = {
  SKU: 'SKU',
  NAME: 'Наименование',
  DESC_SHORT: 'Описание_кратко',
  DESC_FULL: 'Описание_полное',
  PRICE: 'Цена_руб',
  STOCK: 'Остаток_расчет',
  PHOTO: 'Фото_URL',
  ACTIVE: 'Активен',
  TAGS: 'Теги'
};

function doGet(e) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet()
                              .getSheetByName(SHEET_NAME);
  if (!sheet) {
    return jsonResponse({ error: 'Sheet not found', items: [] }, e);
  }

  const data = sheet.getDataRange().getValues();
  const headers = data[0];

  // Динамический маппинг колонок
  const colMap = {};
  headers.forEach((h, i) => colMap[h] = i);

  // Проверка критичных колонок
  if (colMap[COLUMNS.SKU] === undefined || colMap[COLUMNS.ACTIVE] === undefined) {
    return jsonResponse({
      error: 'Missing required columns: SKU or Активен',
      items: []
    }, e);
  }

  const items = [];
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const sku = String(row[colMap[COLUMNS.SKU]] || '').trim();

    // Пропускаем пустые SKU
    if (!sku) continue;

    // Нормализация Активен (TRUE/true/"TRUE"/"Да"/1)
    const activeRaw = row[colMap[COLUMNS.ACTIVE]];
    const activeStr = String(activeRaw).toLowerCase().trim();
    const isActive = activeRaw === true ||
                     activeStr === 'true' ||
                     activeStr === 'да' ||
                     activeStr === 'yes' ||
                     activeStr === '1';

    if (!isActive) continue;

    // parseFloat с заменой запятой для локализованных чисел
    const parseNum = (val) => parseFloat(String(val).replace(',', '.')) || 0;

    items.push({
      sku: sku,
      name: String(row[colMap[COLUMNS.NAME]] || ''),
      descriptionShort: String(row[colMap[COLUMNS.DESC_SHORT]] || ''),
      descriptionFull: String(row[colMap[COLUMNS.DESC_FULL]] || ''),
      priceRub: parseNum(row[colMap[COLUMNS.PRICE]]),
      stock: parseNum(row[colMap[COLUMNS.STOCK]]),
      photoUrl: String(row[colMap[COLUMNS.PHOTO]] || ''),
      tags: String(row[colMap[COLUMNS.TAGS]] || '')
             .split(',').map(t => t.trim()).filter(Boolean)
    });
  }

  const response = {
    generated_at: new Date().toISOString(),
    items: items
  };

  return jsonResponse(response, e);
}

/**
 * Helper для JSON/JSONP ответа
 */
function jsonResponse(data, e) {
  const callback = e && e.parameter && e.parameter.callback;
  const jsonStr = JSON.stringify(data);

  if (callback) {
    return ContentService
      .createTextOutput(callback + '(' + jsonStr + ')')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }

  return ContentService
    .createTextOutput(jsonStr)
    .setMimeType(ContentService.MimeType.JSON);
}
