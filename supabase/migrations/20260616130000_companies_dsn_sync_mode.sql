-- Mode de synchronisation DSN par entreprise (alertes et suivi couverture).

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS dsn_sync_mode text;

ALTER TABLE public.companies
    DROP CONSTRAINT IF EXISTS companies_dsn_sync_mode_check;

ALTER TABLE public.companies
    ADD CONSTRAINT companies_dsn_sync_mode_check
    CHECK (dsn_sync_mode IS NULL OR dsn_sync_mode IN ('external', 'native', 'transition'));

COMMENT ON COLUMN public.companies.dsn_sync_mode IS
    'Source paie pour alertes DSN : external (Cegid, etc.), native (paie EYWAI), transition (reprise).';

-- Entreprises existantes sans historique DSN : native par défaut (pas d''alerte).
UPDATE public.companies
SET dsn_sync_mode = 'native'
WHERE dsn_sync_mode IS NULL;
