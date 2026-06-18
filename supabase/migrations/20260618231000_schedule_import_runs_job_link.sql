-- Lien audit import pointages ↔ job async
-- Prérequis : schedule_import_runs (20260618211000) et schedule_import_jobs (20260618230000)
DO $$
BEGIN
  IF to_regclass('public.schedule_import_runs') IS NULL THEN
    RAISE EXCEPTION
      'schedule_import_runs absente : appliquer d''abord 20260618211000_schedule_import_runs.sql '
      'ou 20260618232000_schedule_import_bootstrap.sql';
  END IF;
  IF to_regclass('public.schedule_import_jobs') IS NULL THEN
    RAISE EXCEPTION
      'schedule_import_jobs absente : appliquer d''abord 20260618230000_schedule_import_jobs.sql '
      'ou 20260618232000_schedule_import_bootstrap.sql';
  END IF;
END $$;

ALTER TABLE schedule_import_runs
  ADD COLUMN IF NOT EXISTS import_job_id uuid REFERENCES schedule_import_jobs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS extraction_mode text,
  ADD COLUMN IF NOT EXISTS page_count integer,
  ADD COLUMN IF NOT EXISTS consensus_conflicts integer;

COMMENT ON COLUMN schedule_import_runs.import_job_id IS
  'Job async ayant produit cette proposition.';
COMMENT ON COLUMN schedule_import_runs.consensus_conflicts IS
  'Nombre de conflits vision/OCR résolus par consensus.';
