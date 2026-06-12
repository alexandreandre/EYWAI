-- Intégrations comptables : catalogue plateforme + suivi des transmissions

-- Étendre la config entreprise
ALTER TABLE public.company_accounting_config
  ADD COLUMN IF NOT EXISTS provider text NOT NULL DEFAULT 'manual',
  ADD COLUMN IF NOT EXISTS auth_type text,
  ADD COLUMN IF NOT EXISTS force_manual boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.company_accounting_config.provider IS
  'Clé fournisseur : manual, cegid_quadra, sage, pennylane, generic_sftp';
COMMENT ON COLUMN public.company_accounting_config.force_manual IS
  'Si true, les envois compta restent manuels même si une API est configurée.';

-- Catalogue plateforme (super-admin)
CREATE TABLE IF NOT EXISTS public.platform_accounting_providers (
    provider_key text PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT false,
    platform_credentials_ref text,
    settings jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_test_at timestamptz,
    last_test_status text,
    last_test_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.platform_accounting_providers IS
    'Catalogue des fournisseurs comptables activables par la plateforme EYWAI.';

ALTER TABLE public.platform_accounting_providers ENABLE ROW LEVEL SECURITY;

-- Suivi des transmissions compta
CREATE TABLE IF NOT EXISTS public.accounting_transmissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    period text NOT NULL,
    channel text NOT NULL DEFAULT 'compta' CHECK (channel IN ('compta', 'banque')),
    provider text NOT NULL DEFAULT 'manual',
    mode text NOT NULL DEFAULT 'manual',
    export_ids uuid[] NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'generated'
        CHECK (status IN ('generated', 'queued', 'sent', 'acknowledged', 'rejected', 'manual', 'failed')),
    external_ref text,
    error_message text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz,
    acknowledged_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS accounting_transmissions_company_period_idx
    ON public.accounting_transmissions (company_id, period DESC);

CREATE INDEX IF NOT EXISTS accounting_transmissions_status_idx
    ON public.accounting_transmissions (status, created_at DESC);

COMMENT ON TABLE public.accounting_transmissions IS
    'Suivi des envois comptables (API ou manuel) par entreprise et période.';

ALTER TABLE public.accounting_transmissions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF to_regclass('public.companies') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conname = 'accounting_transmissions_company_id_fkey'
       )
    THEN
        ALTER TABLE public.accounting_transmissions
            ADD CONSTRAINT accounting_transmissions_company_id_fkey
            FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Seed catalogue (idempotent)
INSERT INTO public.platform_accounting_providers (provider_key, enabled, settings)
VALUES
    ('manual', true, '{"always_available": true}'::jsonb),
    ('cegid_quadra', false, '{"api_base_url": ""}'::jsonb),
    ('sage', false, '{}'::jsonb),
    ('pennylane', false, '{}'::jsonb),
    ('generic_sftp', false, '{}'::jsonb)
ON CONFLICT (provider_key) DO NOTHING;

DO $$
BEGIN
    IF to_regclass('public.user_company_accesses') IS NULL THEN
        RAISE NOTICE 'accounting_transmissions : policies RLS non créées (user_company_accesses absent).';
        RETURN;
    END IF;

    DROP POLICY IF EXISTS accounting_transmissions_select ON public.accounting_transmissions;
    CREATE POLICY accounting_transmissions_select ON public.accounting_transmissions
        FOR SELECT TO authenticated
        USING (
            company_id IN (
                SELECT uca.company_id FROM public.user_company_accesses uca
                WHERE uca.user_id = auth.uid()
            )
        );
END $$;
