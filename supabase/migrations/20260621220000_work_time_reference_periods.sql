-- Périodes de référence horaire paramétrables par entreprise (activité réduite, horaire transitoire).

CREATE TABLE IF NOT EXISTS public.company_work_time_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    label text NOT NULL,
    start_date date NOT NULL,
    end_date date,
    daily_reference_hours numeric(5, 2),
    weekly_reference_hours numeric(5, 2),
    affects_payroll boolean NOT NULL DEFAULT true,
    affects_planning boolean NOT NULL DEFAULT false,
    default_week_template_id uuid REFERENCES public.company_week_schedule_templates(id) ON DELETE SET NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_work_time_periods_company_dates
    ON public.company_work_time_periods (company_id, start_date, end_date);

ALTER TABLE public.company_work_time_periods ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS work_time_periods_select ON public.company_work_time_periods;
CREATE POLICY work_time_periods_select ON public.company_work_time_periods
    FOR SELECT USING (true);

DROP POLICY IF EXISTS work_time_periods_write ON public.company_work_time_periods;
CREATE POLICY work_time_periods_write ON public.company_work_time_periods
    FOR ALL USING (true) WITH CHECK (true);
