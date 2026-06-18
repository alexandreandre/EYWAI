-- CET v2 : alimentations paramétrables (HS + CP), plafonds, débit CP configurable.

ALTER TABLE public.company_cet_settings
    ADD COLUMN IF NOT EXISTS allow_deposit_hs boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS allow_deposit_cp boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS max_cp_days_per_year numeric(8, 2),
    ADD COLUMN IF NOT EXISTS max_account_balance_days numeric(8, 2),
    ADD COLUMN IF NOT EXISTS cp_unit text NOT NULL DEFAULT 'ouvrables',
    ADD COLUMN IF NOT EXISTS ouvres_to_ouvrables_ratio numeric(6, 3) NOT NULL DEFAULT 1.2,
    ADD COLUMN IF NOT EXISTS cp_debit_timing text NOT NULL DEFAULT 'on_validation',
    ADD COLUMN IF NOT EXISTS hs_debit_timing text NOT NULL DEFAULT 'on_payroll';

ALTER TABLE public.company_cet_settings
    DROP CONSTRAINT IF EXISTS company_cet_settings_cp_unit_check;
ALTER TABLE public.company_cet_settings
    ADD CONSTRAINT company_cet_settings_cp_unit_check
    CHECK (cp_unit IN ('ouvres', 'ouvrables'));

ALTER TABLE public.company_cet_settings
    DROP CONSTRAINT IF EXISTS company_cet_settings_cp_debit_timing_check;
ALTER TABLE public.company_cet_settings
    ADD CONSTRAINT company_cet_settings_cp_debit_timing_check
    CHECK (cp_debit_timing IN ('on_validation', 'on_payroll'));

ALTER TABLE public.company_cet_settings
    DROP CONSTRAINT IF EXISTS company_cet_settings_hs_debit_timing_check;
ALTER TABLE public.company_cet_settings
    ADD CONSTRAINT company_cet_settings_hs_debit_timing_check
    CHECK (hs_debit_timing IN ('on_validation', 'on_payroll'));

ALTER TABLE public.employee_cet_movements
    ADD COLUMN IF NOT EXISTS days numeric(10, 2),
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.employee_cet_movements
    ALTER COLUMN hours DROP NOT NULL;

ALTER TABLE public.employee_cet_movements
    DROP CONSTRAINT IF EXISTS employee_cet_movements_movement_type_check;
ALTER TABLE public.employee_cet_movements
    ADD CONSTRAINT employee_cet_movements_movement_type_check
    CHECK (movement_type IN ('deposit_hs', 'deposit_cp', 'withdraw_rest', 'adjustment'));

CREATE INDEX IF NOT EXISTS idx_employee_cet_movements_employee_year_type
    ON public.employee_cet_movements (employee_id, year, movement_type, status);
