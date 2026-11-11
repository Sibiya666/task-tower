-- Operator-applied transport schema; no native task/ownership state.
CREATE TABLE webhook_inbox (
    app_id BIGINT NOT NULL,
    installation_id BIGINT NOT NULL,
    repository_id BIGINT NOT NULL,
    delivery_id TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    event TEXT NOT NULL,
    action TEXT NOT NULL,
    body BYTEA,
    created_at DOUBLE PRECISION NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
    next_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    lease_consumer TEXT,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'failed', 'acked')),
    receipt_hash TEXT,
    PRIMARY KEY (app_id, installation_id, repository_id, delivery_id)
);
CREATE INDEX webhook_pending ON webhook_inbox (app_id, installation_id, repository_id, state, next_at);
