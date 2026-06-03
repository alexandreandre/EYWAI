-- Scraping v2 : tripwire. Snapshots des pages officielles pour détecter un
-- changement matériel AVANT que le parser ne casse silencieusement.
-- Cette couche n'écrit jamais payroll_config : elle alerte uniquement.

CREATE TABLE IF NOT EXISTS public.scraping_page_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES public.scraping_sources (id) ON DELETE SET NULL,
    source_key TEXT,
    url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    normalized_excerpt TEXT,
    http_status INTEGER,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scraping_page_snapshots_url_fetched
    ON public.scraping_page_snapshots (url, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraping_page_snapshots_source
    ON public.scraping_page_snapshots (source_id);

ALTER TABLE public.scraping_page_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY scraping_page_snapshots_service_all
    ON public.scraping_page_snapshots
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY scraping_page_snapshots_super_admin_all
    ON public.scraping_page_snapshots
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
