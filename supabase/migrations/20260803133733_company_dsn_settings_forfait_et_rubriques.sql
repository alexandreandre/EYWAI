-- Compléments au paramétrage DSN, ajoutés après la première migration :
-- la quotité déclarée pour les forfaits annuels en jours (21,67 chez certaines
-- sociétés, 21,27 chez d'autres) et les rubriques d'établissement que le
-- builder ne dérive pas et qu'on reprend telles quelles du cabinet.

ALTER TABLE public.company_dsn_settings
    ADD COLUMN IF NOT EXISTS quotite_forfait_jours text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS rubriques_etablissement jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN public.company_dsn_settings.quotite_forfait_jours IS
    'Quotité mensuelle déclarée pour les contrats comptés en jours (S21.G00.40.012).';

COMMENT ON COLUMN public.company_dsn_settings.rubriques_etablissement IS
    'Rubriques S21.G00.11.xxx reprises du cabinet, non dérivées par le builder.';
