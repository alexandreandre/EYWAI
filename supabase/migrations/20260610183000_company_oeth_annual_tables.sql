-- BOETH externes, déductions, ECAP et revues annuelles OETH.

CREATE TABLE IF NOT EXISTS public.company_oeth_boeth_externes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employment_year integer NOT NULL CHECK (employment_year >= 2020),
    external_type text NOT NULL CHECK (external_type IN ('01', '02', '03', '04')),
    annual_average_count numeric(10, 4) NOT NULL DEFAULT 0 CHECK (annual_average_count >= 0),
    contract_reference text,
    amount_ht numeric(12, 2) NOT NULL DEFAULT 0 CHECK (amount_ht >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, employment_year, external_type, contract_reference)
);

CREATE TABLE IF NOT EXISTS public.company_oeth_deductions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employment_year integer NOT NULL CHECK (employment_year >= 2020),
    deduction_type text NOT NULL CHECK (deduction_type IN ('060', '061', '062', '063', '064')),
    amount_eur numeric(12, 2) NOT NULL DEFAULT 0 CHECK (amount_eur >= 0),
    provider_name text,
    reference text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.company_oeth_ecap_positions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employment_year integer NOT NULL CHECK (employment_year >= 2020),
    job_code_pcs_ese text NOT NULL,
    annual_average_count numeric(10, 4) NOT NULL DEFAULT 0 CHECK (annual_average_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, employment_year, job_code_pcs_ese)
);

CREATE TABLE IF NOT EXISTS public.company_oeth_annual_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employment_year integer NOT NULL CHECK (employment_year >= 2020),
    ema_assujettissement numeric(10, 4),
    ema_boeth_interne numeric(10, 4),
    ema_boeth_externe numeric(10, 4),
    ema_ecap numeric(10, 4),
    urssaf_ema_assujettissement numeric(10, 4),
    urssaf_ema_boeth numeric(10, 4),
    urssaf_ema_ecap numeric(10, 4),
    urssaf_notified_at date,
    boeth_manquants integer,
    contribution_brute numeric(12, 2),
    contribution_nette numeric(12, 2),
    contribution_due numeric(12, 2),
    deductions_detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    neutralisation_active boolean NOT NULL DEFAULT false,
    surcontribution_applicable boolean NOT NULL DEFAULT false,
    accord_agree_active boolean NOT NULL DEFAULT false,
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'validated', 'declared')),
    declared_in_dsn_period text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, employment_year)
);

CREATE INDEX IF NOT EXISTS company_oeth_boeth_externes_year_idx
    ON public.company_oeth_boeth_externes (company_id, employment_year);
CREATE INDEX IF NOT EXISTS company_oeth_deductions_year_idx
    ON public.company_oeth_deductions (company_id, employment_year);
CREATE INDEX IF NOT EXISTS company_oeth_ecap_positions_year_idx
    ON public.company_oeth_ecap_positions (company_id, employment_year);

ALTER TABLE public.company_oeth_boeth_externes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_oeth_deductions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_oeth_ecap_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_oeth_annual_reviews ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'company_oeth_boeth_externes',
        'company_oeth_deductions',
        'company_oeth_ecap_positions',
        'company_oeth_annual_reviews'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I_select ON public.%I', tbl, tbl);
        EXECUTE format(
            'CREATE POLICY %I_select ON public.%I FOR SELECT TO authenticated USING (
                company_id IN (
                    SELECT uca.company_id FROM public.user_company_accesses uca
                    WHERE uca.user_id = auth.uid()
                )
            )', tbl, tbl
        );
        EXECUTE format('DROP POLICY IF EXISTS %I_write ON public.%I', tbl, tbl);
        EXECUTE format(
            'CREATE POLICY %I_write ON public.%I FOR ALL TO authenticated
            USING (
                company_id IN (
                    SELECT uca.company_id FROM public.user_company_accesses uca
                    WHERE uca.user_id = auth.uid()
                    AND uca.role IN (''admin'', ''rh'', ''collaborateur_rh'')
                )
            )
            WITH CHECK (
                company_id IN (
                    SELECT uca.company_id FROM public.user_company_accesses uca
                    WHERE uca.user_id = auth.uid()
                    AND uca.role IN (''admin'', ''rh'', ''collaborateur_rh'')
                )
            )', tbl, tbl
        );
    END LOOP;
END $$;
