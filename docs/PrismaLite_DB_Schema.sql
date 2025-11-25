-- PrismaLite database schema
-- Target: PostgreSQL 14+

BEGIN;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =======================
-- Core reference tables
-- =======================

CREATE TABLE IF NOT EXISTS tenants (
    id             SERIAL PRIMARY KEY,
    name           TEXT        NOT NULL,
    status         TEXT        NOT NULL DEFAULT 'active',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shops (
    id          SERIAL PRIMARY KEY,
    tenant_id   INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    address     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS registers (
    id               SERIAL PRIMARY KEY,
    tenant_id        INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    shop_id          INT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    pos_code         TEXT NOT NULL,
    integration_type TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, pos_code)
);

CREATE TABLE IF NOT EXISTS users (
    id           SERIAL PRIMARY KEY,
    tenant_id    INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    login        TEXT NOT NULL UNIQUE,
    role         TEXT NOT NULL,
    permissions  JSONB NOT NULL DEFAULT '{}'::JSONB,
    store_scope  INT[] NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cameras (
    id            SERIAL PRIMARY KEY,
    tenant_id     INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    shop_id       INT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    register_id   INT REFERENCES registers(id) ON DELETE SET NULL,
    name          TEXT NOT NULL,
    vendor        TEXT NOT NULL,
    channel       TEXT,
    rtsp_url      TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =======================
-- Events & transactional
-- =======================

CREATE TABLE IF NOT EXISTS events (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    INT NOT NULL,
    shop_id      INT NOT NULL,
    register_id  INT NOT NULL,
    check_id     BIGINT,
    event_code   INT NOT NULL,
    timestamp    TIMESTAMPTZ NOT NULL,
    cashier      TEXT,
    payload      JSONB NOT NULL DEFAULT '{}'::JSONB,
    source       TEXT,
    hash         TEXT NOT NULL UNIQUE,
    video_ts     TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

ALTER TABLE events
    ADD CONSTRAINT fk_events_register
    FOREIGN KEY (register_id) REFERENCES registers(id) ON DELETE CASCADE;

ALTER TABLE events
    ADD CONSTRAINT fk_events_shop
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE;

ALTER TABLE events
    ADD CONSTRAINT fk_events_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_code ON events(event_code);
CREATE INDEX IF NOT EXISTS idx_events_tenant ON events(tenant_id);

-- Example monthly partition
CREATE TABLE IF NOT EXISTS events_y2025m01
    PARTITION OF events FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE IF NOT EXISTS checks (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    shop_id       INT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    register_id   INT NOT NULL REFERENCES registers(id) ON DELETE CASCADE,
    check_number  TEXT NOT NULL,
    cashier       TEXT,
    start_ts      TIMESTAMPTZ NOT NULL,
    end_ts        TIMESTAMPTZ,
    total         NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    status        TEXT NOT NULL DEFAULT 'open',
    currency      TEXT NOT NULL DEFAULT 'RUB',
    metadata      JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, check_number)
) PARTITION BY RANGE (start_ts);

CREATE INDEX IF NOT EXISTS idx_checks_ts ON checks(start_ts);

-- =======================
-- Rules & incidents
-- =======================

CREATE TABLE IF NOT EXISTS rules (
    id          SERIAL PRIMARY KEY,
    tenant_id   INT REFERENCES tenants(id) ON DELETE CASCADE,
    code        TEXT NOT NULL UNIQUE,
    category    TEXT NOT NULL,
    description TEXT NOT NULL,
    severity    INT NOT NULL CHECK (severity BETWEEN 1 AND 5),
    params      JSONB NOT NULL DEFAULT '{}'::JSONB,
    scope       JSONB NOT NULL DEFAULT '{}'::JSONB,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS incidents (
    id             BIGSERIAL PRIMARY KEY,
    tenant_id      INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    rule_code      TEXT NOT NULL REFERENCES rules(code) ON DELETE RESTRICT,
    event_id       BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    check_id       BIGINT REFERENCES checks(id) ON DELETE SET NULL,
    shop_id        INT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    register_id    INT NOT NULL REFERENCES registers(id) ON DELETE CASCADE,
    timestamp      TIMESTAMPTZ NOT NULL,
    severity       INT NOT NULL CHECK (severity BETWEEN 1 AND 5),
    status         TEXT NOT NULL DEFAULT 'open',
    payload        JSONB NOT NULL DEFAULT '{}'::JSONB,
    assignee       INT REFERENCES users(id) ON DELETE SET NULL,
    video_link_id  BIGINT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

CREATE INDEX IF NOT EXISTS idx_incidents_rule ON incidents(rule_code);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_ts ON incidents(timestamp);

-- =======================
-- Video subsystem
-- =======================

CREATE TABLE IF NOT EXISTS video_segments (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    camera_id       INT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    start_ts        TIMESTAMPTZ NOT NULL,
    end_ts          TIMESTAMPTZ NOT NULL,
    path            TEXT NOT NULL,
    checksum        TEXT,
    size_bytes      BIGINT NOT NULL,
    retention_until TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (start_ts);

CREATE TABLE IF NOT EXISTS video_links (
    id           BIGSERIAL PRIMARY KEY,
    event_id     BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    camera_id    INT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    start_ts     TIMESTAMPTZ NOT NULL,
    end_ts       TIMESTAMPTZ NOT NULL,
    confidence   NUMERIC(5,2),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_video_links_event ON video_links(event_id);

-- =======================
-- Audit and licensing
-- =======================

CREATE TABLE IF NOT EXISTS audit_log (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id    INT REFERENCES users(id) ON DELETE SET NULL,
    action     TEXT NOT NULL,
    ts         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip         INET,
    details    JSONB NOT NULL DEFAULT '{}'::JSONB
) PARTITION BY RANGE (ts);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

CREATE TABLE IF NOT EXISTS licenses (
    id          SERIAL PRIMARY KEY,
    tenant_id   INT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,
    quota       INT NOT NULL CHECK (quota > 0),
    used        INT NOT NULL DEFAULT 0 CHECK (used >= 0),
    expires_at  TIMESTAMPTZ NOT NULL,
    last_check  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =======================
-- Helper functions/triggers
-- =======================

CREATE OR REPLACE FUNCTION trg_events_set_fk()
RETURNS TRIGGER AS $$
BEGIN
    SELECT tenant_id, shop_id INTO NEW.tenant_id, NEW.shop_id
    FROM registers
    WHERE id = NEW.register_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_event_fk ON events;
CREATE TRIGGER set_event_fk
BEFORE INSERT ON events
FOR EACH ROW EXECUTE FUNCTION trg_events_set_fk();

COMMIT;

