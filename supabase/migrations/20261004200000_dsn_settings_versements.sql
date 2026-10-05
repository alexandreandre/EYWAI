-- Versements aux organismes (bloc S21.G00.20) et assujettissements fiscaux
-- (bloc S21.G00.44) de la DSN mensuelle. Repris des DSN acceptées du cabinet
-- (dsn_settings_reprise.py) : organisme, entité d'affectation, BIC / IBAN,
-- mode de paiement, délégataire ; codes taxe déclarés chaque mois. Les
-- montants ne sont pas stockés : la DSN les calcule depuis les bulletins.

ALTER TABLE public.company_dsn_settings
    ADD COLUMN IF NOT EXISTS versements jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS assujettissements_fiscaux jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.company_dsn_settings.versements IS
    'Organismes payés par la DSN (bloc S21.G00.20) : liste {organisme, entite, bic, iban, mode, delegataire}.';
COMMENT ON COLUMN public.company_dsn_settings.assujettissements_fiscaux IS
    'Codes taxe du bloc S21.G00.44 déclarés chaque mois (001, 003, 007, 013…).';
