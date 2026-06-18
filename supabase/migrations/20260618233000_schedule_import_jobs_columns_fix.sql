-- Complète schedule_import_jobs si la table a été créée partiellement
ALTER TABLE schedule_import_jobs
  ADD COLUMN IF NOT EXISTS filename text,
  ADD COLUMN IF NOT EXISTS file_storage_path text,
  ADD COLUMN IF NOT EXISTS file_hash text,
  ADD COLUMN IF NOT EXISTS request_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS progress_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS proposal_json jsonb,
  ADD COLUMN IF NOT EXISTS page_audit_json jsonb,
  ADD COLUMN IF NOT EXISTS error_message text,
  ADD COLUMN IF NOT EXISTS extraction_mode text,
  ADD COLUMN IF NOT EXISTS tokens_used integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS completed_at timestamptz;

-- Recharge le cache schéma PostgREST (Supabase API)
NOTIFY pgrst, 'reload schema';
