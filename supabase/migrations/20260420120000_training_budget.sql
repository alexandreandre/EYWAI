-- Budget formation par entreprise et année (Pack Talent T7)
CREATE TABLE IF NOT EXISTS public.training_budget (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL,
  year INTEGER NOT NULL,
  global_envelope NUMERIC(14, 2) NOT NULL,
  alert_threshold_1 NUMERIC(5, 2) NOT NULL DEFAULT 70,
  alert_threshold_2 NUMERIC(5, 2) NOT NULL DEFAULT 90,
  service_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT training_budget_company_year_unique UNIQUE (company_id, year)
);

CREATE INDEX IF NOT EXISTS idx_training_budget_company_year
  ON public.training_budget (company_id, year DESC);
