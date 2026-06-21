-- Primes équipes : panier, majoration nuit, pause payée (paramétrable par entreprise).

ALTER TABLE public.monthly_inputs
    ADD COLUMN IF NOT EXISTS bonus_type_id uuid REFERENCES public.company_bonus_types(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS catalog_prime_id text,
    ADD COLUMN IF NOT EXISTS payroll_quantity numeric(10, 2);

ALTER TABLE public.shift_types
    ADD COLUMN IF NOT EXISTS allows_overnight boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS meal_allowance_eligible boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS paid_break_minutes integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS night_windows jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.shift_types.night_windows IS
    'Plages de majoration nuit ex. [{"start":"22:00","end":"06:00","rate":0.5}]';

ALTER TABLE public.company_planning_settings
    ADD COLUMN IF NOT EXISTS payroll_shift_metrics_enabled boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS auto_generate_payroll_variables_before_payslip boolean NOT NULL DEFAULT false;
