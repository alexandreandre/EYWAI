-- Paramètres congés / RTT par entreprise et ajustements soldes par salarié.

CREATE TABLE IF NOT EXISTS public.company_leave_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    cp_acquisition_days_per_month numeric(6, 3) NOT NULL DEFAULT 2.5,
    cp_counting_unit text NOT NULL DEFAULT 'ouvrable'
        CHECK (cp_counting_unit IN ('ouvrable', 'ouvre')),
    cp_reference_period_start_month integer NOT NULL DEFAULT 6
        CHECK (cp_reference_period_start_month >= 1 AND cp_reference_period_start_month <= 12),
    cp_carryover_enabled boolean NOT NULL DEFAULT false,
    cp_carryover_max_days numeric(6, 2),
    rtt_annual_days numeric(6, 2),
    rtt_use_calendar_formula boolean NOT NULL DEFAULT false,
    rtt_period_start_month integer NOT NULL DEFAULT 1
        CHECK (rtt_period_start_month >= 1 AND rtt_period_start_month <= 12),
    rtt_period_end_month integer NOT NULL DEFAULT 12
        CHECK (rtt_period_end_month >= 1 AND rtt_period_end_month <= 12),
    rtt_carryover_enabled boolean NOT NULL DEFAULT false,
    rtt_year_end_reminder_enabled boolean NOT NULL DEFAULT false,
    rtt_year_end_reminder_days_before integer NOT NULL DEFAULT 15
        CHECK (rtt_year_end_reminder_days_before >= 1 AND rtt_year_end_reminder_days_before <= 60),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_leave_settings IS
    'Paramètres RH des congés payés et RTT par entreprise (opt-in, defaults = comportement légal standard).';

CREATE TABLE IF NOT EXISTS public.employee_leave_adjustments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    cp_n1_opening_balance numeric(8, 2) NOT NULL DEFAULT 0,
    cp_n_opening_balance numeric(8, 2) NOT NULL DEFAULT 0,
    rtt_opening_balance numeric(8, 2) NOT NULL DEFAULT 0,
    rtt_forfeited_at timestamptz,
    rtt_forfeited_days numeric(8, 2) NOT NULL DEFAULT 0,
    rtt_forfeited_by_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT employee_leave_adjustments_unique UNIQUE (employee_id, year)
);

CREATE INDEX IF NOT EXISTS idx_employee_leave_adjustments_company_year
    ON public.employee_leave_adjustments (company_id, year);

ALTER TABLE public.company_leave_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_leave_adjustments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_leave_settings_select ON public.company_leave_settings;
CREATE POLICY company_leave_settings_select ON public.company_leave_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_leave_settings_write ON public.company_leave_settings;
CREATE POLICY company_leave_settings_write ON public.company_leave_settings
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

DROP POLICY IF EXISTS employee_leave_adjustments_select ON public.employee_leave_adjustments;
CREATE POLICY employee_leave_adjustments_select ON public.employee_leave_adjustments
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_leave_adjustments_write ON public.employee_leave_adjustments;
CREATE POLICY employee_leave_adjustments_write ON public.employee_leave_adjustments
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
