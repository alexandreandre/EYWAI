-- Totaux paie mensuels agrégés par entreprise depuis imports DSN (dashboard onboarding).

CREATE TABLE IF NOT EXISTS public.company_dsn_payroll_totals (
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    period text NOT NULL CHECK (period ~ '^\d{4}-\d{2}$'),
    gross_salary numeric(14, 2) NOT NULL DEFAULT 0,
    net_imposable numeric(14, 2) NOT NULL DEFAULT 0,
    pas numeric(14, 2) NOT NULL DEFAULT 0,
    employee_count int NOT NULL DEFAULT 0,
    employees_with_gross int NOT NULL DEFAULT 0,
    last_batch_id uuid REFERENCES public.dsn_import_batches(id) ON DELETE SET NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, period)
);

CREATE INDEX IF NOT EXISTS company_dsn_payroll_totals_company_period_idx
    ON public.company_dsn_payroll_totals (company_id, period DESC);

COMMENT ON TABLE public.company_dsn_payroll_totals IS
    'Masse salariale mensuelle déclarée DSN par entreprise (agrégat commit import).';

COMMENT ON COLUMN public.company_dsn_payroll_totals.gross_salary IS
    'Somme des month_totals.brut salariés pour la période (montant mensuel, pas YTD).';

ALTER TABLE public.company_dsn_payroll_totals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_dsn_payroll_totals_select ON public.company_dsn_payroll_totals;
CREATE POLICY company_dsn_payroll_totals_select ON public.company_dsn_payroll_totals
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

-- Écriture réservée au backend (service_role) ; pas de policy INSERT/UPDATE côté client.
