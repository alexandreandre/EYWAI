-- Temps de travail généralisé : modulation, modèles semaine, variables paie, RTT forfait cadres.

-- Employés : date d'ancienneté de référence (distincte de hire_date si reprise)
ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS seniority_reference_date date;

COMMENT ON COLUMN public.employees.seniority_reference_date IS
    'Date de départ pour le calcul d''ancienneté (accord entreprise / reprise).';

-- RTT forfait : réservé aux forfait-jours
ALTER TABLE public.company_leave_settings
    ADD COLUMN IF NOT EXISTS rtt_forfait_cadres_only boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN public.company_leave_settings.rtt_forfait_cadres_only IS
    'Si mode forfait actif : RTT uniquement pour salariés au forfait jour.';

-- CP ancienneté : preset LEWIS
ALTER TABLE public.company_cp_seniority_settings
    DROP CONSTRAINT IF EXISTS company_cp_seniority_settings_preset_check;

ALTER TABLE public.company_cp_seniority_settings
    ADD CONSTRAINT company_cp_seniority_settings_preset_check
    CHECK (preset IN ('plasturgie_idcc_0292', 'lewis_agreement', 'custom'));

-- Modulation du temps de travail
CREATE TABLE IF NOT EXISTS public.company_modulation_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    enabled boolean NOT NULL DEFAULT false,
    reference_period_months integer NOT NULL DEFAULT 12
        CHECK (reference_period_months >= 1 AND reference_period_months <= 12),
    average_weekly_hours numeric(5, 2) NOT NULL DEFAULT 35
        CHECK (average_weekly_hours > 0 AND average_weekly_hours <= 48),
    weekly_high_hours numeric(5, 2) NOT NULL DEFAULT 37
        CHECK (weekly_high_hours > 0 AND weekly_high_hours <= 48),
    weekly_low_hours numeric(5, 2) NOT NULL DEFAULT 32
        CHECK (weekly_low_hours > 0 AND weekly_low_hours <= 48),
    high_weeks_per_cycle integer NOT NULL DEFAULT 1
        CHECK (high_weeks_per_cycle >= 0 AND high_weeks_per_cycle <= 52),
    low_weeks_per_cycle integer NOT NULL DEFAULT 1
        CHECK (low_weeks_per_cycle >= 0 AND low_weeks_per_cycle <= 52),
    cycle_start_week_iso date,
    pay_smoothed boolean NOT NULL DEFAULT true,
    weekly_cap_hours numeric(5, 2) NOT NULL DEFAULT 44
        CHECK (weekly_cap_hours > 0 AND weekly_cap_hours <= 48),
    theoretical_annual_hours numeric(7, 2),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_modulation_settings IS
    'Paramètres modulation / annualisation du temps de travail par entreprise.';

-- Modèles de semaine entreprise (remplace localStorage)
CREATE TABLE IF NOT EXISTS public.company_week_schedule_templates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    weekly_hours numeric(5, 2) NOT NULL DEFAULT 35,
    day_configs jsonb NOT NULL DEFAULT '[]'::jsonb,
    modulation_tier text NOT NULL DEFAULT 'neutral'
        CHECK (modulation_tier IN ('high', 'low', 'neutral')),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, name)
);

CREATE INDEX IF NOT EXISTS idx_week_schedule_templates_company
    ON public.company_week_schedule_templates (company_id);

-- Compteurs modulation par salarié
CREATE TABLE IF NOT EXISTS public.employee_modulation_counters (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    theoretical_hours numeric(10, 2) NOT NULL DEFAULT 0,
    actual_hours numeric(10, 2) NOT NULL DEFAULT 0,
    balance_hours numeric(10, 2) NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (employee_id, year)
);

CREATE INDEX IF NOT EXISTS idx_employee_modulation_counters_company_year
    ON public.employee_modulation_counters (company_id, year);

-- Règles variables de paie récurrentes
CREATE TABLE IF NOT EXISTS public.company_payroll_variable_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    code text NOT NULL,
    label text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    rule_type text NOT NULL
        CHECK (rule_type IN (
            'fixed_monthly',
            'per_astreinte_week',
            'per_shift_type',
            'per_modulation_payout',
            'per_night_hour'
        )),
    bonus_type_id uuid REFERENCES public.company_bonus_types(id) ON DELETE SET NULL,
    amount numeric(12, 2),
    rate numeric(8, 4),
    conditions jsonb NOT NULL DEFAULT '{}'::jsonb,
    generation_mode text NOT NULL DEFAULT 'auto'
        CHECK (generation_mode IN ('auto', 'suggest')),
    sort_order integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code)
);

CREATE INDEX IF NOT EXISTS idx_payroll_variable_rules_company
    ON public.company_payroll_variable_rules (company_id);

-- Shift types : lien prime équipe
ALTER TABLE public.shift_types
    ADD COLUMN IF NOT EXISTS premium_rule_code text;

-- RLS
ALTER TABLE public.company_modulation_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_week_schedule_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_modulation_counters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_payroll_variable_rules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_modulation_settings_select ON public.company_modulation_settings;
CREATE POLICY company_modulation_settings_select ON public.company_modulation_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_modulation_settings_write ON public.company_modulation_settings;
CREATE POLICY company_modulation_settings_write ON public.company_modulation_settings
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

DROP POLICY IF EXISTS company_week_schedule_templates_select ON public.company_week_schedule_templates;
CREATE POLICY company_week_schedule_templates_select ON public.company_week_schedule_templates
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_week_schedule_templates_write ON public.company_week_schedule_templates;
CREATE POLICY company_week_schedule_templates_write ON public.company_week_schedule_templates
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

DROP POLICY IF EXISTS employee_modulation_counters_select ON public.employee_modulation_counters;
CREATE POLICY employee_modulation_counters_select ON public.employee_modulation_counters
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_modulation_counters_write ON public.employee_modulation_counters;
CREATE POLICY employee_modulation_counters_write ON public.employee_modulation_counters
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

DROP POLICY IF EXISTS company_payroll_variable_rules_select ON public.company_payroll_variable_rules;
CREATE POLICY company_payroll_variable_rules_select ON public.company_payroll_variable_rules
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_payroll_variable_rules_write ON public.company_payroll_variable_rules;
CREATE POLICY company_payroll_variable_rules_write ON public.company_payroll_variable_rules
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
