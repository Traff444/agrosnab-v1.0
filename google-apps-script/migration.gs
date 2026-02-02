/**
 * МИГРАЦИЯ ТАБЛИЦЫ MAHORKA SHOP
 *
 * Этот скрипт автоматически приводит таблицу в порядок:
 * 1. Исправляет лист "Склад" (формулы, форматирование, чекбоксы)
 * 2. Очищает лист "Внесение" (удаляет мусорные строки)
 * 3. Очищает лист "Списание" (архивирует старые записи)
 * 4. Создаёт лист "README" с инструкцией
 *
 * КАК ИСПОЛЬЗОВАТЬ:
 * 1. Открыть таблицу в Google Sheets
 * 2. Расширения → Apps Script
 * 3. Вставить этот код
 * 4. Запустить функцию runMigration()
 * 5. Дать разрешения (первый раз)
 */

// =============================================================================
// КОНФИГУРАЦИЯ
// =============================================================================

/** Порог низкого остатка для жёлтого предупреждения */
const LOW_STOCK_THRESHOLD = 5;

// =============================================================================
// ГЛАВНАЯ ФУНКЦИЯ МИГРАЦИИ
// =============================================================================

function runMigration() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  // Подтверждение перед запуском
  const response = ui.alert(
    'Миграция таблицы',
    'Будут выполнены следующие действия:\n\n' +
    '1. Создание резервной копии таблицы\n' +
    '2. Исправление листа "Склад" (формулы, форматы)\n' +
    '3. Очистка листа "Внесение" (удаление мусора)\n' +
    '4. Очистка листа "Списание" (архивация старых)\n' +
    '5. Создание листа "README"\n\n' +
    'Продолжить?',
    ui.ButtonSet.YES_NO
  );

  if (response !== ui.Button.YES) {
    ui.alert('Миграция отменена');
    return;
  }

  let backupFile = null;

  try {
    Logger.log('=== НАЧАЛО МИГРАЦИИ ===');

    // 0. Создаём резервную копию
    const backupName = ss.getName() + '_Backup_' + new Date().toISOString().replace(/[:.]/g, '-');
    backupFile = DriveApp.getFileById(ss.getId()).makeCopy(backupName);
    Logger.log('Резервная копия создана: ' + backupFile.getUrl());

    // 1. Исправляем лист "Склад"
    migrateWarehouseSheet(ss);

    // 2. Очищаем лист "Внесение"
    migrateIntakeSheet(ss);

    // 3. Очищаем лист "Списание"
    migrateWriteoffSheet(ss);

    // 4. Создаём лист "README"
    createReadmeSheet(ss);

    Logger.log('=== МИГРАЦИЯ ЗАВЕРШЕНА ===');

    ui.alert(
      'Миграция завершена!',
      'Все листы обработаны успешно.\n\n' +
      'Проверьте:\n' +
      '• Колонки "Остаток_по_логам" и "Дельта" в листе "Склад"\n' +
      '• Условное форматирование (жёлтый/красный)\n' +
      '• Лист "README" с инструкцией\n\n' +
      'Резервная копия: ' + backupFile.getName(),
      ui.ButtonSet.OK
    );

  } catch (error) {
    Logger.log('ОШИБКА: ' + error.message);
    const backupInfo = backupFile ? '\n\nРезервная копия доступна: ' + backupFile.getName() : '';
    ui.alert('Ошибка миграции', error.message + backupInfo, ui.ButtonSet.OK);
    throw error;
  }
}

// =============================================================================
// 1. МИГРАЦИЯ ЛИСТА "СКЛАД"
// =============================================================================

function migrateWarehouseSheet(ss) {
  Logger.log('--- Миграция листа "Склад" ---');

  const sheet = ss.getSheetByName('Склад');
  if (!sheet) {
    throw new Error('Лист "Склад" не найден!');
  }

  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();

  if (lastRow < 2) {
    Logger.log('Лист "Склад" пустой, пропускаем');
    return;
  }

  // Получаем заголовки
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  Logger.log('Текущие заголовки: ' + headers.join(', '));

  // Находим индексы колонок (0-based)
  const colIndex = {
    sku: headers.indexOf('SKU'),
    price: findColumnIndex(headers, ['Цена_руб', 'Цена', 'Price']),
    startStock: findColumnIndex(headers, ['Стартовый_остаток', 'Начальный_остаток']),
    intake: findColumnIndex(headers, ['Внесено_всего', 'Внесено']),
    writeoff: findColumnIndex(headers, ['Списано_всего', 'Списано']),
    stock: findColumnIndex(headers, ['Остаток_расчет', 'Остаток', 'Stock']),
    active: findColumnIndex(headers, ['Активен', 'Active', 'Активный'])
  };

  Logger.log('Индексы колонок: ' + JSON.stringify(colIndex));

  // Валидация обязательных колонок
  if (colIndex.sku === -1) {
    throw new Error('Обязательная колонка "SKU" не найдена в листе "Склад"');
  }
  if (colIndex.startStock === -1) {
    throw new Error('Обязательная колонка "Стартовый_остаток" не найдена. Ожидаемые имена: Стартовый_остаток, Начальный_остаток');
  }
  if (colIndex.stock === -1) {
    throw new Error('Обязательная колонка остатка не найдена. Ожидаемые имена: Остаток_расчет, Остаток, Stock');
  }

  // Добавляем колонки если их нет (отслеживаем актуальную позицию)
  let currentLastCol = sheet.getLastColumn();
  let logStockCol = findColumnIndex(headers, ['Остаток_по_логам']);
  let deltaCol = findColumnIndex(headers, ['Дельта', 'Delta']);

  if (logStockCol === -1) {
    currentLastCol++;
    logStockCol = currentLastCol - 1; // 0-based индекс
    sheet.getRange(1, currentLastCol).setValue('Остаток_по_логам');
    Logger.log('Добавлена колонка "Остаток_по_логам" в позицию ' + currentLastCol);
  }

  // Обновляем currentLastCol после возможного добавления
  currentLastCol = sheet.getLastColumn();

  if (deltaCol === -1) {
    currentLastCol++;
    deltaCol = currentLastCol - 1; // 0-based индекс
    sheet.getRange(1, currentLastCol).setValue('Дельта');
    Logger.log('Добавлена колонка "Дельта" в позицию ' + currentLastCol);
  }

  // Получаем позиции колонок в логах для формул
  const logColumns = getLogSheetColumns(ss);

  // Batch-обработка данных для производительности
  const allData = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).getValues();
  const logStockFormulas = [];
  const deltaFormulas = [];
  const priceUpdates = [];
  const activeUpdates = [];

  for (let i = 0; i < allData.length; i++) {
    const rowData = allData[i];
    const row = i + 2;
    const sku = rowData[colIndex.sku];

    if (!sku) {
      logStockFormulas.push(['']);
      deltaFormulas.push(['']);
      continue;
    }

    // Собираем данные для исправления цены
    if (colIndex.price !== -1) {
      const priceValue = rowData[colIndex.price];
      if (typeof priceValue === 'string') {
        const cleanPrice = priceValue.replace(/[₽\s\u00A0]/g, '').trim();
        const numPrice = parseFloat(cleanPrice);
        if (!isNaN(numPrice)) {
          priceUpdates.push({ row: row, col: colIndex.price + 1, value: numPrice });
        }
      }
    }

    // Собираем данные для исправления "Активен"
    if (colIndex.active !== -1) {
      activeUpdates.push({ row: row, col: colIndex.active + 1, value: rowData[colIndex.active] });
    }

    // Формула Остаток_по_логам
    const startStockColLetter = getColLetter(colIndex.startStock + 1);
    const skuColLetter = getColLetter(colIndex.sku + 1);
    const logStockFormula = `=${startStockColLetter}${row}+SUMIF(Внесение!${logColumns.intake.sku}:${logColumns.intake.sku},${skuColLetter}${row},Внесение!${logColumns.intake.qty}:${logColumns.intake.qty})-SUMIF(Списание!${logColumns.writeoff.sku}:${logColumns.writeoff.sku},${skuColLetter}${row},Списание!${logColumns.writeoff.qty}:${logColumns.writeoff.qty})`;
    logStockFormulas.push([logStockFormula]);

    // Формула Дельта
    const stockColLetter = getColLetter(colIndex.stock + 1);
    const logStockColLetter = getColLetter(logStockCol + 1);
    const deltaFormula = `=${stockColLetter}${row}-${logStockColLetter}${row}`;
    deltaFormulas.push([deltaFormula]);
  }

  // Batch-применение формул
  if (logStockFormulas.length > 0) {
    sheet.getRange(2, logStockCol + 1, logStockFormulas.length, 1).setFormulas(logStockFormulas);
  }
  if (deltaFormulas.length > 0) {
    sheet.getRange(2, deltaCol + 1, deltaFormulas.length, 1).setFormulas(deltaFormulas);
  }

  // Применяем исправления цен
  priceUpdates.forEach(update => {
    sheet.getRange(update.row, update.col).setValue(update.value);
  });

  // Применяем чекбоксы для "Активен"
  if (activeUpdates.length > 0) {
    const activeRange = sheet.getRange(2, colIndex.active + 1, lastRow - 1, 1);
    activeRange.insertCheckboxes();
    activeUpdates.forEach(update => {
      const boolValue = parseBooleanValue(update.value);
      sheet.getRange(update.row, update.col).setValue(boolValue);
    });
  }

  // Добавляем примечания к заголовкам
  addHeaderNotes(sheet, colIndex, logStockCol, deltaCol);

  // Добавляем условное форматирование
  addConditionalFormatting(sheet, lastRow, colIndex.stock + 1, deltaCol + 1);

  Logger.log('Лист "Склад" обработан, строк: ' + (lastRow - 1));
}

/**
 * Преобразует значение в boolean
 */
function parseBooleanValue(value) {
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'string') {
    const lower = value.toLowerCase().trim();
    return (lower === 'да' || lower === 'yes' || lower === 'true' || lower === '1');
  }
  if (typeof value === 'number') {
    return value !== 0;
  }
  return false;
}

/**
 * Получает позиции колонок в логах (Внесение/Списание)
 */
function getLogSheetColumns(ss) {
  const result = {
    intake: { sku: 'C', qty: 'E' },
    writeoff: { sku: 'C', qty: 'E' }
  };

  // Проверяем лист "Внесение"
  const intakeSheet = ss.getSheetByName('Внесение');
  if (intakeSheet && intakeSheet.getLastColumn() > 0) {
    const headers = intakeSheet.getRange(1, 1, 1, intakeSheet.getLastColumn()).getValues()[0];
    const skuIdx = headers.indexOf('sku');
    const qtyIdx = headers.indexOf('qty');
    if (skuIdx !== -1) result.intake.sku = getColLetter(skuIdx + 1);
    if (qtyIdx !== -1) result.intake.qty = getColLetter(qtyIdx + 1);
  }

  // Проверяем лист "Списание"
  const writeoffSheet = ss.getSheetByName('Списание');
  if (writeoffSheet && writeoffSheet.getLastColumn() > 0) {
    const headers = writeoffSheet.getRange(1, 1, 1, writeoffSheet.getLastColumn()).getValues()[0];
    const skuIdx = headers.indexOf('sku');
    const qtyIdx = headers.indexOf('qty');
    if (skuIdx !== -1) result.writeoff.sku = getColLetter(skuIdx + 1);
    if (qtyIdx !== -1) result.writeoff.qty = getColLetter(qtyIdx + 1);
  }

  return result;
}

/**
 * Добавляет примечания к заголовкам
 */
function addHeaderNotes(sheet, colIndex, logStockCol, deltaCol) {
  const notes = {
    'SKU': 'Уникальный идентификатор товара. Формат: PRD-XXXXXX. НЕ РЕДАКТИРОВАТЬ после создания!',
    'Наименование': 'Название товара. Отображается покупателям.',
    'Описание_кратко': 'Краткое описание (1-2 предложения). Для карточки товара.',
    'Описание_полное': 'Полное описание. Для детальной страницы товара.',
    'Цена_руб': 'Цена в рублях. ТОЛЬКО число, без ₽ и пробелов!',
    'Стартовый_остаток': 'Начальный остаток при создании товара. НЕ РЕДАКТИРОВАТЬ после создания!',
    'Внесено_всего': 'ФОРМУЛА: сумма всех приходов из листа "Внесение". Не редактировать!',
    'Списано_всего': 'ФОРМУЛА: сумма всех списаний из листа "Списание". Не редактировать!',
    'Остаток_расчет': 'ФОРМУЛА: Стартовый + Внесено - Списано. Не редактировать!',
    'Остаток_по_логам': 'ПРОВЕРКА: независимый расчёт по логам. Должен совпадать с Остаток_расчет!',
    'Дельта': 'ПРОВЕРКА: разница между Остаток_расчет и Остаток_по_логам. ДОЛЖНА БЫТЬ 0!',
    'Поставщик_ID': 'Ссылка на поставщика из листа "Поставщики". Формат: SUP-XXXXXX.',
    'Фото_URL': 'Ссылка на фото товара (Cloudinary или Google Drive).',
    'Активен': 'Чекбокс: товар виден покупателям (TRUE) или скрыт (FALSE).',
    'Теги': 'Категории через запятую. Например: крепкая, золотая, премиум.'
  };

  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];

  for (let i = 0; i < headers.length; i++) {
    const header = headers[i];
    if (notes[header]) {
      sheet.getRange(1, i + 1).setNote(notes[header]);
    }
  }

  // Примечания для новых колонок
  sheet.getRange(1, logStockCol + 1).setNote(notes['Остаток_по_логам']);
  sheet.getRange(1, deltaCol + 1).setNote(notes['Дельта']);

  Logger.log('Примечания добавлены к заголовкам');
}

/**
 * Добавляет условное форматирование
 */
function addConditionalFormatting(sheet, lastRow, stockCol, deltaCol) {
  // Очищаем старые правила
  sheet.clearConditionalFormatRules();

  const rules = [];

  // 1. Жёлтый если остаток < LOW_STOCK_THRESHOLD и > 0
  if (stockCol > 0) {
    const stockRange = sheet.getRange(2, stockCol, lastRow - 1, 1);
    const yellowRule = SpreadsheetApp.newConditionalFormatRule()
      .whenNumberBetween(1, LOW_STOCK_THRESHOLD - 1)
      .setBackground('#FFF2CC') // Светло-жёлтый
      .setRanges([stockRange])
      .build();
    rules.push(yellowRule);

    // 2. Красный если остаток <= 0
    const redStockRule = SpreadsheetApp.newConditionalFormatRule()
      .whenNumberLessThanOrEqualTo(0)
      .setBackground('#F4CCCC') // Светло-красный
      .setFontColor('#990000')
      .setRanges([stockRange])
      .build();
    rules.push(redStockRule);
  }

  // 3. Красный если дельта ≠ 0
  if (deltaCol > 0) {
    const deltaRange = sheet.getRange(2, deltaCol, lastRow - 1, 1);
    const redDeltaRule = SpreadsheetApp.newConditionalFormatRule()
      .whenNumberNotEqualTo(0)
      .setBackground('#F4CCCC') // Светло-красный
      .setFontColor('#990000')
      .setBold(true)
      .setRanges([deltaRange])
      .build();
    rules.push(redDeltaRule);
  }

  sheet.setConditionalFormatRules(rules);
  Logger.log('Условное форматирование добавлено');
}

// =============================================================================
// 2. МИГРАЦИЯ ЛИСТА "ВНЕСЕНИЕ"
// =============================================================================

function migrateIntakeSheet(ss) {
  Logger.log('--- Миграция листа "Внесение" ---');

  const sheet = ss.getSheetByName('Внесение');
  if (!sheet) {
    Logger.log('Лист "Внесение" не найден, создаём пустой');
    createIntakeSheet(ss);
    return;
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    Logger.log('Лист "Внесение" пустой');
    return;
  }

  const data = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).getValues();
  const rowsToDelete = [];

  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const dateValue = row[0]; // Колонка A - дата

    // Проверяем валидность даты (ISO формат или Date объект)
    if (!isValidLogDate(dateValue)) {
      rowsToDelete.push(i + 2); // +2 потому что начинаем со строки 2
      Logger.log('Мусорная строка ' + (i + 2) + ': ' + dateValue);
    }
  }

  // Удаляем мусорные строки эффективно (группами)
  deleteRowsEfficiently(sheet, rowsToDelete);

  Logger.log('Лист "Внесение" очищен, удалено строк: ' + rowsToDelete.length);
}

/**
 * Создаёт пустой лист "Внесение" с правильными заголовками
 */
function createIntakeSheet(ss) {
  const sheet = ss.insertSheet('Внесение');
  const headers = [
    'date', 'operation_id', 'sku', 'name', 'qty',
    'stock_before', 'stock_after', 'reason', 'source',
    'actor_id', 'actor_username', 'note'
  ];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
  Logger.log('Создан лист "Внесение"');
}

// =============================================================================
// 3. МИГРАЦИЯ ЛИСТА "СПИСАНИЕ"
// =============================================================================

function migrateWriteoffSheet(ss) {
  Logger.log('--- Миграция листа "Списание" ---');

  const sheet = ss.getSheetByName('Списание');
  if (!sheet) {
    Logger.log('Лист "Списание" не найден, создаём пустой');
    createWriteoffSheet(ss);
    return;
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    Logger.log('Лист "Списание" пустой');
    return;
  }

  const data = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).getValues();
  const rowsToArchive = [];
  const rowsToDelete = [];

  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const dateValue = row[0]; // Колонка A - дата

    // Проверяем тип даты
    if (isExcelSerialDate(dateValue)) {
      // Excel serial date (46030 и т.д.) - архивируем
      rowsToArchive.push({index: i + 2, data: row});
    } else if (!isValidLogDate(dateValue)) {
      // Мусорная строка - удаляем
      rowsToDelete.push(i + 2);
      Logger.log('Мусорная строка ' + (i + 2) + ': ' + dateValue);
    }
  }

  // Создаём архивный лист если есть что архивировать
  if (rowsToArchive.length > 0) {
    archiveOldWriteoffs(ss, rowsToArchive);
  }

  // Удаляем строки снизу вверх (сначала архивные, потом мусорные)
  const allRowsToDelete = [
    ...rowsToArchive.map(r => r.index),
    ...rowsToDelete
  ].sort((a, b) => b - a); // Сортируем по убыванию

  // Удаляем строки эффективно (группами)
  deleteRowsEfficiently(sheet, allRowsToDelete);

  Logger.log('Лист "Списание" очищен, удалено строк: ' + allRowsToDelete.length);
}

/**
 * Создаёт пустой лист "Списание" с правильными заголовками
 */
function createWriteoffSheet(ss) {
  const sheet = ss.insertSheet('Списание');
  const headers = [
    'date', 'operation_id', 'sku', 'name', 'qty',
    'stock_before', 'stock_after', 'reason', 'source',
    'actor_id', 'actor_username', 'order_id', 'note'
  ];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
  Logger.log('Создан лист "Списание"');
}

/**
 * Архивирует старые записи с Excel-датами
 */
function archiveOldWriteoffs(ss, rowsToArchive) {
  let archiveSheet = ss.getSheetByName('Списание_Архив');

  if (!archiveSheet) {
    archiveSheet = ss.insertSheet('Списание_Архив');
    // Копируем заголовки из основного листа
    const mainSheet = ss.getSheetByName('Списание');
    const headers = mainSheet.getRange(1, 1, 1, mainSheet.getLastColumn()).getValues();
    archiveSheet.getRange(1, 1, 1, headers[0].length).setValues(headers);
    archiveSheet.setFrozenRows(1);
  }

  // Добавляем архивные строки
  const lastRow = archiveSheet.getLastRow();
  rowsToArchive.forEach((item, index) => {
    archiveSheet.getRange(lastRow + 1 + index, 1, 1, item.data.length).setValues([item.data]);
  });

  Logger.log('Архивировано старых записей: ' + rowsToArchive.length);
}

// =============================================================================
// 4. СОЗДАНИЕ ЛИСТА "README"
// =============================================================================

function createReadmeSheet(ss) {
  Logger.log('--- Создание листа "README" ---');

  // Удаляем старый README если есть
  const oldSheet = ss.getSheetByName('README');
  if (oldSheet) {
    ss.deleteSheet(oldSheet);
  }

  const sheet = ss.insertSheet('README');

  // Устанавливаем ширину колонок
  sheet.setColumnWidth(1, 300);
  sheet.setColumnWidth(2, 500);

  const content = [
    ['ИНСТРУКЦИЯ ПО РАБОТЕ С ТАБЛИЦЕЙ', ''],
    ['', ''],
    ['=== ЛИСТ "СКЛАД" ===', ''],
    ['SKU', 'Уникальный ID товара. Формат: PRD-XXXXXX. НЕ МЕНЯТЬ!'],
    ['Наименование', 'Название товара для покупателей'],
    ['Цена_руб', 'Цена. ТОЛЬКО число, без ₽!'],
    ['Стартовый_остаток', 'Начальный остаток. НЕ МЕНЯТЬ после создания!'],
    ['Внесено_всего', 'ФОРМУЛА. Сумма приходов. Не трогать!'],
    ['Списано_всего', 'ФОРМУЛА. Сумма списаний. Не трогать!'],
    ['Остаток_расчет', 'ФОРМУЛА. Текущий остаток. Не трогать!'],
    ['Остаток_по_логам', 'ПРОВЕРКА. Должен = Остаток_расчет'],
    ['Дельта', 'ПРОВЕРКА. ДОЛЖНА БЫТЬ 0! Красный = ошибка!'],
    ['Активен', 'Чекбокс. TRUE = виден, FALSE = скрыт'],
    ['', ''],
    ['=== ЦВЕТОВАЯ ИНДИКАЦИЯ ===', ''],
    ['Жёлтый фон', 'Остаток < ' + LOW_STOCK_THRESHOLD + ' штук. Пора заказывать!'],
    ['Красный фон (остаток)', 'Остаток = 0. Нет в наличии!'],
    ['Красный фон (дельта)', 'Дельта ≠ 0. ОШИБКА! Данные повреждены!'],
    ['', ''],
    ['=== ЛИСТ "ВНЕСЕНИЕ" ===', ''],
    ['Назначение', 'Журнал приходов товара (append-only)'],
    ['Редактирование', 'ЗАПРЕЩЕНО! Только бот добавляет записи'],
    ['Формат даты', 'ISO 8601: 2026-01-30T14:25:00'],
    ['', ''],
    ['=== ЛИСТ "СПИСАНИЕ" ===', ''],
    ['Назначение', 'Журнал списаний товара (append-only)'],
    ['Редактирование', 'ЗАПРЕЩЕНО! Только бот добавляет записи'],
    ['reason: order', 'Авто-списание при заказе'],
    ['reason: damage', 'Порча товара'],
    ['reason: gift', 'Подарок'],
    ['reason: correction', 'Ручная корректировка'],
    ['', ''],
    ['=== FAQ ===', ''],
    ['Как добавить товар?', 'Заполнить SKU, Наименование, Цена, Стартовый_остаток, Активен'],
    ['Как изменить цену?', 'Отредактировать ячейку Цена_руб (только число!)'],
    ['Как скрыть товар?', 'Снять чекбокс "Активен"'],
    ['Дельта не 0?', 'СРОЧНО свяжитесь с разработчиком!'],
    ['', ''],
    ['=== ВАЖНО ===', ''],
    ['НЕ РЕДАКТИРУЙТЕ', 'Листы "Внесение" и "Списание"'],
    ['НЕ МЕНЯЙТЕ', 'SKU и формулы в "Склад"'],
    ['НЕ УДАЛЯЙТЕ', 'Колонки с формулами'],
    ['', ''],
    ['Дата миграции:', new Date().toISOString()]
  ];

  sheet.getRange(1, 1, content.length, 2).setValues(content);

  // Форматирование
  sheet.getRange(1, 1).setFontSize(16).setFontWeight('bold');
  sheet.getRange('A3').setFontWeight('bold').setBackground('#E8F0FE');
  sheet.getRange('A15').setFontWeight('bold').setBackground('#E8F0FE');
  sheet.getRange('A20').setFontWeight('bold').setBackground('#E8F0FE');
  sheet.getRange('A25').setFontWeight('bold').setBackground('#E8F0FE');
  sheet.getRange('A33').setFontWeight('bold').setBackground('#E8F0FE');
  sheet.getRange('A39').setFontWeight('bold').setBackground('#FFF2CC');

  // Перемещаем README в начало
  ss.setActiveSheet(sheet);
  ss.moveActiveSheet(1);

  Logger.log('Лист "README" создан');
}

// =============================================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// =============================================================================

/**
 * Находит индекс колонки по возможным названиям
 */
function findColumnIndex(headers, possibleNames) {
  for (const name of possibleNames) {
    const index = headers.indexOf(name);
    if (index !== -1) return index;
  }
  return -1;
}

/**
 * Преобразует номер колонки в букву (1 -> A, 2 -> B, ...)
 */
function getColLetter(colNum) {
  let letter = '';
  let temp = colNum;
  while (temp > 0) {
    temp--;
    letter = String.fromCharCode(65 + (temp % 26)) + letter;
    temp = Math.floor(temp / 26);
  }
  return letter;
}

/**
 * Проверяет, является ли число Excel serial date (старые записи до интеграции бота)
 * Excel serial dates: дни с 1 января 1900
 * 40000 = 23 июня 2009
 * 46000 = 1 января 2026
 * Считаем "старыми" записи до 2024 года
 */
function isExcelSerialDate(value) {
  if (typeof value !== 'number') return false;

  // Проверяем диапазон разумных serial dates
  if (value < 1 || value > 100000) return false;

  // Конвертируем в JS дату для проверки
  // Excel epoch: 30 декабря 1899 (с учётом бага високосного 1900)
  const msPerDay = 24 * 60 * 60 * 1000;
  const excelEpoch = new Date(1899, 11, 30);
  const jsDate = new Date(excelEpoch.getTime() + value * msPerDay);

  // Разумная дата (2000-2100) и до даты интеграции бота (2024-01-01)
  const cutoffDate = new Date('2024-01-01');
  return jsDate.getFullYear() >= 2000 &&
         jsDate.getFullYear() <= 2100 &&
         jsDate < cutoffDate;
}

/**
 * Проверяет, является ли дата валидной для лога
 */
function isValidLogDate(value) {
  // Date объект (включая те, что конвертированы из serial)
  if (value instanceof Date) {
    const time = value.getTime();
    // Валидная дата после 2020 года
    return !isNaN(time) && time > new Date('2020-01-01').getTime();
  }

  // ISO строка (разные варианты)
  if (typeof value === 'string' && value.trim()) {
    // Более гибкий паттерн ISO: поддержка timezone, миллисекунд
    const isoPattern = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\.\d{1,3})?(Z|[+-]\d{2}:?\d{2})?)?$/;
    if (isoPattern.test(value.trim())) {
      const date = new Date(value);
      return !isNaN(date.getTime());
    }
  }

  // Число может быть Google Sheets native date (serial format)
  // Если это современная дата (после 2024), считаем валидной
  if (typeof value === 'number' && value > 0) {
    const msPerDay = 24 * 60 * 60 * 1000;
    const excelEpoch = new Date(1899, 11, 30);
    const jsDate = new Date(excelEpoch.getTime() + value * msPerDay);
    return jsDate.getFullYear() >= 2024;
  }

  return false;
}

/**
 * Эффективное удаление строк (группами непрерывных диапазонов)
 */
function deleteRowsEfficiently(sheet, rowNumbers) {
  if (!rowNumbers || rowNumbers.length === 0) return;

  // Сортируем по убыванию (удаляем снизу вверх)
  const sorted = [...rowNumbers].sort((a, b) => b - a);

  // Группируем непрерывные диапазоны
  let rangeStart = sorted[0];
  let rangeCount = 1;

  for (let i = 1; i <= sorted.length; i++) {
    if (i < sorted.length && sorted[i] === rangeStart - rangeCount) {
      rangeCount++;
    } else {
      // Удаляем диапазон
      const firstRow = rangeStart - rangeCount + 1;
      sheet.deleteRows(firstRow, rangeCount);

      if (i < sorted.length) {
        rangeStart = sorted[i];
        rangeCount = 1;
      }
    }
  }
}

// =============================================================================
// ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ОТЛАДКИ
// =============================================================================

/**
 * Показывает текущее состояние таблицы
 */
function showDiagnostics() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  const sheets = ss.getSheets().map(s => s.getName());

  let report = 'Листы в таблице:\n';
  sheets.forEach(name => {
    const sheet = ss.getSheetByName(name);
    report += `• ${name}: ${sheet.getLastRow()} строк\n`;
  });

  ui.alert('Диагностика', report, ui.ButtonSet.OK);
}

/**
 * Проверяет все "Дельта" в листе "Склад"
 */
function checkDeltas() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const sheet = ss.getSheetByName('Склад');

  if (!sheet) {
    ui.alert('Лист "Склад" не найден!');
    return;
  }

  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const deltaCol = headers.indexOf('Дельта');

  if (deltaCol === -1) {
    ui.alert('Колонка "Дельта" не найдена. Сначала запустите миграцию!');
    return;
  }

  const lastRow = sheet.getLastRow();
  const deltaValues = sheet.getRange(2, deltaCol + 1, lastRow - 1, 1).getValues();

  const problems = [];
  for (let i = 0; i < deltaValues.length; i++) {
    const delta = deltaValues[i][0];
    if (delta !== 0 && delta !== '') {
      const sku = sheet.getRange(i + 2, 1).getValue();
      problems.push(`${sku}: дельта = ${delta}`);
    }
  }

  if (problems.length === 0) {
    ui.alert('Все дельты = 0. Данные консистентны!');
  } else {
    ui.alert('ВНИМАНИЕ! Найдены проблемы:\n\n' + problems.join('\n'));
  }
}
