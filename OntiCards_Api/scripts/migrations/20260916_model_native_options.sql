-- Additive migration. Existing model settings and indexes are preserved.
ALTER TABLE model_config ADD COLUMN IF NOT EXISTS api_options jsonb;
