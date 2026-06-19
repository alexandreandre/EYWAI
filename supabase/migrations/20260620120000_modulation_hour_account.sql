-- Compte d'heures modulation : paramètres entreprise, grand livre mouvements, cache compteur.

ALTER TABLE public.company_modulation_settings
    ADD COLUMN IF NOT EXISTS hour_account_enabled boolean NOT NULL DEFAULT false;

ALTER TABLE public.company_modulation_settings
    ADD COLUMN IF NOT EXISTS hs_franchise_hours_per_period numeric(6, 2);

ALTER TABLE public.company_modulation_settings
    ADD COLUMN IF NOT EXISTS hs_franchise_period text NOT NULL DEFAULT 'month';

ALTER TABLE public.company_modulation_settings
    DROP CONSTRAINT IF EXISTS company_modulation_settings_hs_franchise_period_check;

ALTER TABLE public.company_modulation_settings
    ADD CONSTRAINT company_modulation_settings_hs_franchise_period_check
    CHECK (hs_franchise_period IN ('month', 'pay_period'));

ALTER TABLE public.company_modulation_settings
    ADD COLUMN IF NOT EXISTS max_account_balance_hours numeric(8, 2);

ALTER TABLE public.company_modulation_settings
    ADD COLUMN IF NOT EXISTS account_credit_source text NOT NULL DEFAULT 'overtime_only';

ALTER TABLE public.company_modulation_settings
    DROP CONSTRAINT IF EXISTS company_modulation_settings_account_credit_source_check;

ALTER TABLE public.company_modulation_settings
    ADD CONSTRAINT company_modulation_settings_account_credit_source_check
    CHECK (account_credit_source IN ('overtime_only', 'surplus_over_modulated'));

ALTER TABLE public.company_modulation_settings
    ADD COLUMN IF NOT EXISTS recovery_absence_enabled boolean NOT NULL DEFAULT true;

ALTER TABLE public.company_modulation_settings
    ADD COLUMN IF NOT EXISTS recovery_debit_timing text NOT NULL DEFAULT 'on_validation';

ALTER TABLE public.company_modulation_settings
    DROP CONSTRAINT IF EXISTS company_modulation_settings_recovery_debit_timing_check;

ALTER TABLE public.company_modulation_settings
    ADD CONSTRAINT company_modulation_settings_recovery_debit_timing_check
    CHECK (recovery_debit_timing IN ('on_validation', 'on_payroll'));

COMMENT ON COLUMN public.company_modulation_settings.hour_account_enabled IS
    'Active le compte d''heures modulation (franchise HS, crédit, récupération).';

CREATE TABLE IF NOT EXISTS public.employee_modulation_movements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month integer CHECK (month IS NULL OR (month >= 1 AND month <= 12)),
    movement_type text NOT NULL
        CHECK (movement_type IN (
            'credit_hs',
            'debit_recovery',
            'debit_payout',
            'adjustment',
            'opening_balance'
        )),
    hours numeric(10, 2) NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'validated', 'applied_payroll', 'cancelled')),
    source text NOT NULL DEFAULT 'payroll_auto'
        CHECK (source IN ('payroll_auto', 'absence', 'manual_rh')),
    reference_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    note text,
    requested_by uuid,
    validated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employee_modulation_movements_employee_period
    ON public.employee_modulation_movements (employee_id, year, month);

CREATE INDEX IF NOT EXISTS idx_employee_modulation_movements_company_status
    ON public.employee_modulation_movements (company_id, status);

COMMENT ON TABLE public.employee_modulation_movements IS
    'Grand livre compte d''heures modulation par salarié.';

ALTER TABLE public.employee_modulation_counters
    ADD COLUMN IF NOT EXISTS account_balance_hours numeric(10, 2) NOT NULL DEFAULT 0;

ALTER TABLE public.employee_modulation_counters
    ADD COLUMN IF NOT EXISTS period_credited_hours numeric(10, 2) NOT NULL DEFAULT 0;

ALTER TABLE public.employee_modulation_counters
    ADD COLUMN IF NOT EXISTS period_paid_hours numeric(10, 2) NOT NULL DEFAULT 0;

ALTER TABLE public.employee_modulation_movements ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS employee_modulation_movements_select ON public.employee_modulation_movements;
CREATE POLICY employee_modulation_movements_select ON public.employee_modulation_movements
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

DROP POLICY IF EXISTS employee_modulation_movements_write ON public.employee_modulation_movements;
CREATE POLICY employee_modulation_movements_write ON public.employee_modulation_movements
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
