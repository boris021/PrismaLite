-- ===========================================
-- PRISMALITE: БАЗА ДЛЯ ЧЕКОВ SetRetail
-- ===========================================

-- 1) Создаём БД и пользователя (если нужно).
-- Если БД и пользователь уже есть – этот блок можно пропустить
-- и оставить только раздел "Таблицы".
------------------------------------------------

-- создаём роль (пользователя)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'prismalite'
    ) THEN
        CREATE ROLE prismalite LOGIN PASSWORD 'PrismaLite123!';
    END IF;
END$$;

-- создаём базу, если её нет
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_database WHERE datname = 'prismalite'
    ) THEN
        CREATE DATABASE prismalite OWNER prismalite;
    END IF;
END$$;

-- дальше всё выполняем уже в БД prismalite
\connect prismalite;

-- права на схему public
GRANT ALL ON SCHEMA public TO prismalite;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO prismalite;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO prismalite;

------------------------------------------------
-- 2) Таблицы чеков
------------------------------------------------

-- Основная таблица чеков
CREATE TABLE IF NOT EXISTS receipts (
    id BIGSERIAL PRIMARY KEY,
    uid_purchase TEXT,                       -- UID из SetRetail, если используем
    shop TEXT NOT NULL,
    cash TEXT NOT NULL,
    shift TEXT NOT NULL,
    number TEXT NOT NULL,
    oper_day DATE NOT NULL,
    sale_time TIMESTAMPTZ NOT NULL,
    tab_number TEXT,
    user_name TEXT,
    amount NUMERIC(12,2),
    discount_amount NUMERIC(12,2),
    inn TEXT,
    status TEXT,
    is_refund BOOLEAN DEFAULT FALSE,
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (shop, cash, shift, number)
);

-- Позиции чека
CREATE TABLE IF NOT EXISTS receipt_positions (
    id BIGSERIAL PRIMARY KEY,
    receipt_id BIGINT NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    pos_order INT,
    goods_code TEXT,
    bar_code TEXT,
    count NUMERIC(12,3),
    cost NUMERIC(12,2),
    nds NUMERIC(12,2),
    is_void BOOLEAN DEFAULT FALSE,
    raw_json JSONB
);

-- Оплаты по чеку
CREATE TABLE IF NOT EXISTS receipt_payments (
    id BIGSERIAL PRIMARY KEY,
    receipt_id BIGINT NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    payment_type TEXT,              -- cash / card / coupon / bonus и т.п.
    amount NUMERIC(12,2),
    raw_json JSONB
);

------------------------------------------------
-- 3) Индексы
------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_receipts_operday
    ON receipts(oper_day);

CREATE INDEX IF NOT EXISTS idx_receipts_shop_cash_shift_number
    ON receipts(shop, cash, shift, number);

CREATE INDEX IF NOT EXISTS idx_positions_receipt_id
    ON receipt_positions(receipt_id);

CREATE INDEX IF NOT EXISTS idx_payments_receipt_id
    ON receipt_payments(receipt_id);

------------------------------------------------
-- 4) Пример партиционирования по дате (опционально)
-- потом можно генерить эти партиции скриптом
------------------------------------------------
-- Пример для дня 2025-11-25:
-- CREATE TABLE IF NOT EXISTS receipts_2025_11_25 PARTITION OF receipts
-- FOR VALUES FROM ('2025-11-25') TO ('2025-11-26');
