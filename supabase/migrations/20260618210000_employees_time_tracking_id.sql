-- Matricule badgeuse / GTA (Cegid, etc.) pour matching import pointages
ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS time_tracking_id text;

CREATE INDEX IF NOT EXISTS idx_employees_company_time_tracking_id
  ON employees (company_id, time_tracking_id)
  WHERE time_tracking_id IS NOT NULL;

COMMENT ON COLUMN employees.time_tracking_id IS
  'Matricule badgeuse / GTA (ex. Cegid) — unique par entreprise si renseigné.';
