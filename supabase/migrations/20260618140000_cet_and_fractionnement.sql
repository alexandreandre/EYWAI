-- CET (compte épargne-temps) et fractionnement CP MBC.

CREATE TABLE IF NOT EXISTS public.company_cet_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    cet_enabled boolean NOT NULL DEFAULT false,
    agreement_reference text,
    hours_per_rest_day numeric(6, 2) NOT NULL DEFAULT 7,
    request_deadline_day_of_month integer CHECK (
        request_deadline_day_of_month IS NULL
        OR (request_deadline_day_of_month >= 1 AND request_deadline_day_of_month <= 28)
    ),
    validation_mode text NOT NULL DEFAULT 'rh'
        CHECK (validation_mode IN ('auto', 'rh')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_cet_settings IS
    'Paramètres accord CET par entreprise.';

CREATE TABLE IF NOT EXISTS public.employee_cet_movements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month integer NOT NULL CHECK (month >= 1 AND month <= 12),
    movement_type text NOT NULL
        CHECK (movement_type IN ('deposit_hs', 'withdraw_rest', 'adjustment')),
    hours numeric(10, 2) NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'validated', 'rejected', 'applied_payroll')),
    note text,
    requested_by uuid,
    validated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employee_cet_movements_employee_period
    ON public.employee_cet_movements (employee_id, year, month);

CREATE INDEX IF NOT EXISTS idx_employee_cet_movements_company_status
    ON public.employee_cet_movements (company_id, status);

CREATE TABLE IF NOT EXISTS public.company_cp_fractionnement_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    fractionnement_enabled boolean NOT NULL DEFAULT false,
    cp_unit text NOT NULL DEFAULT 'ouvres'
        CHECK (cp_unit IN ('ouvres', 'ouvrables')),
    ouvres_to_ouvrables_ratio numeric(6, 3) NOT NULL DEFAULT 1.2,
    fifth_week_deduction_ouvres numeric(6, 2) NOT NULL DEFAULT 5,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_cp_fractionnement_settings IS
    'Paramètres calcul fractionnement CP (formule MBC).';

CREATE TABLE IF NOT EXISTS public.employee_cp_fractionnement_grants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    grant_year integer NOT NULL CHECK (grant_year >= 2000 AND grant_year <= 2100),
    payroll_year integer NOT NULL CHECK (payroll_year >= 2000 AND payroll_year <= 2100),
    payroll_month integer NOT NULL DEFAULT 11 CHECK (payroll_month >= 1 AND payroll_month <= 12),
    days_granted integer NOT NULL DEFAULT 0 CHECK (days_granted >= 0 AND days_granted <= 2),
    calculation_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT employee_cp_fractionnement_grants_unique UNIQUE (employee_id, grant_year)
);

CREATE TABLE IF NOT EXISTS public.employee_cp_fractionnement_inputs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    grant_year integer NOT NULL CHECK (grant_year >= 2000 AND grant_year <= 2100),
    cp_reported_june_ouvres numeric(10, 2) NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT employee_cp_fractionnement_inputs_unique UNIQUE (employee_id, grant_year)
);

CREATE INDEX IF NOT EXISTS idx_employee_cp_fractionnement_inputs_company_year
    ON public.employee_cp_fractionnement_inputs (company_id, grant_year);

ALTER TABLE public.company_cet_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_cet_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_cp_fractionnement_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_cp_fractionnement_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_cp_fractionnement_inputs ENABLE ROW LEVEL SECURITY;

-- company_cet_settings
DROP POLICY IF EXISTS company_cet_settings_select ON public.company_cet_settings;
CREATE POLICY company_cet_settings_select ON public.company_cet_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_cet_settings_write ON public.company_cet_settings;
CREATE POLICY company_cet_settings_write ON public.company_cet_settings
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

-- employee_cet_movements
DROP POLICY IF EXISTS employee_cet_movements_select ON public.employee_cet_movements;
CREATE POLICY employee_cet_movements_select ON public.employee_cet_movements
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
        OR employee_id IN (
            SELECT e.id FROM public.employees e
            WHERE e.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_cet_movements_write ON public.employee_cet_movements;
CREATE POLICY employee_cet_movements_write ON public.employee_cet_movements
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
        OR (
            employee_id IN (
                SELECT e.id FROM public.employees e
                WHERE e.user_id = auth.uid()
            )
            AND status = 'pending'
            AND movement_type IN ('deposit_hs', 'withdraw_rest')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
        OR (
            employee_id IN (
                SELECT e.id FROM public.employees e
                WHERE e.user_id = auth.uid()
            )
            AND status = 'pending'
        )
    );

-- company_cp_fractionnement_settings
DROP POLICY IF EXISTS company_cp_fractionnement_settings_select ON public.company_cp_fractionnement_settings;
CREATE POLICY company_cp_fractionnement_settings_select ON public.company_cp_fractionnement_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_cp_fractionnement_settings_write ON public.company_cp_fractionnement_settings;
CREATE POLICY company_cp_fractionnement_settings_write ON public.company_cp_fractionnement_settings
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

-- employee_cp_fractionnement_grants
DROP POLICY IF EXISTS employee_cp_fractionnement_grants_select ON public.employee_cp_fractionnement_grants;
CREATE POLICY employee_cp_fractionnement_grants_select ON public.employee_cp_fractionnement_grants
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_cp_fractionnement_grants_write ON public.employee_cp_fractionnement_grants;
CREATE POLICY employee_cp_fractionnement_grants_write ON public.employee_cp_fractionnement_grants
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

-- employee_cp_fractionnement_inputs
DROP POLICY IF EXISTS employee_cp_fractionnement_inputs_select ON public.employee_cp_fractionnement_inputs;
CREATE POLICY employee_cp_fractionnement_inputs_select ON public.employee_cp_fractionnement_inputs
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_cp_fractionnement_inputs_write ON public.employee_cp_fractionnement_inputs;
CREATE POLICY employee_cp_fractionnement_inputs_write ON public.employee_cp_fractionnement_inputs
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
