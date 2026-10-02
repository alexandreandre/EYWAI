-- Contrats passés d'un salarié. Le contrat en cours reste sur employees
-- (hire_date, contract_end_date). Cette table ne recalcule pas l'ancienneté.

CREATE TABLE IF NOT EXISTS public.employee_contract_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    contract_type text NOT NULL,
    date_debut date NOT NULL,
    date_fin date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT employee_contract_periods_range CHECK (date_fin >= date_debut)
);

CREATE INDEX IF NOT EXISTS employee_contract_periods_employee_idx
    ON public.employee_contract_periods (employee_id, date_debut DESC);

COMMENT ON TABLE public.employee_contract_periods IS
    'Contrat passé saisi par la RH. N''alimente pas la date d''ancienneté.';

ALTER TABLE public.employee_contract_periods ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS employee_contract_periods_select ON public.employee_contract_periods;
CREATE POLICY employee_contract_periods_select ON public.employee_contract_periods
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_contract_periods_write ON public.employee_contract_periods;
CREATE POLICY employee_contract_periods_write ON public.employee_contract_periods
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
