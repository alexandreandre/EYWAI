-- Prêts employeur au salarié : contrat, échéancier, remboursements paie.

CREATE TABLE IF NOT EXISTS public.employee_loans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    principal_amount numeric(12, 2) NOT NULL CHECK (principal_amount > 0),
    annual_interest_rate numeric(8, 4) NOT NULL DEFAULT 0 CHECK (annual_interest_rate >= 0),
    start_date date NOT NULL,
    duration_months integer NOT NULL CHECK (duration_months >= 1 AND duration_months <= 360),
    monthly_payment numeric(12, 2) NOT NULL CHECK (monthly_payment > 0),
    repayment_day integer NOT NULL DEFAULT 1 CHECK (repayment_day >= 1 AND repayment_day <= 28),
    reason text,
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'suspended', 'repaid', 'cancelled', 'defaulted')),
    remaining_capital numeric(12, 2) NOT NULL DEFAULT 0 CHECK (remaining_capital >= 0),
    requires_2062_declaration boolean NOT NULL DEFAULT false,
    declared_2062 boolean NOT NULL DEFAULT false,
    contract_file_path text,
    created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.employee_loans IS
    'Prêts d''argent de l''entreprise au salarié (capital, taux, échéancier, statut).';

CREATE TABLE IF NOT EXISTS public.employee_loan_installments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id uuid NOT NULL REFERENCES public.employee_loans(id) ON DELETE CASCADE,
    installment_number integer NOT NULL CHECK (installment_number >= 1),
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month integer NOT NULL CHECK (month >= 1 AND month <= 12),
    capital_part numeric(12, 2) NOT NULL DEFAULT 0 CHECK (capital_part >= 0),
    interest_part numeric(12, 2) NOT NULL DEFAULT 0 CHECK (interest_part >= 0),
    total_due numeric(12, 2) NOT NULL CHECK (total_due >= 0),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'paid', 'skipped')),
    payslip_id uuid REFERENCES public.payslips(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (loan_id, installment_number)
);

COMMENT ON TABLE public.employee_loan_installments IS
    'Échéancier d''amortissement prévisionnel d''un prêt employeur.';

CREATE TABLE IF NOT EXISTS public.employee_loan_repayments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id uuid NOT NULL REFERENCES public.employee_loans(id) ON DELETE CASCADE,
    payslip_id uuid REFERENCES public.payslips(id) ON DELETE SET NULL,
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month integer NOT NULL CHECK (month >= 1 AND month <= 12),
    capital_amount numeric(12, 2) NOT NULL DEFAULT 0 CHECK (capital_amount >= 0),
    interest_amount numeric(12, 2) NOT NULL DEFAULT 0 CHECK (interest_amount >= 0),
    avantage_nature_amount numeric(12, 2) NOT NULL DEFAULT 0 CHECK (avantage_nature_amount >= 0),
    remaining_after numeric(12, 2) NOT NULL DEFAULT 0 CHECK (remaining_after >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.employee_loan_repayments IS
    'Historique des remboursements de prêt appliqués sur bulletin de paie.';

CREATE INDEX IF NOT EXISTS idx_employee_loans_company_status
    ON public.employee_loans(company_id, status);

CREATE INDEX IF NOT EXISTS idx_employee_loans_employee
    ON public.employee_loans(employee_id);

CREATE INDEX IF NOT EXISTS idx_employee_loan_installments_loan_period
    ON public.employee_loan_installments(loan_id, year, month);

CREATE INDEX IF NOT EXISTS idx_employee_loan_repayments_loan
    ON public.employee_loan_repayments(loan_id);

ALTER TABLE public.employee_loans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_loan_installments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_loan_repayments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS employee_loans_select ON public.employee_loans;
CREATE POLICY employee_loans_select ON public.employee_loans
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_loans_write ON public.employee_loans;
CREATE POLICY employee_loans_write ON public.employee_loans
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

DROP POLICY IF EXISTS employee_loan_installments_select ON public.employee_loan_installments;
CREATE POLICY employee_loan_installments_select ON public.employee_loan_installments
    FOR SELECT TO authenticated
    USING (
        loan_id IN (
            SELECT el.id FROM public.employee_loans el
            WHERE el.company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
            )
        )
    );

DROP POLICY IF EXISTS employee_loan_installments_write ON public.employee_loan_installments;
CREATE POLICY employee_loan_installments_write ON public.employee_loan_installments
    FOR ALL TO authenticated
    USING (
        loan_id IN (
            SELECT el.id FROM public.employee_loans el
            WHERE el.company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
                AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
            )
        )
    )
    WITH CHECK (
        loan_id IN (
            SELECT el.id FROM public.employee_loans el
            WHERE el.company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
                AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
            )
        )
    );

DROP POLICY IF EXISTS employee_loan_repayments_select ON public.employee_loan_repayments;
CREATE POLICY employee_loan_repayments_select ON public.employee_loan_repayments
    FOR SELECT TO authenticated
    USING (
        loan_id IN (
            SELECT el.id FROM public.employee_loans el
            WHERE el.company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
            )
        )
    );

DROP POLICY IF EXISTS employee_loan_repayments_write ON public.employee_loan_repayments;
CREATE POLICY employee_loan_repayments_write ON public.employee_loan_repayments
    FOR ALL TO authenticated
    USING (
        loan_id IN (
            SELECT el.id FROM public.employee_loans el
            WHERE el.company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
                AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
            )
        )
    )
    WITH CHECK (
        loan_id IN (
            SELECT el.id FROM public.employee_loans el
            WHERE el.company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
                AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
            )
        )
    );

-- Taux d'intérêt légal (semestriel) pour calcul avantage en nature prêt employeur.
INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'taux_interet_legal',
    '{
        "taux_annuel": 0.0352,
        "semestre": "2025-S2",
        "source": "Arrêté du 19 décembre 2024 — taux légal 1er semestre 2025"
    }'::jsonb,
    1,
    true,
    'Taux d''intérêt légal pour avantage en nature prêt employeur (à mettre à jour semestriellement)',
    NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'taux_interet_legal' AND company_id IS NULL
);
