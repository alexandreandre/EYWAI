-- Scraping v2 : gate de validation humaine sur le tier critique.
-- Staging des changements de taux critiques AVANT écriture dans payroll_config.
-- L'orchestrateur dépose ici ; un super admin valide/rejette ; apply_pending_change
-- applique ensuite via la logique de versioning payroll_config existante.

CREATE TABLE IF NOT EXISTS public.scraping_pending_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES public.scraping_sources (id) ON DELETE SET NULL,
    scraper_name TEXT NOT NULL,
    config_key TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'critical',
    persistence_mode TEXT NOT NULL DEFAULT 'full',
    proposed_config_data JSONB NOT NULL,
    current_config_data JSONB,
    current_version INTEGER,
    source_links JSONB NOT NULL DEFAULT '[]'::jsonb,
    decision_case TEXT,
    sources_agreement BOOLEAN,
    discrepancies JSONB,
    ai_candidate JSONB,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'superseded')),
    created_by_job_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by UUID,
    review_note TEXT,
    applied_at TIMESTAMPTZ,
    applied_payroll_config_id UUID
);

CREATE INDEX IF NOT EXISTS idx_scraping_pending_changes_status
    ON public.scraping_pending_changes (status);
CREATE INDEX IF NOT EXISTS idx_scraping_pending_changes_config_key
    ON public.scraping_pending_changes (config_key);
CREATE INDEX IF NOT EXISTS idx_scraping_pending_changes_created_at
    ON public.scraping_pending_changes (created_at DESC);

-- Un seul changement en attente par (config_key, scraper_name).
CREATE UNIQUE INDEX IF NOT EXISTS uq_scraping_pending_changes_active
    ON public.scraping_pending_changes (config_key, scraper_name)
    WHERE status = 'pending';

-- RLS : super administrateurs uniquement (le service_role bypass la RLS pour
-- l'orchestrateur et l'apply en subprocess).
ALTER TABLE public.scraping_pending_changes ENABLE ROW LEVEL SECURITY;

CREATE POLICY scraping_pending_changes_service_all
    ON public.scraping_pending_changes
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY scraping_pending_changes_super_admin_all
    ON public.scraping_pending_changes
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

-- Réconciliation tier (manifeste) -> is_critical (DB) : les sources dont le
-- scraper est tier="critical" dans scraper_manifest.py doivent être is_critical.
UPDATE public.scraping_sources
SET is_critical = true, updated_at = now()
WHERE source_key IN (
    'SMIC',
    'PSS',
    'PAS',
    'CSG',
    'DIALOGUE_SOCIAL',
    'AGS',
    'ALLOCATIONS_FAMILIALES',
    'VIEILLESSE_PATRONAL',
    'VIEILLESSE_SALARIAL',
    'MMID_PATRONAL',
    'AGIRC-ARRCO'
)
AND is_critical IS DISTINCT FROM true;
