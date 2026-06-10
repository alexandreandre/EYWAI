-- Remboursement glissant : suivi du reliquat par échéance et lien remboursement ↔ échéance.

ALTER TABLE public.employee_loan_installments
    ADD COLUMN IF NOT EXISTS capital_paid numeric(12, 2) NOT NULL DEFAULT 0
        CHECK (capital_paid >= 0),
    ADD COLUMN IF NOT EXISTS interest_paid numeric(12, 2) NOT NULL DEFAULT 0
        CHECK (interest_paid >= 0);

ALTER TABLE public.employee_loan_installments
    DROP CONSTRAINT IF EXISTS employee_loan_installments_status_check;

ALTER TABLE public.employee_loan_installments
    ADD CONSTRAINT employee_loan_installments_status_check
        CHECK (status IN ('pending', 'partial', 'paid', 'skipped'));

ALTER TABLE public.employee_loan_repayments
    ADD COLUMN IF NOT EXISTS installment_id uuid
        REFERENCES public.employee_loan_installments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_employee_loan_repayments_installment
    ON public.employee_loan_repayments(installment_id);

COMMENT ON COLUMN public.employee_loan_installments.capital_paid IS
    'Capital déjà prélevé sur cette échéance (remboursement glissant).';
COMMENT ON COLUMN public.employee_loan_installments.interest_paid IS
    'Intérêts déjà prélevés sur cette échéance (remboursement glissant).';
COMMENT ON COLUMN public.employee_loan_repayments.installment_id IS
    'Échéance d''amortissement concernée par ce prélèvement bulletin.';

-- Backfill : échéances pending avec remboursements existants sur la même période prêt.
UPDATE public.employee_loan_installments AS i
SET
    capital_paid = agg.total_capital,
    interest_paid = agg.total_interest,
    status = CASE
        WHEN agg.total_capital >= i.capital_part
             AND agg.total_interest >= i.interest_part
        THEN 'paid'
        ELSE 'partial'
    END
FROM (
    SELECT
        r.loan_id,
        r.year,
        r.month,
        SUM(r.capital_amount) AS total_capital,
        SUM(r.interest_amount) AS total_interest
    FROM public.employee_loan_repayments AS r
    GROUP BY r.loan_id, r.year, r.month
) AS agg
WHERE i.loan_id = agg.loan_id
  AND i.year = agg.year
  AND i.month = agg.month
  AND i.status = 'pending'
  AND (agg.total_capital > 0 OR agg.total_interest > 0);

-- Lier les remboursements existants à leur échéance (même loan + période).
UPDATE public.employee_loan_repayments AS r
SET installment_id = i.id
FROM public.employee_loan_installments AS i
WHERE r.installment_id IS NULL
  AND r.loan_id = i.loan_id
  AND r.year = i.year
  AND r.month = i.month;
