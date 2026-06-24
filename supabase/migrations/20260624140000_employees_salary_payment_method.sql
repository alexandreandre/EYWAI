-- Moyen de paiement du salaire (virement, chèque, espèces).
ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS salary_payment_method text DEFAULT 'virement';

ALTER TABLE public.employees
    DROP CONSTRAINT IF EXISTS employees_salary_payment_method_check;

ALTER TABLE public.employees
    ADD CONSTRAINT employees_salary_payment_method_check
    CHECK (salary_payment_method IN ('virement', 'cheque', 'especes'));

COMMENT ON COLUMN public.employees.salary_payment_method IS
    'Mode de paiement du salaire net : virement (défaut), cheque ou especes.';
