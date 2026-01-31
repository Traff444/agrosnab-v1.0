"""Constants for Google Sheets operations."""

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

REQUIRED_COLUMNS = [
    "SKU",
    "Наименование",
    "Цена_руб",
    "Остаток_расчет",
    "Фото_URL",
    "Активен",
]

OPTIONAL_COLUMNS = [
    "Теги",
    "Описание_кратко",
    "Описание_полное",
    "Стартовый_остаток",
    "Внесено_всего",
    "Списано_всего",
    "Поставщик_ID",
    "last_intake_at",
    "last_intake_qty",
    "last_updated_by",
]

# Column aliases for code compatibility
COL_ALIASES = {
    "Цена": "Цена_руб",
    "Остаток": "Остаток_расчет",
    "Фото": "Фото_URL",
}

# Log sheet columns (unified format for Списание/Внесение)
LOG_COLUMNS = [
    "date",
    "operation_id",
    "sku",
    "name",
    "qty",
    "stock_before",
    "stock_after",
    "reason",
    "source",
    "actor_id",
    "actor_username",
    "note",
]

# CRM Leads columns
LEADS_COLUMNS = [
    "user_id",
    "username",
    "first_seen_at",
    "last_seen_at",
    "stage",
    "orders_count",
    "lifetime_value",
    "last_order_id",
    "consent_at",
    "consent_version",
    "phone",
    "tags",
    "notes",
]

# Deduplication lookback rows
DEDUP_LOOKBACK_ROWS = 200
