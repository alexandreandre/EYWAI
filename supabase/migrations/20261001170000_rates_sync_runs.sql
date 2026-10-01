-- Suivi durable des mises à jour de taux.
-- Le lot ne vit plus seulement dans la mémoire du process API : le cron mensuel
-- et n'importe quelle instance peuvent lire le même run.

CREATE TABLE IF NOT EXISTS public.rates_sync_runs (
    id UUID PRIMARY KEY,
    month_key TEXT,
    trigger TEXT NOT NULL
        CHECK (trigger IN ('schedule', 'manual', 'page')),
    status TEXT NOT NULL
        CHECK (status IN ('running', 'succeeded', 'partial', 'failed', 'cancelled')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    triggered_by TEXT,
    forced BOOLEAN NOT NULL DEFAULT false,
    target JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
    jobs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS rates_sync_runs_one_running_month
    ON public.rates_sync_runs (month_key)
    WHERE status = 'running' AND month_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS rates_sync_runs_month_started
    ON public.rates_sync_runs (month_key, started_at DESC);

COMMENT ON TABLE public.rates_sync_runs IS
    'Lot de mise à jour des taux (manuel ou planifié). Un seul run running par mois.';

CREATE TABLE IF NOT EXISTS public.rates_monthly_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    auto_enabled BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO public.rates_monthly_settings (id, auto_enabled)
VALUES (1, true)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE public.rates_monthly_settings IS
    'Interrupteur global de la mise à jour automatique des taux en début de mois.';

ALTER TABLE public.rates_sync_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rates_monthly_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY rates_sync_runs_service_all
    ON public.rates_sync_runs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY rates_sync_runs_super_admin_all
    ON public.rates_sync_runs
    FOR ALL
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.super_admins sa
            WHERE sa.user_id = auth.uid() AND sa.is_active = true
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.super_admins sa
            WHERE sa.user_id = auth.uid() AND sa.is_active = true
        )
    );

CREATE POLICY rates_monthly_settings_service_all
    ON public.rates_monthly_settings
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY rates_monthly_settings_super_admin_all
    ON public.rates_monthly_settings
    FOR ALL
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.super_admins sa
            WHERE sa.user_id = auth.uid() AND sa.is_active = true
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.super_admins sa
            WHERE sa.user_id = auth.uid() AND sa.is_active = true
        )
    );
