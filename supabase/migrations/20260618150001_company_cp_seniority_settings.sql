-- CP ancienneté (congés payés supplémentaires) paramétrables par entreprise.

CREATE TABLE IF NOT EXISTS public.company_cp_seniority_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    enabled boolean NOT NULL DEFAULT false,
    preset text NOT NULL DEFAULT 'plasturgie_idcc_0292'
        CHECK (preset IN ('plasturgie_idcc_0292', 'custom')),
    seniority_reference text NOT NULL DEFAULT 'cp_period_end'
        CHECK (seniority_reference IN ('cp_period_end')),
    seniority_basis text NOT NULL DEFAULT 'company_only'
        CHECK (seniority_basis IN ('company_only', 'include_prior_service')),
    counting_unit text NOT NULL DEFAULT 'ouvrable'
        CHECK (counting_unit IN ('ouvrable', 'ouvre')),
    rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    forfait_annual_days_default numeric(6, 2) NOT NULL DEFAULT 216,
    forfait_reduction_enabled boolean NOT NULL DEFAULT true,
    company_agreement_overrides boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_cp_seniority_settings IS
    'Paramètres congés payés supplémentaires d''ancienneté par entreprise.';

CREATE TABLE IF NOT EXISTS public.employee_cp_seniority_grants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    grant_year integer NOT NULL CHECK (grant_year >= 2000 AND grant_year <= 2100),
    days_granted numeric(6, 2) NOT NULL DEFAULT 0 CHECK (days_granted >= 0),
    category_resolved text,
    seniority_years_at_ref numeric(8, 2),
    forfait_days_reduction numeric(6, 2) NOT NULL DEFAULT 0 CHECK (forfait_days_reduction >= 0),
    calculation_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT employee_cp_seniority_grants_unique UNIQUE (employee_id, grant_year)
);

CREATE INDEX IF NOT EXISTS idx_employee_cp_seniority_grants_company_year
    ON public.employee_cp_seniority_grants (company_id, grant_year);

ALTER TABLE public.company_cp_seniority_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_cp_seniority_grants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_cp_seniority_settings_select ON public.company_cp_seniority_settings;
CREATE POLICY company_cp_seniority_settings_select ON public.company_cp_seniority_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_cp_seniority_settings_write ON public.company_cp_seniority_settings;
CREATE POLICY company_cp_seniority_settings_write ON public.company_cp_seniority_settings
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

DROP POLICY IF EXISTS employee_cp_seniority_grants_select ON public.employee_cp_seniority_grants;
CREATE POLICY employee_cp_seniority_grants_select ON public.employee_cp_seniority_grants
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_cp_seniority_grants_write ON public.employee_cp_seniority_grants;
CREATE POLICY employee_cp_seniority_grants_write ON public.employee_cp_seniority_grants
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );
