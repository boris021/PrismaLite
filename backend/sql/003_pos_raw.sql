-- 003_pos_raw.sql
-- Сырые события и документы SetPrisma v3 / Frontol Video API

CREATE TABLE IF NOT EXISTS pos_events (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,           -- 'setretail10', 'frontol6' и т.п.
    prefix          TEXT,                    -- ККМ / SSC / ...
    shop            INTEGER,
    device          INTEGER,
    code            INTEGER,                 -- Код события (4,5,6,18,25,37...)
    event_datetime  TIMESTAMPTZ,
    shift_number    INTEGER,
    tab_number      TEXT,
    employee        TEXT,
    document_number TEXT,
    document_type   TEXT,
    payload         JSONB NOT NULL,          -- Полный event из JSON
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pos_events_shop_time
    ON pos_events (shop, event_datetime);

CREATE INDEX IF NOT EXISTS idx_pos_events_code
    ON pos_events (code);

CREATE INDEX IF NOT EXISTS idx_pos_events_doc
    ON pos_events (document_type, document_number);

--------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pos_documents (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT NOT NULL,          -- 'setretail10', 'frontol6' ...
    prefix       TEXT,
    shop         INTEGER,
    shop_name    TEXT,
    device       INTEGER,
    device_name  TEXT,
    shift_number INTEGER,
    tab_number   TEXT,
    employee     TEXT,
    doc_type     TEXT,
    doc_number   TEXT,
    amount       NUMERIC(12, 2),
    status       INTEGER,
    doc_datetime TIMESTAMPTZ,
    raw          JSONB NOT NULL,         -- ВЕСЬ "document" как пришёл с кассы
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pos_documents_shop_time
    ON pos_documents (shop, doc_datetime);

CREATE INDEX IF NOT EXISTS idx_pos_documents_doc
    ON pos_documents (doc_type, doc_number);
