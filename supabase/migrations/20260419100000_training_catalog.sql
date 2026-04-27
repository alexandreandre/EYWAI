-- Catalogue formations & inscriptions (Pack Talent)

CREATE TABLE IF NOT EXISTS training_catalog (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  title text NOT NULL,
  training_type text NOT NULL,
  provider text,
  duration_hours double precision,
  unit_cost_ht double precision,
  pedagogical_objective text,
  categories jsonb NOT NULL DEFAULT '[]'::jsonb,
  certification_id uuid REFERENCES certification_referential (id) ON DELETE SET NULL,
  status text NOT NULL DEFAULT 'active',
  program_url text,
  external_link text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_training_catalog_company ON training_catalog (company_id);
CREATE INDEX IF NOT EXISTS idx_training_catalog_status ON training_catalog (company_id, status);

CREATE TABLE IF NOT EXISTS training_enrollments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  training_id uuid NOT NULL REFERENCES training_catalog (id) ON DELETE CASCADE,
  employee_id uuid NOT NULL REFERENCES employees (id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'planned',
  planned_date date,
  completion_date date,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_training_enrollments_company ON training_enrollments (company_id);
CREATE INDEX IF NOT EXISTS idx_training_enrollments_training ON training_enrollments (training_id);
CREATE INDEX IF NOT EXISTS idx_training_enrollments_employee ON training_enrollments (employee_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_training_enrollments_active_unique
  ON training_enrollments (training_id, employee_id)
  WHERE status IN ('planned', 'in_progress');
