-- 003_incidents.sql
-- Миграция для таблиц инцидентов

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'incident_status') THEN
        CREATE TYPE incident_status AS ENUM ('open', 'in_progress', 'resolved', 'closed');
    END IF;
END$$;

-- Основная таблица инцидентов
CREATE TABLE IF NOT EXISTS public.incidents (
    id              BIGSERIAL PRIMARY KEY,
    receipt_id      BIGINT      NOT NULL REFERENCES public.receipts(id) ON DELETE CASCADE,
    main_event_type TEXT        NOT NULL,
    severity        event_severity NOT NULL,   -- тот же ENUM A/B/C
    status          incident_status NOT NULL DEFAULT 'open',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    details         JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- Связка инцидентов с событиями
CREATE TABLE IF NOT EXISTS public.incident_events (
    incident_id BIGINT NOT NULL REFERENCES public.incidents(id) ON DELETE CASCADE,
    event_id    BIGINT NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
    PRIMARY KEY (incident_id, event_id)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_incidents_receipt_id ON public.incidents (receipt_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status     ON public.incidents (status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity   ON public.incidents (severity);

-- Триггер на обновление updated_at
CREATE OR REPLACE FUNCTION public.set_incidents_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_incidents_set_updated_at'
    ) THEN
        CREATE TRIGGER trg_incidents_set_updated_at
        BEFORE UPDATE ON public.incidents
        FOR EACH ROW
        EXECUTE FUNCTION public.set_incidents_updated_at();
    END IF;
END$$;
