-- Cotisations salariales / patronales agrégées depuis les blocs DSN (pilotage dashboard).

ALTER TABLE public.company_dsn_payroll_totals
    ADD COLUMN IF NOT EXISTS employee_charges numeric(14, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS employer_charges numeric(14, 2) NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.company_dsn_payroll_totals.employee_charges IS
    'Somme des montants salariaux des cotisations DSN pour la période.';

COMMENT ON COLUMN public.company_dsn_payroll_totals.employer_charges IS
    'Somme des montants patronaux des cotisations DSN pour la période (réductions incluses).';
