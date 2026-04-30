CREATE TABLE IF NOT EXISTS salary_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID NOT NULL REFERENCES employees(id)
    ON DELETE CASCADE,
  company_id UUID NOT NULL,
  ancien_salaire JSONB NOT NULL,
  nouveau_salaire JSONB NOT NULL,
  motif TEXT,
  effective_date DATE NOT NULL,
  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_salary_history_employee
  ON salary_history(employee_id);
CREATE INDEX IF NOT EXISTS idx_salary_history_company
  ON salary_history(company_id);
