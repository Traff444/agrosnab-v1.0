/**
 * Google Apps Script Web App для чтения каталога товаров из Google Sheets
 * + Мониторинг, Валидация данных, Бэкапы
 *
 * Деплой:
 * 1. Google Sheets → Extensions → Apps Script
 * 2. Вставить этот код в Code.gs
 * 3. Deploy → New deployment → Type: Web app
 * 4. Execute as: Me
 * 5. Who has access: Anyone
 * 6. Скопировать URL вида https://script.google.com/macros/s/.../exec
 *
 * Настройка триггеров (Triggers → Add Trigger):
 * - dailyBackup: Daily timer, 03:00-04:00
 * - dailyHealthCheck: Daily timer, 09:00-10:00
 * - weeklyExportToDrive: Weekly timer, Sunday 02:00-03:00
 */

// ============================================================================
// КОНФИГУРАЦИЯ
// ============================================================================

const CONFIG = {
  SHEET_NAME: 'Склад',
  BACKUP_PREFIX: 'Бэкап_',
  BACKUP_DAYS_TO_KEEP: 7,
  DRIVE_BACKUP_FOLDER_NAME: 'Backups',
  DRIVE_BACKUPS_TO_KEEP: 4,
  // Telegram алерты (заполните для уведомлений)
  TELEGRAM_BOT_TOKEN: '',  // Токен бота для алертов
  TELEGRAM_CHAT_ID: '',    // ID владельца для алертов
};

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

// Регулярные выражения для валидации
const VALIDATORS = {
  SKU: /^PRD-[A-F0-9]{6}$/,
  URL: /^https?:\/\/.+/i
};

// ============================================================================
// WEB APP - КАТАЛОГ
// ============================================================================

function doGet(e) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet()
                              .getSheetByName(CONFIG.SHEET_NAME);
  if (!sheet) {
    return jsonResponse({ error: 'Sheet not found', items: [] }, e);
  }

  const data = sheet.getDataRange().getValues();
  const headers = data[0];

  const colMap = {};
  headers.forEach((h, i) => colMap[h] = i);

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

    if (!sku) continue;

    const activeRaw = row[colMap[COLUMNS.ACTIVE]];
    const activeStr = String(activeRaw).toLowerCase().trim();
    const isActive = activeRaw === true ||
                     activeStr === 'true' ||
                     activeStr === 'да' ||
                     activeStr === 'yes' ||
                     activeStr === '1';

    if (!isActive) continue;

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

// ============================================================================
// HEALTH CHECK & МОНИТОРИНГ
// ============================================================================

/**
 * Проверка здоровья системы. Запускать через триггер ежедневно.
 */
function dailyHealthCheck() {
  const issues = [];
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);

  // 1. Проверка доступности листа
  if (!sheet) {
    issues.push('CRITICAL: Лист "' + CONFIG.SHEET_NAME + '" не найден!');
    sendAlert(issues.join('\n'));
    return;
  }

  const data = sheet.getDataRange().getValues();
  const headers = data[0];

  const colMap = {};
  headers.forEach((h, i) => colMap[h] = i);

  // 2. Проверка обязательных колонок
  const requiredCols = [COLUMNS.SKU, COLUMNS.NAME, COLUMNS.PRICE, COLUMNS.ACTIVE];
  requiredCols.forEach(col => {
    if (colMap[col] === undefined) {
      issues.push('CRITICAL: Отсутствует колонка "' + col + '"');
    }
  });

  if (issues.length > 0) {
    sendAlert(issues.join('\n'));
    return;
  }

  // 3. Подсчёт товаров
  let activeCount = 0;
  let totalCount = 0;
  const invalidRows = [];

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const sku = String(row[colMap[COLUMNS.SKU]] || '').trim();

    if (!sku) continue;
    totalCount++;

    const activeRaw = row[colMap[COLUMNS.ACTIVE]];
    const activeStr = String(activeRaw).toLowerCase().trim();
    const isActive = activeRaw === true ||
                     activeStr === 'true' ||
                     activeStr === 'да' ||
                     activeStr === 'yes' ||
                     activeStr === '1';

    if (isActive) activeCount++;

    // Проверка валидности данных
    const rowIssues = validateRow(row, colMap, i + 1);
    if (rowIssues.length > 0) {
      invalidRows.push({ row: i + 1, issues: rowIssues });
    }
  }

  // 4. Проверка количества активных товаров
  if (activeCount === 0) {
    issues.push('WARNING: Нет активных товаров в каталоге!');
  }

  // 5. Проверка невалидных строк (показываем первые 5)
  if (invalidRows.length > 0) {
    issues.push('WARNING: Найдено ' + invalidRows.length + ' строк с проблемами:');
    invalidRows.slice(0, 5).forEach(r => {
      issues.push('  Строка ' + r.row + ': ' + r.issues.join(', '));
    });
    if (invalidRows.length > 5) {
      issues.push('  ... и ещё ' + (invalidRows.length - 5) + ' строк');
    }
  }

  // Отправка алерта если есть проблемы
  if (issues.length > 0) {
    const header = '📊 Health Check Report\n' +
                   'Всего товаров: ' + totalCount + '\n' +
                   'Активных: ' + activeCount + '\n\n';
    sendAlert(header + issues.join('\n'));
  }

  // Логирование
  Logger.log('Health check completed. Total: ' + totalCount + ', Active: ' + activeCount + ', Issues: ' + issues.length);
}

/**
 * Валидация одной строки данных
 */
function validateRow(row, colMap, rowNum) {
  const issues = [];

  // SKU формат
  const sku = String(row[colMap[COLUMNS.SKU]] || '').trim();
  if (sku && !VALIDATORS.SKU.test(sku)) {
    issues.push('Неверный формат SKU');
  }

  // Наименование не пустое
  const name = String(row[colMap[COLUMNS.NAME]] || '').trim();
  if (!name) {
    issues.push('Пустое наименование');
  }

  // Цена > 0
  const price = parseFloat(String(row[colMap[COLUMNS.PRICE]]).replace(',', '.')) || 0;
  if (price <= 0) {
    issues.push('Цена <= 0');
  }

  // Остаток >= 0
  const stock = parseFloat(String(row[colMap[COLUMNS.STOCK]]).replace(',', '.'));
  if (isNaN(stock) || stock < 0) {
    issues.push('Некорректный остаток');
  }

  // URL фото (если указан)
  if (colMap[COLUMNS.PHOTO] !== undefined) {
    const photoUrl = String(row[colMap[COLUMNS.PHOTO]] || '').trim();
    if (photoUrl && !VALIDATORS.URL.test(photoUrl)) {
      issues.push('Некорректный URL фото');
    }
  }

  return issues;
}

// ============================================================================
// ВАЛИДАЦИЯ ДАННЫХ (применение правил к таблице)
// ============================================================================

/**
 * Применить Data Validation к листу "Склад".
 * Запустить один раз вручную: Run → setupDataValidation
 */
function setupDataValidation() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);

  if (!sheet) {
    Logger.log('Лист "' + CONFIG.SHEET_NAME + '" не найден');
    return;
  }

  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const lastRow = sheet.getLastRow();
  const dataRows = lastRow - 1;

  if (dataRows <= 0) {
    Logger.log('Нет данных для валидации');
    return;
  }

  const colMap = {};
  headers.forEach((h, i) => colMap[h] = i + 1); // 1-indexed для Range

  // Активен: выпадающий список
  if (colMap[COLUMNS.ACTIVE]) {
    const activeCol = colMap[COLUMNS.ACTIVE];
    const activeRange = sheet.getRange(2, activeCol, dataRows, 1);
    const activeRule = SpreadsheetApp.newDataValidation()
      .requireValueInList(['да', 'нет'], true)
      .setAllowInvalid(false)
      .setHelpText('Выберите "да" или "нет"')
      .build();
    activeRange.setDataValidation(activeRule);
    Logger.log('Validation applied to column "Активен"');
  }

  // Цена: число > 0
  if (colMap[COLUMNS.PRICE]) {
    const priceCol = colMap[COLUMNS.PRICE];
    const priceRange = sheet.getRange(2, priceCol, dataRows, 1);
    const priceRule = SpreadsheetApp.newDataValidation()
      .requireNumberGreaterThan(0)
      .setAllowInvalid(true)
      .setHelpText('Цена должна быть больше 0')
      .build();
    priceRange.setDataValidation(priceRule);
    Logger.log('Validation applied to column "Цена"');
  }

  // Остаток: целое >= 0
  if (colMap[COLUMNS.STOCK]) {
    const stockCol = colMap[COLUMNS.STOCK];
    const stockRange = sheet.getRange(2, stockCol, dataRows, 1);
    const stockRule = SpreadsheetApp.newDataValidation()
      .requireNumberGreaterThanOrEqualTo(0)
      .setAllowInvalid(true)
      .setHelpText('Остаток должен быть >= 0')
      .build();
    stockRange.setDataValidation(stockRule);
    Logger.log('Validation applied to column "Остаток"');
  }

  Logger.log('Data validation setup complete');
}

/**
 * Защитить заголовки (первую строку) от редактирования.
 * Запустить один раз вручную.
 */
function protectHeaders() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);

  if (!sheet) return;

  // Удаляем старую защиту если есть
  const protections = sheet.getProtections(SpreadsheetApp.ProtectionType.RANGE);
  protections.forEach(p => {
    if (p.getDescription() === 'Защита заголовков') {
      p.remove();
    }
  });

  // Создаём защиту с предупреждением (warning-based)
  const headerRange = sheet.getRange(1, 1, 1, sheet.getLastColumn());
  const protection = headerRange.protect().setDescription('Защита заголовков');
  protection.setWarningOnly(true);

  Logger.log('Headers protected (warning mode)');
}

/**
 * Установить условное форматирование для подсветки проблем.
 * Запустить один раз вручную.
 */
function setupConditionalFormatting() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);

  if (!sheet) return;

  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();

  const colMap = {};
  headers.forEach((h, i) => colMap[h] = i + 1);

  // Удаляем старые правила
  sheet.clearConditionalFormatRules();
  const rules = [];

  // Красный фон: пустое наименование
  if (colMap[COLUMNS.NAME]) {
    const nameCol = String.fromCharCode(64 + colMap[COLUMNS.NAME]);
    const nameRange = sheet.getRange(nameCol + '2:' + nameCol + lastRow);
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('')
      .setBackground('#FFCDD2')
      .setRanges([nameRange])
      .build());
  }

  // Жёлтый фон: цена = 0
  if (colMap[COLUMNS.PRICE]) {
    const priceCol = String.fromCharCode(64 + colMap[COLUMNS.PRICE]);
    const priceRange = sheet.getRange(priceCol + '2:' + priceCol + lastRow);
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenNumberEqualTo(0)
      .setBackground('#FFF9C4')
      .setRanges([priceRange])
      .build());
  }

  // Жёлтый фон: остаток < 0
  if (colMap[COLUMNS.STOCK]) {
    const stockCol = String.fromCharCode(64 + colMap[COLUMNS.STOCK]);
    const stockRange = sheet.getRange(stockCol + '2:' + stockCol + lastRow);
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenNumberLessThan(0)
      .setBackground('#FFF9C4')
      .setRanges([stockRange])
      .build());
  }

  // Зелёный фон: товар активен
  if (colMap[COLUMNS.ACTIVE]) {
    const activeCol = String.fromCharCode(64 + colMap[COLUMNS.ACTIVE]);
    const activeRange = sheet.getRange(activeCol + '2:' + activeCol + lastRow);
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('да')
      .setBackground('#C8E6C9')
      .setRanges([activeRange])
      .build());
  }

  sheet.setConditionalFormatRules(rules);
  Logger.log('Conditional formatting applied: ' + rules.length + ' rules');
}

// ============================================================================
// БЭКАПЫ
// ============================================================================

/**
 * Ежедневный бэкап листа "Склад" в новый лист.
 * Настроить триггер: Daily timer, 03:00-04:00
 */
function dailyBackup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sourceSheet = ss.getSheetByName(CONFIG.SHEET_NAME);

  if (!sourceSheet) {
    Logger.log('Source sheet not found');
    return;
  }

  // Создание бэкап-листа
  const today = Utilities.formatDate(new Date(), 'Europe/Moscow', 'yyyyMMdd');
  const backupName = CONFIG.BACKUP_PREFIX + today;

  // Проверка существования
  let existingBackup = ss.getSheetByName(backupName);
  if (existingBackup) {
    ss.deleteSheet(existingBackup);
  }

  // Копирование
  const backupSheet = sourceSheet.copyTo(ss);
  backupSheet.setName(backupName);

  // Скрываем бэкап-лист
  backupSheet.hideSheet();

  Logger.log('Backup created: ' + backupName);

  // Очистка старых бэкапов
  cleanupOldBackups();
}

/**
 * Удаление бэкапов старше CONFIG.BACKUP_DAYS_TO_KEEP дней.
 */
function cleanupOldBackups() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - CONFIG.BACKUP_DAYS_TO_KEEP);

  sheets.forEach(sheet => {
    const name = sheet.getName();
    if (name.startsWith(CONFIG.BACKUP_PREFIX)) {
      const dateStr = name.replace(CONFIG.BACKUP_PREFIX, '');
      // Парсим YYYYMMDD
      if (dateStr.length === 8) {
        const year = parseInt(dateStr.substring(0, 4));
        const month = parseInt(dateStr.substring(4, 6)) - 1;
        const day = parseInt(dateStr.substring(6, 8));
        const backupDate = new Date(year, month, day);

        if (backupDate < cutoffDate) {
          ss.deleteSheet(sheet);
          Logger.log('Deleted old backup: ' + name);
        }
      }
    }
  });
}

/**
 * Еженедельный экспорт в Google Drive как CSV.
 * Настроить триггер: Weekly timer, Sunday 02:00-03:00
 */
function weeklyExportToDrive() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);

  if (!sheet) {
    Logger.log('Sheet not found');
    return;
  }

  // Получаем или создаём папку Backups
  const parentFolder = DriveApp.getFileById(ss.getId()).getParents().next();
  let backupFolder;

  const folders = parentFolder.getFoldersByName(CONFIG.DRIVE_BACKUP_FOLDER_NAME);
  if (folders.hasNext()) {
    backupFolder = folders.next();
  } else {
    backupFolder = parentFolder.createFolder(CONFIG.DRIVE_BACKUP_FOLDER_NAME);
  }

  // Создаём CSV
  const data = sheet.getDataRange().getValues();
  const csvContent = data.map(row =>
    row.map(cell => {
      const str = String(cell);
      // Экранируем кавычки и оборачиваем в кавычки если нужно
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return '"' + str.replace(/"/g, '""') + '"';
      }
      return str;
    }).join(',')
  ).join('\n');

  // Имя файла с датой
  const today = Utilities.formatDate(new Date(), 'Europe/Moscow', 'yyyy-MM-dd');
  const fileName = 'Склад_' + today + '.csv';

  // Создаём файл
  backupFolder.createFile(fileName, csvContent, 'text/csv');
  Logger.log('CSV export created: ' + fileName);

  // Очистка старых экспортов
  cleanupOldDriveBackups(backupFolder);
}

/**
 * Удаление старых CSV бэкапов из Drive.
 */
function cleanupOldDriveBackups(folder) {
  const files = folder.getFilesByType('text/csv');
  const fileList = [];

  while (files.hasNext()) {
    const file = files.next();
    fileList.push({
      file: file,
      date: file.getDateCreated()
    });
  }

  // Сортируем по дате (новые первые)
  fileList.sort((a, b) => b.date - a.date);

  // Удаляем лишние
  if (fileList.length > CONFIG.DRIVE_BACKUPS_TO_KEEP) {
    fileList.slice(CONFIG.DRIVE_BACKUPS_TO_KEEP).forEach(item => {
      item.file.setTrashed(true);
      Logger.log('Trashed old backup: ' + item.file.getName());
    });
  }
}

/**
 * Ручное восстановление из бэкапа.
 * Запустить вручную, указав имя бэкап-листа.
 */
function restoreFromBackup(backupSheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const backupSheet = ss.getSheetByName(backupSheetName);

  if (!backupSheet) {
    Logger.log('Backup sheet not found: ' + backupSheetName);
    return;
  }

  const targetSheet = ss.getSheetByName(CONFIG.SHEET_NAME);
  if (!targetSheet) {
    Logger.log('Target sheet not found');
    return;
  }

  // Очищаем целевой лист
  targetSheet.clearContents();

  // Копируем данные
  const data = backupSheet.getDataRange().getValues();
  targetSheet.getRange(1, 1, data.length, data[0].length).setValues(data);

  Logger.log('Restored from: ' + backupSheetName);
}

// ============================================================================
// УВЕДОМЛЕНИЯ
// ============================================================================

/**
 * Отправка алерта в Telegram.
 */
function sendAlert(message) {
  if (!CONFIG.TELEGRAM_BOT_TOKEN || !CONFIG.TELEGRAM_CHAT_ID) {
    Logger.log('Telegram credentials not configured. Alert: ' + message);
    return;
  }

  const url = 'https://api.telegram.org/bot' + CONFIG.TELEGRAM_BOT_TOKEN + '/sendMessage';

  const payload = {
    chat_id: CONFIG.TELEGRAM_CHAT_ID,
    text: '🔔 ТопХит Alert\n\n' + message,
    parse_mode: 'HTML'
  };

  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    UrlFetchApp.fetch(url, options);
    Logger.log('Alert sent to Telegram');
  } catch (e) {
    Logger.log('Failed to send Telegram alert: ' + e.message);
  }
}

// ============================================================================
// УТИЛИТЫ
// ============================================================================

/**
 * Получить список всех бэкапов.
 */
function listBackups() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  const backups = [];

  sheets.forEach(sheet => {
    const name = sheet.getName();
    if (name.startsWith(CONFIG.BACKUP_PREFIX)) {
      backups.push(name);
    }
  });

  Logger.log('Available backups: ' + backups.join(', '));
  return backups;
}

/**
 * Получить статистику каталога.
 */
function getCatalogStats() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);

  if (!sheet) return { error: 'Sheet not found' };

  const data = sheet.getDataRange().getValues();
  const headers = data[0];

  const colMap = {};
  headers.forEach((h, i) => colMap[h] = i);

  let total = 0;
  let active = 0;
  let totalStock = 0;
  let totalValue = 0;

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const sku = String(row[colMap[COLUMNS.SKU]] || '').trim();
    if (!sku) continue;

    total++;

    const activeRaw = row[colMap[COLUMNS.ACTIVE]];
    const activeStr = String(activeRaw).toLowerCase().trim();
    const isActive = activeRaw === true ||
                     activeStr === 'true' ||
                     activeStr === 'да' ||
                     activeStr === 'yes' ||
                     activeStr === '1';

    if (isActive) active++;

    const stock = parseFloat(String(row[colMap[COLUMNS.STOCK]]).replace(',', '.')) || 0;
    const price = parseFloat(String(row[colMap[COLUMNS.PRICE]]).replace(',', '.')) || 0;

    totalStock += stock;
    totalValue += stock * price;
  }

  const stats = {
    total_products: total,
    active_products: active,
    inactive_products: total - active,
    total_stock: totalStock,
    total_value_rub: Math.round(totalValue),
    generated_at: new Date().toISOString()
  };

  Logger.log(JSON.stringify(stats));
  return stats;
}

// ============================================================================
// НАСТРОЙКА ТРИГГЕРОВ
// ============================================================================

/**
 * Удалить все существующие триггеры проекта.
 */
function deleteAllTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    ScriptApp.deleteTrigger(trigger);
    Logger.log('Deleted trigger: ' + trigger.getHandlerFunction());
  });
  Logger.log('All triggers deleted. Total: ' + triggers.length);
}

/**
 * Настроить все триггеры автоматически.
 * Запустить один раз вручную: Run → setupTriggers
 */
function setupTriggers() {
  // Сначала удаляем старые триггеры
  deleteAllTriggers();

  // 1. Daily backup at 03:00
  ScriptApp.newTrigger('dailyBackup')
    .timeBased()
    .atHour(3)
    .everyDays(1)
    .inTimezone('Europe/Moscow')
    .create();
  Logger.log('Created trigger: dailyBackup at 03:00');

  // 2. Daily health check at 09:00
  ScriptApp.newTrigger('dailyHealthCheck')
    .timeBased()
    .atHour(9)
    .everyDays(1)
    .inTimezone('Europe/Moscow')
    .create();
  Logger.log('Created trigger: dailyHealthCheck at 09:00');

  // 3. Weekly CSV export on Sunday at 02:00
  ScriptApp.newTrigger('weeklyExportToDrive')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.SUNDAY)
    .atHour(2)
    .inTimezone('Europe/Moscow')
    .create();
  Logger.log('Created trigger: weeklyExportToDrive on Sunday at 02:00');

  Logger.log('All triggers configured successfully!');
}

/**
 * Показать текущие триггеры.
 */
function listTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  if (triggers.length === 0) {
    Logger.log('No triggers configured');
    return;
  }

  triggers.forEach(trigger => {
    Logger.log('Trigger: ' + trigger.getHandlerFunction() +
               ' | Type: ' + trigger.getEventType() +
               ' | ID: ' + trigger.getUniqueId());
  });
  Logger.log('Total triggers: ' + triggers.length);
}

/**
 * Полная инициализация системы.
 * Запустить один раз после деплоя.
 */
function initializeSystem() {
  Logger.log('=== Starting system initialization ===');

  // 1. Setup triggers
  setupTriggers();

  // 2. Setup data validation
  setupDataValidation();

  // 3. Setup conditional formatting
  setupConditionalFormatting();

  // 4. Protect headers
  protectHeaders();

  // 5. Create first backup
  dailyBackup();

  // 6. Run health check
  dailyHealthCheck();

  Logger.log('=== System initialization complete ===');
}
