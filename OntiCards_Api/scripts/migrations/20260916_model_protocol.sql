-- Run once before starting the updated API on an existing installation.
-- Idempotent; existing URLs, keys, model names and vector indexes are untouched.
ALTER TABLE model_config
    ADD COLUMN IF NOT EXISTS api_protocol varchar(32) NOT NULL DEFAULT 'auto',
    ADD COLUMN IF NOT EXISTS embedding_dimensions integer;
