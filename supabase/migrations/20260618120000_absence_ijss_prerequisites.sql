-- Prérequis suivi IJSS : subrogation par absence, attestations, config Net-Entreprises

-- Subrogation persistée par absence (mode « par cas »)
ALTER TABLE public.absence_requests
    ADD COLUMN IF NOT EXISTS subrogation_active boolean;

COMMENT ON COLUMN public.absence_requests.subrogation_active IS
    'Subrogation IJSS pour cet arrêt (null = inférée depuis company_maintenance_settings).';

-- Attestations de salaire (canonique si table préexistante en prod)
CREATE TABLE IF NOT EXISTS public.salary_certificates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id uuid NOT NULL,
    absence_request_id uuid NOT NULL,
    company_id uuid NOT NULL,
    storage_path text NOT NULL,
    filename text NOT NULL,
    generated_by uuid,
    transmitted_to_cpam boolean NOT NULL DEFAULT false,
    transmission_date timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS salary_certificates_absence_request_id_idx
    ON public.salary_certificates (absence_request_id);

CREATE INDEX IF NOT EXISTS salary_certificates_company_id_idx
    ON public.salary_certificates (company_id);

ALTER TABLE public.salary_certificates
    ADD COLUMN IF NOT EXISTS transmitted_to_cpam boolean NOT NULL DEFAULT false;

ALTER TABLE public.salary_certificates
    ADD COLUMN IF NOT EXISTS transmission_date timestamptz;

COMMENT ON TABLE public.salary_certificates IS
    'Attestations de salaire (Cerfa) générées pour les arrêts IJSS.';

ALTER TABLE public.salary_certificates ENABLE ROW LEVEL SECURITY;

-- Config Net-Entreprises par entreprise
CREATE TABLE IF NOT EXISTS public.company_net_entreprises_config (
    company_id uuid PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT false,
    mode text NOT NULL DEFAULT 'manual'
        CHECK (mode IN ('manual', 'api_certificat', 'api_declarant')),
    siret_declarant text,
    raison_sociale_declarant text,
    identifiant text,
    contact_email text,
    certificat_label text,
    certificat_expires_at timestamptz,
    secret_ref text,
    last_test_at timestamptz,
    last_test_status text,
    last_test_message text,
    updated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_net_entreprises_config IS
    'Connexion Net-Entreprises (DSN sortante et flux IJSS entrants).';

ALTER TABLE public.company_net_entreprises_config ENABLE ROW LEVEL SECURITY;

-- Suivi transmissions DSN
CREATE TABLE IF NOT EXISTS public.dsn_transmissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    export_id uuid,
    period text NOT NULL,
    dsn_type text NOT NULL DEFAULT 'mensuelle',
    status text NOT NULL DEFAULT 'generated'
        CHECK (status IN (
            'generated', 'manual', 'queued', 'sent', 'acknowledged', 'rejected'
        )),
    mode text NOT NULL DEFAULT 'manual',
    net_entreprises_ref text,
    submitted_at timestamptz,
    acknowledged_at timestamptz,
    error_message text,
    crm_retour jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dsn_transmissions_company_period_idx
    ON public.dsn_transmissions (company_id, period DESC);

ALTER TABLE public.dsn_transmissions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF to_regclass('public.companies') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conname = 'company_net_entreprises_config_company_id_fkey'
       )
    THEN
        ALTER TABLE public.company_net_entreprises_config
            ADD CONSTRAINT company_net_entreprises_config_company_id_fkey
            FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
    END IF;

    IF to_regclass('public.companies') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conname = 'dsn_transmissions_company_id_fkey'
       )
    THEN
        ALTER TABLE public.dsn_transmissions
            ADD CONSTRAINT dsn_transmissions_company_id_fkey
            FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
    END IF;
END $$;
