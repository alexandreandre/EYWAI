-- Parcours d'onboarding (checklist + tâches) par salarié
CREATE TABLE IF NOT EXISTS onboarding_checklists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID NOT NULL REFERENCES employees(id)
    ON DELETE CASCADE,
  company_id UUID NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS onboarding_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  checklist_id UUID NOT NULL
    REFERENCES onboarding_checklists(id) ON DELETE CASCADE,
  company_id UUID NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL,
  is_completed BOOLEAN DEFAULT FALSE,
  completed_at TIMESTAMPTZ,
  completed_by UUID,
  due_days INT,
  position INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_employee
  ON onboarding_checklists(employee_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_company
  ON onboarding_checklists(company_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_tasks_checklist
  ON onboarding_tasks(checklist_id);
