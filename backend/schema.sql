CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    improvement_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS financial_snapshots (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    request_id UUID NOT NULL,
    data JSONB NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, request_id)
);
CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY,
    snapshot_id UUID NOT NULL UNIQUE REFERENCES financial_snapshots(id) ON DELETE CASCADE,
    plan JSONB NOT NULL,
    explanation JSONB,
    status TEXT NOT NULL CHECK (status IN ('processing', 'complete')),
    ai_status TEXT NOT NULL,
    model_version TEXT,
    prompt_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    action_id TEXT NOT NULL,
    rating TEXT CHECK (rating IN ('helpful', 'not_helpful')),
    action_status TEXT CHECK (action_status IN ('accepted', 'completed', 'dismissed')),
    comment TEXT NOT NULL DEFAULT '',
    consented BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(analysis_id, action_id)
);
CREATE INDEX IF NOT EXISTS snapshots_user_history ON financial_snapshots(user_id, created_at DESC);
