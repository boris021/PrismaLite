-- =====================================================================
-- PrismaLite DB Schema (Core POS + Events)
-- Версия: 0.1
-- Назначение: базовая структура БД для ingest чеков и кассовых событий
-- =====================================================================

-- РЕКОМЕНДАЦИЯ:
-- Создавай отдельную БД prismalite и СХЕМУ prismalite, чтобы не гадить в public.

CREATE SCHEMA IF NOT EXISTS prismalite;
SET search_path TO prismalite, public;

-- =====================================================================
-- 1. СПРАВОЧНИКИ: МАГАЗИНЫ / КАССЫ / КАССИРЫ
-- =====================================================================

-- Магазин (филиал / торговая точка)
CREATE TABLE IF NOT EXISTS stores (
    id           BIGSERIAL PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,        -- внутренний код магазина (например, "ST01")
    name         TEXT NOT NULL,               -- человекочитаемое название
    address      TEXT,
    timezone     TEXT NOT NULL DEFAULT 'Asia/Almaty',
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Касса (POS-терминал)
CREATE TABLE IF NOT EXISTS tills (
    id           BIGSERIAL PRIMARY KEY,
    store_id     BIGINT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    code         TEXT NOT NULL,               -- ID кассы / фискальника (например, "KASSA-01")
    description  TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (store_id, code)
);

-- Кассир (оператор)
CREATE TABLE IF NOT EXISTS cashiers (
    id            BIGSERIAL PRIMARY KEY,
    external_id   TEXT,                       -- ID из внешней системы (Set Retail, 1С и т.п.)
    full_name     TEXT,
    short_name    TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (external_id)
);

-- =====================================================================
-- 2. ЧЕКИ И ПОЗИЦИИ
-- =====================================================================

-- Тип операции чека
CREATE TYPE receipt_operation_type AS ENUM ('SALE', 'REFUND', 'RETURN', 'OTHER');

-- Чек (документ)
CREATE TABLE IF NOT EXISTS receipts (
    id                 BIGSERIAL PRIMARY KEY,
    store_id           BIGINT NOT NULL REFERENCES stores(id) ON DELETE RESTRICT,
    till_id            BIGINT NOT NULL REFERENCES tills(id) ON DELETE RESTRICT,
    cashier_id         BIGINT REFERENCES cashiers(id) ON DELETE SET NULL,

    fiscal_doc_number  TEXT,                 -- номер фискального документа
    operation_type     receipt_operation_type NOT NULL DEFAULT 'SALE',
    business_date      DATE NOT NULL,        -- дата смены (по магазину)
    opened_at          TIMESTAMPTZ NOT NULL, -- время открытия документа
    closed_at          TIMESTAMPTZ,          -- время закрытия (может быть NULL, если прерван)

    total_amount       NUMERIC(12, 2),       -- итог по чеку
    total_discount     NUMERIC(12, 2),
    total_cash         NUMERIC(12, 2),
    total_cashless     NUMERIC(12, 2),

    is_canceled        BOOLEAN NOT NULL DEFAULT FALSE,
    is_copy            BOOLEAN NOT NULL DEFAULT FALSE,

    raw_source_id      TEXT,                 -- ID сырых логов / файла (для отладки)
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_receipts_store_date
    ON receipts (store_id, business_date);

CREATE INDEX IF NOT EXISTS idx_receipts_till_datetime
    ON receipts (till_id, opened_at);

-- Позиция чека
CREATE TABLE IF NOT EXISTS receipt_items (
    id              BIGSERIAL PRIMARY KEY,
    receipt_id      BIGINT NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    line_number     INTEGER NOT NULL,              -- номер строки в чеке
    sku             TEXT,                          -- внутренний код товара
    barcode         TEXT,                          -- штрихкод
    name            TEXT,
    quantity        NUMERIC(12, 3) NOT NULL DEFAULT 0,
    price           NUMERIC(12, 2) NOT NULL DEFAULT 0,
    amount          NUMERIC(12, 2) NOT NULL DEFAULT 0,

    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    discount_reason TEXT,
    tax_rate        NUMERIC(5, 2),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_receipt_items_unique_line
    ON receipt_items (receipt_id, line_number);

-- =====================================================================
-- 3. СПРАВОЧНИКИ СОБЫТИЙ
-- =====================================================================

-- Категория события (укрупнённая)
CREATE TABLE IF NOT EXISTS event_categories (
    id        SMALLSERIAL PRIMARY KEY,
    code      TEXT NOT NULL UNIQUE,          -- технический код (AUTH, DOC, ITEM, PAYMENT, CASHDRAWER, REPORT, OPERATOR, ERROR, ETC)
    name      TEXT NOT NULL                  -- Человекочитаемое название
);

-- Тип события (одна запись на каждый код из События.txt)
CREATE TABLE IF NOT EXISTS event_types (
    id              SMALLSERIAL PRIMARY KEY,
    code            INTEGER NOT NULL UNIQUE, -- числовой код события из Set Retail / логов
    category_id     SMALLINT NOT NULL REFERENCES event_categories(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,           -- краткое название
    description     TEXT,                    -- более подробное описание
    is_critical     BOOLEAN NOT NULL DEFAULT FALSE,  -- будет ли по умолчанию влиять на инциденты
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Базовое наполнение справочника категорий
INSERT INTO event_categories (code, name) VALUES
    ('AUTH',       'Авторизация и режимы'),
    ('DOC',        'Документы (чеки и операции)'),
    ('ITEM',       'Товарные операции'),
    ('CARD_COUPON','Карты, купоны и скидки'),
    ('PAYMENT',    'Оплаты'),
    ('TOTAL',      'Финальные операции по чеку'),
    ('CASHDRAWER', 'Денежный ящик'),
    ('REPORT',     'Отчёты кассы'),
    ('OPERATOR',   'Общение с оператором'),
    ('ERROR',      'Ошибки и отказы')
ON CONFLICT (code) DO NOTHING;

-- Базовое наполнение типов событий (по файлу События.txt)

INSERT INTO event_types (code, category_id, name, description, is_critical)
SELECT v.code,
       c.id AS category_id,
       v.name,
       v.description,
       v.is_critical
FROM (
    VALUES
        (2,   'AUTH',       'Отказ в авторизации',                       'Неуспешная попытка входа кассира', TRUE),
        (4,   'AUTH',       'Вход в режим администратора',               'Переход кассы в режим администратора', TRUE),
        (5,   'AUTH',       'Выход из режима администратора',            'Выход из режима администратора', FALSE),

        (11,  'DOC',        'Начало документа',                          'Открытие документа (чека/операции)', FALSE),
        (12,  'DOC',        'Конец документа',                           'Закрытие документа (чека/операции)', FALSE),
        (13,  'DOC',        'Аннулирование документа',                   'Полная отмена документа', TRUE),
        (15,  'DOC',        'Получение документа',                       'Загрузка / получение документа', FALSE),
        (16,  'DOC',        'Отмена документа',                          'Отмена проведения документа', TRUE),

        (20,  'ITEM',       'Добавление товарной позиции',               'Добавление товара в чек', FALSE),
        (22,  'ITEM',       'Отказ в добавлении товара',                 'Ошибка при добавлении товара', TRUE),
        (23,  'ITEM',       'Отмена товара',                             'Отмена позиции в чеке', TRUE),
        (24,  'ITEM',       'Удаление товара',                           'Удаление позиции из чека', TRUE),
        (25,  'ITEM',       'Изменение количества товара',               'Изменение количества по позиции', FALSE),
        (27,  'ITEM',       'Сканирование марки',                        'Сканирование маркированного товара', FALSE),
        (34,  'ITEM',       'Отклонение марки',                          'Отклонение кода марки', TRUE),
        (35,  'ITEM',       'Отказ в изменении количества товара',       'Ошибка при изменении количества', TRUE),
        (38,  'ITEM',       'Переход на чековую позицию по ш/к',         'Переход к строке чека по штрихкоду', FALSE),
        (39,  'ITEM',       'Сканирование вне чека',                     'Сканирование товара при отсутствии открытого документа', TRUE),

        (41,  'CARD_COUPON','Отказ в добавлении карты',                  'Ошибка при добавлении карты лояльности/оплаты', TRUE),
        (50,  'CARD_COUPON','Добавление купона',                         'Добавление купона к чеку', FALSE),
        (51,  'CARD_COUPON','Отказ в добавлении купона',                 'Ошибка при добавлении купона', TRUE),
        (60,  'CARD_COUPON','Назначение скидки',                         'Применение скидки к чеку/позиции', FALSE),

        (70,  'PAYMENT',    'Добавление оплаты наличными',               'Внесение наличной оплаты', FALSE),
        (72,  'PAYMENT',    'Удаление оплаты',                           'Удаление строки оплаты', TRUE),
        (73,  'PAYMENT',    'Ввод оплаты безналичными',                  'Оплата картой или иным безналичным способом', FALSE),

        (90,  'TOTAL',      'Подытог',                                   'Расчёт промежуточного итога по чеку', FALSE),
        (91,  'TOTAL',      'Отмена расчёта',                            'Отмена расчёта по чеку', TRUE),
        (92,  'TOTAL',      'Регистрация чека',                          'Финальная регистрация чека', TRUE),
        (93,  'TOTAL',      'Копия чека',                                'Печать копии чека', FALSE),

        (100, 'CASHDRAWER', 'Открыт денежный ящик',                      'Открытие денежного ящика', FALSE),
        (103, 'CASHDRAWER', 'Закрыт денежный ящик',                      'Закрытие денежного ящика', FALSE),
        (115, 'CASHDRAWER', 'Открыт денежный ящик по кнопке',            'Открытие денежного ящика вручную (по кнопке)', TRUE),

        (105, 'REPORT',     'Печать X-отчета',                           'Печать промежуточного отчёта (X-отчёт)', FALSE),
        (106, 'REPORT',     'Печать Z-отчета',                           'Печать итогового отчёта смены (Z-отчёт)', TRUE),

        (111, 'OPERATOR',   'Запрос оператору',                          'Запрос кассира к оператору/супервизору', FALSE),
        (112, 'OPERATOR',   'Ответ оператора',                           'Ответ оператора/супервизора', FALSE),

        (201, 'ERROR',      'Отказ в отмене товара',                     'Ошибка при попытке отменить товар', TRUE),
        (202, 'ERROR',      'Отказ в удалении товара',                   'Ошибка при попытке удалить товар', TRUE)
) AS v (code, category_code, name, description, is_critical)
JOIN event_categories c
  ON c.code = v.category_code
ON CONFLICT (code) DO NOTHING;

-- =====================================================================
-- 4. ТАБЛИЦА СОБЫТИЙ
-- =====================================================================

-- Источник события: pos (от кассы), agent (агент / коннектор), system (системное), other
CREATE TYPE event_source_type AS ENUM ('pos', 'agent', 'system', 'other');

CREATE TABLE IF NOT EXISTS events (
    id              BIGSERIAL PRIMARY KEY,
    store_id        BIGINT NOT NULL REFERENCES stores(id) ON DELETE RESTRICT,
    till_id         BIGINT REFERENCES tills(id) ON DELETE SET NULL,
    cashier_id      BIGINT REFERENCES cashiers(id) ON DELETE SET NULL,
    receipt_id      BIGINT REFERENCES receipts(id) ON DELETE SET NULL,

    event_type_id   SMALLINT NOT NULL REFERENCES event_types(id) ON DELETE RESTRICT,
    event_code      INTEGER NOT NULL,             -- дублируем числовой код для удобства индексации
    source          event_source_type NOT NULL DEFAULT 'pos',

    occurred_at     TIMESTAMPTZ NOT NULL,         -- фактическое время на кассе
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(), -- время получения системой

    payload         JSONB,                        -- сырые данные события (штрихкоды, суммы, GUID и т.п.)
    raw_line        TEXT,                         -- исходная строка лога (если есть)

    correlation_id  TEXT,                         -- связь с более крупными сущностями / внешними системами
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Индексы для быстрых выборок событий
CREATE INDEX IF NOT EXISTS idx_events_store_time
    ON events (store_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_events_type_time
    ON events (event_type_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_events_receipt
    ON events (receipt_id);

CREATE INDEX IF NOT EXISTS idx_events_code_time
    ON events (event_code, occurred_at);

-- =====================================================================
-- TODO (следующие шаги по схеме, будут дополняться):
--  - таблицы cameras, recorders, video_segments
--  - таблицы incidents и связки incident_events
--  - пользователи системы (security_analysts, admins)
--  - вспомогательные справочники (тип кассы, тип магазина и т.п.)
-- =====================================================================
