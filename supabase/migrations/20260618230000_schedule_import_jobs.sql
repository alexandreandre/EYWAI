-- Jobs async pour extraction IA des relevés de pointages
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

COMMENT ON TABLE schedule_import_jobs IS
  'Jobs async extraction relevés pointages (IA hybride vision + OCR par page).';
