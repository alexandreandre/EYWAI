-- RLS scraping_repair_jobs (aligné scraping_pending_changes / page_snapshots).

ALTER TABLE public.scraping_repair_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY scraping_repair_jobs_service_all
    ON public.scraping_repair_jobs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY scraping_repair_jobs_super_admin_all
    ON public.scraping_repair_jobs
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
