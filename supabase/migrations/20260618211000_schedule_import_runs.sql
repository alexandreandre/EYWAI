-- Traçabilité des imports de pointages (audit paie)
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
