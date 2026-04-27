-- Objectifs & KPI (Pack Talent) — services + objectifs + jalons + check-ins
-- Ticket 1 : employee_objectives, objective_milestones, objective_checkins

CREATE TABLE IF NOT EXISTS company_services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_company_services_company ON company_services (company_id);

ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS service_id uuid REFERENCES company_services (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_employees_service ON employees (service_id);

CREATE TABLE IF NOT EXISTS employee_objectives (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  employee_id uuid REFERENCES employees (id) ON DELETE CASCADE,
  service_id uuid REFERENCES company_services (id) ON DELETE SET NULL,
  parent_objective_id uuid REFERENCES employee_objectives (id) ON DELETE SET NULL,
  title text NOT NULL,
  type text NOT NULL,
  period_year integer NOT NULL,
  status text NOT NULL DEFAULT 'active',
  description text,
  kpi_label text,
  kpi_unit text,
  kpi_target_value double precision,
  kpi_initial_value double precision,
  due_date date,
  weight double precision,
  annual_review_id uuid,
  notes text,
  evaluation_date date,
  final_achievement_rate double precision,
  evaluation_comment text,
  evaluated_in_review_id uuid,
  last_modified_by uuid,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_employee_objectives_company ON employee_objectives (company_id);
CREATE INDEX IF NOT EXISTS idx_employee_objectives_employee ON employee_objectives (employee_id);
CREATE INDEX IF NOT EXISTS idx_employee_objectives_service ON employee_objectives (service_id);
CREATE INDEX IF NOT EXISTS idx_employee_objectives_period ON employee_objectives (company_id, period_year);
CREATE INDEX IF NOT EXISTS idx_employee_objectives_parent ON employee_objectives (parent_objective_id);

CREATE TABLE IF NOT EXISTS objective_milestones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  objective_id uuid NOT NULL REFERENCES employee_objectives (id) ON DELETE CASCADE,
  milestone_date date NOT NULL,
  expected_value double precision NOT NULL,
  actual_value double precision,
  comment text,
  updated_by uuid,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_objective_milestones_objective ON objective_milestones (objective_id);

CREATE TABLE IF NOT EXISTS objective_checkins (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  objective_id uuid NOT NULL REFERENCES employee_objectives (id) ON DELETE CASCADE,
  checkin_date date NOT NULL,
  progress_note text NOT NULL,
  updated_by uuid,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_objective_checkins_objective ON objective_checkins (objective_id);
