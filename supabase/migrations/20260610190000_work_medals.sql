-- Médailles du travail : paramétrage entreprise, dossiers par palier, ancienneté antérieure.

ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS prior_service_months integer NOT NULL DEFAULT 0
        CHECK (prior_service_months >= 0);

COMMENT ON COLUMN public.employees.prior_service_months IS
    'Mois de carrière antérieurs à l''embauche (pour calcul carrière totale médaille du travail).';

CREATE TABLE IF NOT EXISTS public.company_work_medal_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    enabled boolean NOT NULL DEFAULT false,
    seniority_basis text NOT NULL DEFAULT 'total_career'
        CHECK (seniority_basis IN ('total_career', 'company_only')),
    reminder_months_before integer NOT NULL DEFAULT 6
        CHECK (reminder_months_before >= 0 AND reminder_months_before <= 24),
    tiers jsonb NOT NULL DEFAULT '[]'::jsonb,
    default_is_taxable boolean NOT NULL DEFAULT true,
    default_is_socially_taxed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_work_medal_settings IS
    'Paramétrage des primes médaille du travail par entreprise (paliers, ancienneté, rappels).';

CREATE TABLE IF NOT EXISTS public.employee_work_medal_cases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    medal_level text NOT NULL
        CHECK (medal_level IN ('argent', 'vermeil', 'or', 'grand_or')),
    milestone_years integer NOT NULL
        CHECK (milestone_years IN (20, 30, 35, 40)),
    eligible_date date NOT NULL,
    status text NOT NULL DEFAULT 'upcoming'
        CHECK (status IN (
            'upcoming', 'awaiting_employee', 'awaiting_rh',
            'approved', 'paid', 'dismissed'
        )),
    amount_computed numeric(12, 2),
    payroll_year integer,
    payroll_month integer CHECK (payroll_month IS NULL OR (payroll_month >= 1 AND payroll_month <= 12)),
    monthly_input_id uuid REFERENCES public.monthly_inputs(id) ON DELETE SET NULL,
    employee_confirmed_at timestamptz,
    rh_validated_at timestamptz,
    rh_validated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    dismissed_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (employee_id, medal_level)
);

COMMENT ON TABLE public.employee_work_medal_cases IS
    'Dossier prime médaille du travail par salarié et par échelon (20/30/35/40 ans).';

CREATE INDEX IF NOT EXISTS idx_work_medal_cases_company_status
    ON public.employee_work_medal_cases(company_id, status);

CREATE INDEX IF NOT EXISTS idx_work_medal_cases_employee
    ON public.employee_work_medal_cases(employee_id);

ALTER TABLE public.company_work_medal_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_work_medal_cases ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_work_medal_settings_select ON public.company_work_medal_settings;
CREATE POLICY company_work_medal_settings_select ON public.company_work_medal_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_work_medal_settings_write ON public.company_work_medal_settings;
CREATE POLICY company_work_medal_settings_write ON public.company_work_medal_settings
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

DROP POLICY IF EXISTS employee_work_medal_cases_select ON public.employee_work_medal_cases;
CREATE POLICY employee_work_medal_cases_select ON public.employee_work_medal_cases
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_work_medal_cases_write ON public.employee_work_medal_cases;
CREATE POLICY employee_work_medal_cases_write ON public.employee_work_medal_cases
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
