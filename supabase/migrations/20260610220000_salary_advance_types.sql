-- Distinction avance sur salaire / acompte sur salaire / acompte sur prime.

ALTER TABLE IF EXISTS public.salary_advances
    ADD COLUMN IF NOT EXISTS advance_type text NOT NULL DEFAULT 'avance_salaire'
        CHECK (advance_type IN ('avance_salaire', 'acompte_salaire', 'acompte_prime'));

ALTER TABLE IF EXISTS public.salary_advances
    ADD COLUMN IF NOT EXISTS accounting_account text;

ALTER TABLE IF EXISTS public.salary_advances
    ADD COLUMN IF NOT EXISTS prime_label text;

ALTER TABLE IF EXISTS public.salary_advances
    ADD COLUMN IF NOT EXISTS prime_id text;

ALTER TABLE IF EXISTS public.salary_advances
    ADD COLUMN IF NOT EXISTS prime_expected_amount numeric(12, 2);

ALTER TABLE IF EXISTS public.salary_advances
    ADD COLUMN IF NOT EXISTS prime_final_amount numeric(12, 2);

ALTER TABLE IF EXISTS public.salary_advances
    ADD COLUMN IF NOT EXISTS prime_reconciled_at timestamptz;

ALTER TABLE IF EXISTS public.salary_advances
    ADD COLUMN IF NOT EXISTS prime_reconciled_payslip_id uuid
        REFERENCES public.payslips(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.salary_advances.advance_type IS
    'Nature : avance_salaire (avant travail), acompte_salaire (salaire gagné), acompte_prime (anticipation prime).';

COMMENT ON COLUMN public.salary_advances.accounting_account IS
    'Compte PCG figé à la création (4251/4252/4253 selon la nature).';

CREATE INDEX IF NOT EXISTS idx_salary_advances_acompte_prime
    ON public.salary_advances(company_id, employee_id)
    WHERE advance_type = 'acompte_prime';

-- Comptes comptables par défaut (surchargeables par société via payroll_config).
INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'comptes_avances_acomptes',
    '{
        "avance_salaire": "4252",
        "acompte_salaire": "4251",
        "acompte_prime": "4253",
        "libelles": {
            "avance_salaire": "Avances sur salaires",
            "acompte_salaire": "Acomptes sur salaires",
            "acompte_prime": "Acomptes sur primes"
        }
    }'::jsonb,
    1,
    true,
    'Comptes PCG pour avances et acomptes personnel (425 sous-comptes)',
    NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'comptes_avances_acomptes' AND company_id IS NULL
);
