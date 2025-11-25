CREATE TABLE IF NOT EXISTS agent_logs (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,              -- setretail10 / testfile / etc
    request     JSONB NOT NULL,             -- параметры запроса
    status      TEXT NOT NULL,              -- success / error
    message     TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_created_at
    ON agent_logs(created_at DESC);
