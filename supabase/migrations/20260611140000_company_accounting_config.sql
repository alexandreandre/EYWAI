-- Configuration d'intégration comptable par entreprise (mode manuel / API / SFTP).
--
-- Idempotent et tolérant à un schéma partiel :
-- - FK companies ajoutée seulement si public.companies existe
-- - Policies RLS ajoutées seulement si public.user_company_accesses existe
--   (sinon RLS actif sans policy : accès service_role backend uniquement)

CREATE TABLE IF NOT EXISTS public.company_accounting_config (
    company_id uuid PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT false,
    mode text NOT NULL DEFAULT 'manual'
        CHECK (mode IN ('manual', 'api_quadra', 'api_sage', 'api_pennylane', 'sftp')),
    credentials_ref text,
    default_format text NOT NULL DEFAULT 'csv',
    recipients_compta text[] NOT NULL DEFAULT '{}',
    last_transmission_at timestamptz,
    last_test_at timestamptz,
    last_test_status text,
    last_test_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF to_regclass('public.companies') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
           FROM pg_constraint
           WHERE conname = 'company_accounting_config_company_id_fkey'
             AND conrelid = 'public.company_accounting_config'::regclass
       )
    THEN
        ALTER TABLE public.company_accounting_config
            ADD CONSTRAINT company_accounting_config_company_id_fkey
            FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
    END IF;
END $$;

COMMENT ON TABLE public.company_accounting_config IS
    'Mode de transmission comptable par entreprise (manuel, API logiciel, SFTP).';

ALTER TABLE public.company_accounting_config ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF to_regclass('public.user_company_accesses') IS NULL THEN
        RAISE NOTICE
            'company_accounting_config : user_company_accesses absent — policies RLS non créées (accès service_role uniquement).';
        RETURN;
    END IF;

    DROP POLICY IF EXISTS company_accounting_config_select ON public.company_accounting_config;
    CREATE POLICY company_accounting_config_select ON public.company_accounting_config
        FOR SELECT TO authenticated
        USING (
            company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
            )
        );

    DROP POLICY IF EXISTS company_accounting_config_write ON public.company_accounting_config;
    CREATE POLICY company_accounting_config_write ON public.company_accounting_config
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
END $$;
