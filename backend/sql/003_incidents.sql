-- 003_incidents.sql
-- Модуль инцидентов PrismaLite

-- Статус инцидента
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'incident_status') THEN
        CREATE TYPE incident_status AS ENUM ('new', 'in_progress', 'resolved', 'ignored');
    END IF;
END$$;

-- Таблица инцидентов
CREATE TABLE IF NOT EXISTS public.incidents (
    id              BIGSERIAL PRIMARY KEY,
    receipt_id      BIGINT NOT NULL REFERENCES public.receipts(id) ON DELETE CASCADE,
    severity        event_severity NOT NULL,  -- A / B / C (переиспользуем тип из events)
    status          incident_status NOT NULL DEFAULT 'new',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Для быстрого просмотра / аналитики
    shop            TEXT,
    cash            TEXT,
    shift           TEXT,
    number          TEXT,
    sale_time       TIMESTAMPTZ,

    -- Сводка по событиям
    event_types     TEXT[] NOT NULL DEFAULT '{}',
    events_count    INTEGER NOT NULL DEFAULT 0,

    -- Зарезервировано под видео (будем использовать позже)
    video_from      TIMESTAMPTZ,
    video_to        TIMESTAMPTZ,
    video_meta      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_incidents_receipt_id
    ON public.incidents (receipt_id);

CREATE INDEX IF NOT EXISTS idx_incidents_severity
    ON public.incidents (severity);

CREATE INDEX IF NOT EXISTS idx_incidents_status
    ON public.incidents (status);

CREATE INDEX IF NOT EXISTS idx_incidents_sale_time
    ON public.incidents (sale_time);


-- Связка инцидентов и событий
CREATE TABLE IF NOT EXISTS public.incident_events (
    id           BIGSERIAL PRIMARY KEY,
    incident_id  BIGINT NOT NULL REFERENCES public.incidents(id) ON DELETE CASCADE,
    event_id     BIGINT NOT NULL REFERENCES public.events(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_incident_events_unique
    ON public.incident_events (incident_id, event_id);

CREATE INDEX IF NOT EXISTS idx_incident_events_event_id
    ON public.incident_events (event_id);
