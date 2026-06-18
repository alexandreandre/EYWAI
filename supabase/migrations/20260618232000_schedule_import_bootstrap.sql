-- Bootstrap idempotent : tables import pointages (runs + jobs)
-- Utiliser si schedule_import_runs n'existe pas encore sur l'instance.

-- 1. Audit runs (doit exister avant le lien job)
CREATE TABLE IF NOT EXISTS schedule_import_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  filename text,
  detected_format text,
  period_start date,
  period_end date,
  employees_matched integer DEFAULT 0,
  days_written integer DEFAULT 0,
  warnings_json jsonb DEFAULT '[]'::jsonb,
  proposal_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE schedule_import_runs
  ADD COLUMN IF NOT EXISTS extraction_method text,
  ADD COLUMN IF NOT EXISTS raw_ocr_excerpt text,
  ADD COLUMN IF NOT EXISTS file_hash text,
  ADD COLUMN IF NOT EXISTS parse_confidence numeric,
  ADD COLUMN IF NOT EXISTS coverage_avg numeric;

CREATE INDEX IF NOT EXISTS idx_schedule_import_runs_company_created
  ON schedule_import_runs (company_id, created_at DESC);

ALTER TABLE schedule_import_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS schedule_import_runs_select_company ON schedule_import_runs;
CREATE POLICY schedule_import_runs_select_company
  ON schedule_import_runs FOR SELECT
  USING (
    company_id IN (
      SELECT uca.company_id FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS schedule_import_runs_insert_company ON schedule_import_runs;
CREATE POLICY schedule_import_runs_insert_company
  ON schedule_import_runs FOR INSERT
  WITH CHECK (
    company_id IN (
      SELECT uca.company_id FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

-- 2. Jobs async
CREATE TABLE IF NOT EXISTS schedule_import_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'extracting', 'completed', 'failed', 'cancelled')),
  filename text,
  file_storage_path text,
  file_hash text,
  request_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  progress_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  proposal_json jsonb,
  page_audit_json jsonb,
  error_message text,
  extraction_mode text,
  tokens_used integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

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

CREATE INDEX IF NOT EXISTS idx_schedule_import_jobs_company_status
  ON schedule_import_jobs (company_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_schedule_import_jobs_user_created
  ON schedule_import_jobs (user_id, created_at DESC);

ALTER TABLE schedule_import_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS schedule_import_jobs_select_company ON schedule_import_jobs;
CREATE POLICY schedule_import_jobs_select_company
  ON schedule_import_jobs FOR SELECT
  USING (
    company_id IN (
      SELECT uca.company_id FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS schedule_import_jobs_insert_company ON schedule_import_jobs;
CREATE POLICY schedule_import_jobs_insert_company
  ON schedule_import_jobs FOR INSERT
  WITH CHECK (
    company_id IN (
      SELECT uca.company_id FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS schedule_import_jobs_update_company ON schedule_import_jobs;
CREATE POLICY schedule_import_jobs_update_company
  ON schedule_import_jobs FOR UPDATE
  USING (
    company_id IN (
      SELECT uca.company_id FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

-- 3. Lien runs ↔ jobs (jobs doit exister pour la FK)
ALTER TABLE schedule_import_runs
  ADD COLUMN IF NOT EXISTS import_job_id uuid REFERENCES schedule_import_jobs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS extraction_mode text,
  ADD COLUMN IF NOT EXISTS page_count integer,
  ADD COLUMN IF NOT EXISTS consensus_conflicts integer;

COMMENT ON TABLE schedule_import_jobs IS
  'Jobs async extraction relevés pointages (IA hybride vision + OCR par page).';

NOTIFY pgrst, 'reload schema';
