-- Suivi contingent heures sup : paramètres entreprise, ajustements salarié, crédits repos.

CREATE TABLE IF NOT EXISTS public.company_overtime_contingent_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    legal_cor_contingent_hours numeric(8, 2) NOT NULL DEFAULT 220,
    management_contingent_hours numeric(8, 2),
    hours_per_rest_day numeric(6, 2) NOT NULL DEFAULT 7,
    include_structural_hours boolean NOT NULL DEFAULT true,
    pause_deduction_enabled boolean NOT NULL DEFAULT false,
    pause_hs_deduction_per_workday numeric(8, 6) NOT NULL DEFAULT 0.058765,
    workdays_per_year_for_pause integer NOT NULL DEFAULT 260,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_overtime_contingent_settings IS
    'Paramètres de suivi du contingent annuel d''heures supplémentaires par entreprise.';

CREATE TABLE IF NOT EXISTS public.employee_overtime_adjustments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    opening_balance_hours numeric(10, 2) NOT NULL DEFAULT 0,
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT employee_overtime_adjustments_unique UNIQUE (employee_id, year)
);

CREATE INDEX IF NOT EXISTS idx_employee_overtime_adjustments_company_year
    ON public.employee_overtime_adjustments (company_id, year);

CREATE TABLE IF NOT EXISTS public.repos_compensateur_credits (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month integer NOT NULL CHECK (month >= 1 AND month <= 12),
    source text NOT NULL DEFAULT 'cor' CHECK (source IN ('cor', 'rcr', 'manual')),
    heures numeric(10, 2) NOT NULL DEFAULT 0,
    jours numeric(10, 2) NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT repos_compensateur_credits_unique UNIQUE (employee_id, year, month, source)
);

CREATE INDEX IF NOT EXISTS idx_repos_compensateur_credits_company_year
    ON public.repos_compensateur_credits (company_id, year);

ALTER TABLE public.company_overtime_contingent_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_overtime_adjustments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.repos_compensateur_credits ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_overtime_contingent_settings_select ON public.company_overtime_contingent_settings;
CREATE POLICY company_overtime_contingent_settings_select ON public.company_overtime_contingent_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_overtime_contingent_settings_write ON public.company_overtime_contingent_settings;
CREATE POLICY company_overtime_contingent_settings_write ON public.company_overtime_contingent_settings
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

DROP POLICY IF EXISTS employee_overtime_adjustments_select ON public.employee_overtime_adjustments;
CREATE POLICY employee_overtime_adjustments_select ON public.employee_overtime_adjustments
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_overtime_adjustments_write ON public.employee_overtime_adjustments;
CREATE POLICY employee_overtime_adjustments_write ON public.employee_overtime_adjustments
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

DROP POLICY IF EXISTS repos_compensateur_credits_select ON public.repos_compensateur_credits;
CREATE POLICY repos_compensateur_credits_select ON public.repos_compensateur_credits
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS repos_compensateur_credits_write ON public.repos_compensateur_credits;
CREATE POLICY repos_compensateur_credits_write ON public.repos_compensateur_credits
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh', 'service')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh', 'service')
        )
    );
