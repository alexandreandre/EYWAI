-- Contrats collectifs prévoyance / santé / retraite supplémentaire (bloc
-- S21.G00.15). Dérivés des DSN acceptées du cabinet (dsn_deriver_psc.py), ils
-- vivaient dans les settings.json des jeux de conformité ; la colonne les
-- porte en base. L'ordre (15.005) est l'identifiant que les affiliations des
-- salariés référencent en 70.013 : il fait partie de la donnée.

ALTER TABLE public.company_dsn_settings
    ADD COLUMN IF NOT EXISTS organismes_complementaires jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.company_dsn_settings.organismes_complementaires IS
    'Contrats collectifs du bloc S21.G00.15 : liste ordonnée {reference, organisme, delegataire, nature, ordre}.';
