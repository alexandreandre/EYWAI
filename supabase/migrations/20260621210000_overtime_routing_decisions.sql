-- Décisions RH mensuelles : répartition HS payer / compteur (politique manual).

CREATE TABLE IF NOT EXISTS public.employee_overtime_routing_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month integer NOT NULL CHECK (month >= 1 AND month <= 12),
    total_hs_hours numeric(10, 2) NOT NULL,
    hours_to_pay numeric(10, 2) NOT NULL,
    hours_to_account numeric(10, 2) NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'validated', 'applied_payroll')),
    decided_by uuid,
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (employee_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_overtime_routing_decisions_company_period
    ON public.employee_overtime_routing_decisions (company_id, year, month);

ALTER TABLE public.employee_overtime_routing_decisions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS overtime_routing_decisions_select ON public.employee_overtime_routing_decisions;
CREATE POLICY overtime_routing_decisions_select ON public.employee_overtime_routing_decisions
    FOR SELECT USING (true);

DROP POLICY IF EXISTS overtime_routing_decisions_write ON public.employee_overtime_routing_decisions;
CREATE POLICY overtime_routing_decisions_write ON public.employee_overtime_routing_decisions
    FOR ALL USING (true) WITH CHECK (true);
