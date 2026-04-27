-- Overrides critères bilan 6 ans (hors EYWAI) — Pack Talent T8
CREATE TABLE IF NOT EXISTS public.legal_obligation_overrides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
  employee_id UUID NOT NULL REFERENCES public.employees (id) ON DELETE CASCADE,
  criteria_training_completed BOOLEAN NOT NULL DEFAULT false,
  criteria_certification_obtained BOOLEAN NOT NULL DEFAULT false,
  criteria_career_evolution BOOLEAN NOT NULL DEFAULT false,
  notes TEXT,
  updated_by UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT legal_obligation_overrides_company_employee_unique UNIQUE (company_id, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_legal_obligation_overrides_company
  ON public.legal_obligation_overrides (company_id);

-- RLS : accès aux lignes dont l'entreprise est liée à l'utilisateur (user_company_accesses)
ALTER TABLE public.legal_obligation_overrides ENABLE ROW LEVEL SECURITY;

CREATE POLICY legal_obligation_overrides_select
  ON public.legal_obligation_overrides
  FOR SELECT
  TO authenticated
  USING (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

CREATE POLICY legal_obligation_overrides_insert
  ON public.legal_obligation_overrides
  FOR INSERT
  TO authenticated
  WITH CHECK (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

CREATE POLICY legal_obligation_overrides_update
  ON public.legal_obligation_overrides
  FOR UPDATE
  TO authenticated
  USING (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  )
  WITH CHECK (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

CREATE POLICY legal_obligation_overrides_delete
  ON public.legal_obligation_overrides
  FOR DELETE
  TO authenticated
  USING (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );
