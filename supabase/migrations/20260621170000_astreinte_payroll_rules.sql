-- Astreinte paie : jours spéciaux entreprise, codes export, nouveaux rule_types.

CREATE TABLE IF NOT EXISTS public.company_payroll_special_days (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    day_date date NOT NULL,
    kind text NOT NULL CHECK (kind IN ('bridge', 'christmas_week')),
    label text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, day_date, kind)
);

CREATE INDEX IF NOT EXISTS idx_company_payroll_special_days_company_date
    ON public.company_payroll_special_days (company_id, day_date);

ALTER TABLE public.company_bonus_types
    ADD COLUMN IF NOT EXISTS export_code text;

ALTER TABLE public.monthly_inputs
    ADD COLUMN IF NOT EXISTS export_code text;

ALTER TABLE public.company_payroll_variable_rules
    DROP CONSTRAINT IF EXISTS company_payroll_variable_rules_rule_type_check;

ALTER TABLE public.company_payroll_variable_rules
    ADD CONSTRAINT company_payroll_variable_rules_rule_type_check
    CHECK (rule_type IN (
        'fixed_monthly',
        'per_astreinte_week',
        'per_shift_type',
        'per_modulation_payout',
        'per_night_hour',
        'per_astreinte_weekend_km',
        'per_astreinte_week_tiered',
        'per_astreinte_weekend_majoration'
    ));

ALTER TABLE public.company_payroll_special_days ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_payroll_special_days_select ON public.company_payroll_special_days;
CREATE POLICY company_payroll_special_days_select ON public.company_payroll_special_days
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_payroll_special_days_write ON public.company_payroll_special_days;
CREATE POLICY company_payroll_special_days_write ON public.company_payroll_special_days
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
