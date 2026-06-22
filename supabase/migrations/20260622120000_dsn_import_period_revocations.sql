-- Révocations d'import DSN par entreprise / période (sans supprimer les fiches salariés).

CREATE TABLE IF NOT EXISTS public.dsn_import_period_revocations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    period text NOT NULL,
    revoked_at timestamptz NOT NULL DEFAULT now(),
    revoked_by uuid,
    CONSTRAINT dsn_import_period_revocations_period_format CHECK (period ~ '^\d{4}-\d{2}$'),
    CONSTRAINT dsn_import_period_revocations_company_period_key UNIQUE (company_id, period)
);

CREATE INDEX IF NOT EXISTS dsn_import_period_revocations_company_idx
    ON public.dsn_import_period_revocations (company_id, period);

COMMENT ON TABLE public.dsn_import_period_revocations IS
    'Périodes DSN révoquées manuellement (cumuls supprimés, couverture retirée).';

ALTER TABLE public.dsn_import_period_revocations ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF to_regclass('public.super_admins') IS NULL THEN
        RAISE NOTICE 'dsn_import_period_revocations : policies RLS non créées (super_admins absent).';
        RETURN;
    END IF;

    DROP POLICY IF EXISTS dsn_import_period_revocations_super_admin
        ON public.dsn_import_period_revocations;
    CREATE POLICY dsn_import_period_revocations_super_admin
        ON public.dsn_import_period_revocations
        FOR ALL
        USING (
            EXISTS (
                SELECT 1 FROM public.super_admins sa
                WHERE sa.user_id = auth.uid()
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM public.super_admins sa
                WHERE sa.user_id = auth.uid()
            )
        );
END $$;
