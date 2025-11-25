-- 002_events.sql
-- Модуль событий PrismaLite

-- 1. Тип приоритета события
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'event_severity') THEN
        CREATE TYPE event_severity AS ENUM ('A', 'B', 'C');
    END IF;
END$$;

-- 2. Таблица событий
CREATE TABLE IF NOT EXISTS public.events (
    id          BIGSERIAL PRIMARY KEY,
    receipt_id  BIGINT      NOT NULL REFERENCES public.receipts(id) ON DELETE CASCADE,
    position_id BIGINT      NULL REFERENCES public.receipt_positions(id) ON DELETE CASCADE,
    event_type  TEXT        NOT NULL,
    severity    event_severity NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    details     JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- 3. Индексы
CREATE INDEX IF NOT EXISTS idx_events_receipt_id  ON public.events (receipt_id);
CREATE INDEX IF NOT EXISTS idx_events_event_type  ON public.events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_created_at  ON public.events (created_at);
CREATE INDEX IF NOT EXISTS idx_events_severity    ON public.events (severity);
