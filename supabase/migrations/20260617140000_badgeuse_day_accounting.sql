-- Badgeuse : heures comptabilisées (override RH par jour, distinct de la validation).

CREATE TABLE IF NOT EXISTS public.employee_time_day_accounting (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id uuid NOT NULL,
    company_id uuid NOT NULL,
    day date NOT NULL,
    accounted_seconds integer NOT NULL
        CHECK (accounted_seconds >= 0 AND accounted_seconds <= 86400),
    updated_by uuid NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (employee_id, company_id, day)
);

CREATE INDEX IF NOT EXISTS idx_employee_time_day_accounting_company_day
    ON public.employee_time_day_accounting (company_id, day);

ALTER TABLE public.employee_time_day_accounting ENABLE ROW LEVEL SECURITY;

CREATE POLICY employee_time_day_accounting_select ON public.employee_time_day_accounting
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
        OR employee_id = auth.uid()
    );

CREATE POLICY employee_time_day_accounting_write ON public.employee_time_day_accounting
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
