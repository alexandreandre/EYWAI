-- Référentiel compétences + évaluations (Pack Talent T9)
CREATE TABLE IF NOT EXISTS public.competency_referential (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT,
  required_level INTEGER,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_competency_referential_company
  ON public.competency_referential (company_id);

CREATE TABLE IF NOT EXISTS public.employee_competencies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL,
  employee_id UUID NOT NULL,
  competency_id UUID NOT NULL REFERENCES public.competency_referential (id) ON DELETE CASCADE,
  score INTEGER NOT NULL DEFAULT 0,
  evaluation_date DATE NOT NULL,
  evaluated_by UUID,
  comment TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employee_competencies_company
  ON public.employee_competencies (company_id);

CREATE INDEX IF NOT EXISTS idx_employee_competencies_employee
  ON public.employee_competencies (employee_id, competency_id, evaluation_date DESC);

-- Lien optionnel formation du catalogue ↔ compétence (gaps / formation recommandée)
ALTER TABLE public.training_catalog
  ADD COLUMN IF NOT EXISTS competency_id UUID REFERENCES public.competency_referential (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_training_catalog_competency
  ON public.training_catalog (competency_id)
  WHERE competency_id IS NOT NULL;
