-- Paramétrage CET groupe (Cartol, Comitech, MBC, Colorplast) — idempotent par nom société.

INSERT INTO public.company_cet_settings (
    company_id,
    cet_enabled,
    allow_deposit_hs,
    allow_deposit_cp,
    max_cp_days_per_year,
    validation_mode,
    cp_unit,
    cp_debit_timing,
    hs_debit_timing,
    updated_at
)
SELECT
    c.id,
    true,
    true,
    CASE
        WHEN upper(c.company_name) LIKE '%MBC%' THEN false
        ELSE true
    END,
    CASE
        WHEN upper(c.company_name) LIKE '%MBC%' THEN NULL
        ELSE 10
    END,
    CASE
        WHEN upper(c.company_name) LIKE '%MBC%' THEN 'rh'
        ELSE 'manager'
    END,
    'ouvres',
    'on_validation',
    'on_payroll',
    now()
FROM public.companies c
WHERE (
    upper(c.company_name) LIKE '%CARTOL%'
    OR upper(c.company_name) LIKE '%COMITECH%'
    OR upper(c.company_name) LIKE '%MBC%'
    OR upper(c.company_name) LIKE '%COLORPLAST%'
)
ON CONFLICT (company_id) DO UPDATE SET
    cet_enabled = EXCLUDED.cet_enabled,
    allow_deposit_hs = EXCLUDED.allow_deposit_hs,
    allow_deposit_cp = EXCLUDED.allow_deposit_cp,
    max_cp_days_per_year = EXCLUDED.max_cp_days_per_year,
    validation_mode = EXCLUDED.validation_mode,
    cp_unit = EXCLUDED.cp_unit,
    cp_debit_timing = EXCLUDED.cp_debit_timing,
    hs_debit_timing = EXCLUDED.hs_debit_timing,
    updated_at = now();
