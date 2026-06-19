-- Staging fiable import pointages : batches, items, profils entreprise

CREATE TABLE IF NOT EXISTS public.schedule_import_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'parsed'
        CHECK (status IN ('parsed', 'previewed', 'committing', 'committed', 'failed', 'cancelled')),
    source_type text NOT NULL DEFAULT 'document_pdf'
        CHECK (source_type IN (
            'document_pdf', 'document_image', 'csv', 'xlsx', 'badgeuse', 'nl_text'
        )),
    parser_key text,
    filename text,
    file_hash text,
    file_storage_path text,
    period_year integer,
    period_month integer,
    period_start date,
    period_end date,
    preview_json jsonb,
    summary_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text,
    import_job_id uuid REFERENCES public.schedule_import_jobs(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_schedule_import_batches_company_status
    ON public.schedule_import_batches (company_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_schedule_import_batches_job
    ON public.schedule_import_batches (import_job_id)
    WHERE import_job_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS schedule_import_batches_company_hash_committed_idx
    ON public.schedule_import_batches (company_id, file_hash)
    WHERE file_hash IS NOT NULL AND status = 'committed';

COMMENT ON TABLE public.schedule_import_batches IS
    'Staging métier des imports de pointages (preview avant commit calendrier).';

CREATE TABLE IF NOT EXISTS public.schedule_import_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL REFERENCES public.schedule_import_batches(id) ON DELETE CASCADE,
    row_index integer NOT NULL DEFAULT 0,
    employee_id uuid REFERENCES public.employees(id) ON DELETE SET NULL,
    time_tracking_id text,
    raw_name text,
    jour integer,
    heures numeric,
    type text DEFAULT 'travail',
    nature text NOT NULL DEFAULT 'reel'
        CHECK (nature IN ('prevu', 'reel')),
    match_status text NOT NULL DEFAULT 'unmatched'
        CHECK (match_status IN ('matched', 'ambiguous', 'unmatched', 'skipped')),
    match_method text,
    match_confidence text,
    anomalies jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_schedule_import_items_batch
    ON public.schedule_import_items (batch_id, row_index);

CREATE INDEX IF NOT EXISTS idx_schedule_import_items_employee
    ON public.schedule_import_items (batch_id, employee_id)
    WHERE employee_id IS NOT NULL;

COMMENT ON TABLE public.schedule_import_items IS
    'Lignes staging jour × employé pour import pointages.';

CREATE TABLE IF NOT EXISTS public.company_timesheet_import_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    profile_name text NOT NULL DEFAULT 'default',
    source_type text NOT NULL DEFAULT 'csv'
        CHECK (source_type IN (
            'document_pdf', 'document_image', 'csv', 'xlsx', 'badgeuse', 'nl_text'
        )),
    parser_key text NOT NULL DEFAULT 'tabular_generic',
    column_mapping jsonb NOT NULL DEFAULT '{}'::jsonb,
    options jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, profile_name, source_type)
);

CREATE INDEX IF NOT EXISTS idx_company_timesheet_import_profiles_company
    ON public.company_timesheet_import_profiles (company_id);

COMMENT ON TABLE public.company_timesheet_import_profiles IS
    'Profils de mapping colonnes / options pour import pointages par entreprise.';

ALTER TABLE public.schedule_import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.schedule_import_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_timesheet_import_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS schedule_import_batches_select_company ON public.schedule_import_batches;
CREATE POLICY schedule_import_batches_select_company
    ON public.schedule_import_batches FOR SELECT
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS schedule_import_batches_insert_company ON public.schedule_import_batches;
CREATE POLICY schedule_import_batches_insert_company
    ON public.schedule_import_batches FOR INSERT
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS schedule_import_batches_update_company ON public.schedule_import_batches;
CREATE POLICY schedule_import_batches_update_company
    ON public.schedule_import_batches FOR UPDATE
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS schedule_import_items_select_company ON public.schedule_import_items;
CREATE POLICY schedule_import_items_select_company
    ON public.schedule_import_items FOR SELECT
    USING (
        batch_id IN (
            SELECT b.id FROM public.schedule_import_batches b
            WHERE b.company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
            )
        )
    );

DROP POLICY IF EXISTS schedule_import_items_insert_company ON public.schedule_import_items;
CREATE POLICY schedule_import_items_insert_company
    ON public.schedule_import_items FOR INSERT
    WITH CHECK (
        batch_id IN (
            SELECT b.id FROM public.schedule_import_batches b
            WHERE b.company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
            )
        )
    );

DROP POLICY IF EXISTS company_timesheet_import_profiles_select ON public.company_timesheet_import_profiles;
CREATE POLICY company_timesheet_import_profiles_select
    ON public.company_timesheet_import_profiles FOR SELECT
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_timesheet_import_profiles_write ON public.company_timesheet_import_profiles;
CREATE POLICY company_timesheet_import_profiles_write
    ON public.company_timesheet_import_profiles FOR ALL
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

ALTER TABLE public.schedule_import_runs
    ADD COLUMN IF NOT EXISTS batch_id uuid REFERENCES public.schedule_import_batches(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.schedule_import_runs.batch_id IS
    'Batch staging ayant produit ou validé cet import.';

NOTIFY pgrst, 'reload schema';
