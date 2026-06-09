-- Suivi cumulatif des exonérations JEI par établissement (plafond annuel 5 × PASS).

CREATE TABLE IF NOT EXISTS public.company_jei_exonerations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month integer NOT NULL CHECK (month >= 1 AND month <= 12),
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    montant_exonere numeric(12, 2) NOT NULL DEFAULT 0
        CHECK (montant_exonere >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, year, month, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_company_jei_exonerations_company_year
    ON public.company_jei_exonerations (company_id, year);

COMMENT ON TABLE public.company_jei_exonerations IS
    'Montants d''exonération JEI appliqués par salarié et par mois (suivi plafond 5 PASS).';

ALTER TABLE public.company_jei_exonerations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_jei_exonerations_select ON public.company_jei_exonerations;
CREATE POLICY company_jei_exonerations_select ON public.company_jei_exonerations
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

-- Écriture réservée au service backend (service role) ; pas de policy INSERT/UPDATE côté client.
