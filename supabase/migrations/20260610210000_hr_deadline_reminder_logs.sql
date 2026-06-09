-- Journal des relances RH échéances (CDD, période d'essai, titre de séjour)

CREATE TABLE IF NOT EXISTS public.hr_deadline_reminder_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    reminder_type TEXT NOT NULL CHECK (
        reminder_type IN ('cdd_end', 'trial_end', 'residence_permit')
    ),
    deadline_date DATE NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, employee_id, reminder_type, deadline_date)
);

CREATE INDEX IF NOT EXISTS hr_deadline_reminder_logs_company_idx
    ON public.hr_deadline_reminder_logs (company_id);

CREATE INDEX IF NOT EXISTS hr_deadline_reminder_logs_employee_idx
    ON public.hr_deadline_reminder_logs (employee_id);

ALTER TABLE public.hr_deadline_reminder_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hr_deadline_reminder_logs_select ON public.hr_deadline_reminder_logs;
CREATE POLICY hr_deadline_reminder_logs_select ON public.hr_deadline_reminder_logs
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS hr_deadline_reminder_logs_write ON public.hr_deadline_reminder_logs;
CREATE POLICY hr_deadline_reminder_logs_write ON public.hr_deadline_reminder_logs
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
