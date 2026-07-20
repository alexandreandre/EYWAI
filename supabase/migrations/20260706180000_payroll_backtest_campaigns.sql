-- Campagnes backtest paie (convergence Ayway vs référentiel Cegid)

CREATE TABLE IF NOT EXISTS public.payroll_backtest_campaigns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2020 AND year <= 2100),
    month integer NOT NULL CHECK (month >= 1 AND month <= 12),
    reference_dir text,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    config jsonb NOT NULL DEFAULT '{}'::jsonb,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    notify_email text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_payroll_backtest_campaigns_status
    ON public.payroll_backtest_campaigns(status, updated_at DESC);

COMMENT ON TABLE public.payroll_backtest_campaigns IS
    'Campagne backtest paie entreprise × mois (orchestration autonome).';

CREATE TABLE IF NOT EXISTS public.payroll_backtest_employee_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES public.payroll_backtest_campaigns(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'validated', 'blocked', 'skipped')),
    reference_source text,
    last_comparison jsonb NOT NULL DEFAULT '{}'::jsonb,
    fixes_applied jsonb NOT NULL DEFAULT '[]'::jsonb,
    iteration_count integer NOT NULL DEFAULT 0,
    blocked_reason text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (campaign_id, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_payroll_backtest_employee_runs_campaign
    ON public.payroll_backtest_employee_runs(campaign_id, status);

COMMENT ON TABLE public.payroll_backtest_employee_runs IS
    'Suivi salarié par campagne backtest paie.';

ALTER TABLE public.payroll_backtest_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payroll_backtest_employee_runs ENABLE ROW LEVEL SECURITY;
