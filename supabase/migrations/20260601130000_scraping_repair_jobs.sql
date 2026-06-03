-- Agent autonome de réparation scraping : file d'attente + suivi validation URLs officielles.

ALTER TABLE public.scraping_sources
    ADD COLUMN IF NOT EXISTS url_validated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS url_validation_status TEXT
        CHECK (
            url_validation_status IS NULL
            OR url_validation_status IN ('valid', 'invalid', 'unknown')
        );

CREATE TABLE IF NOT EXISTS public.scraping_repair_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scraper_name TEXT NOT NULL,
    source_id UUID REFERENCES public.scraping_sources (id) ON DELETE SET NULL,
    trigger TEXT NOT NULL DEFAULT 'manual'
        CHECK (
            trigger IN (
                'orchestrator_failure',
                'tripwire_change',
                'ci_dry_run_failure',
                'parser_repair',
                'manual',
                'source_url_invalid'
            )
        ),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (
            status IN (
                'queued',
                'running',
                'tests_failed',
                'tests_passed',
                'merged',
                'aborted'
            )
        ),
    error_message TEXT,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    attempts INTEGER NOT NULL DEFAULT 0,
    model_used TEXT,
    diff_summary TEXT,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    pr_url TEXT,
    ci_run_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_scraping_repair_jobs_status_created
    ON public.scraping_repair_jobs (status, created_at);

CREATE INDEX IF NOT EXISTS idx_scraping_repair_jobs_scraper_active
    ON public.scraping_repair_jobs (scraper_name, status);

COMMENT ON TABLE public.scraping_repair_jobs IS
    'File d''attente de l''agent autonome de réparation du code scraping (parsers, URLs, fixtures).';

COMMENT ON COLUMN public.scraping_sources.url_validated_at IS
    'Dernière vérification automatique de primary_url (cron mensuel).';

COMMENT ON COLUMN public.scraping_sources.url_validation_status IS
    'Résultat de la dernière validation URL : valid, invalid, unknown.';
