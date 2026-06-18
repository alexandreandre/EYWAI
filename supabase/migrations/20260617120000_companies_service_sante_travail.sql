-- Coordonnées du service de santé au travail (SPST) au niveau entreprise

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS service_sante_travail_nom text;

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS service_sante_travail_adresse_rue text;

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS service_sante_travail_adresse_code_postal text;

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS service_sante_travail_adresse_ville text;

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS service_sante_travail_telephone text;

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS service_sante_travail_email text;

COMMENT ON COLUMN public.companies.service_sante_travail_nom IS
    'Nom du service de santé au travail (SPST/SPSTI)';

COMMENT ON COLUMN public.companies.service_sante_travail_adresse_rue IS
    'Adresse rue du service de santé au travail';

COMMENT ON COLUMN public.companies.service_sante_travail_adresse_code_postal IS
    'Code postal du service de santé au travail';

COMMENT ON COLUMN public.companies.service_sante_travail_adresse_ville IS
    'Ville du service de santé au travail';

COMMENT ON COLUMN public.companies.service_sante_travail_telephone IS
    'Téléphone du service de santé au travail pour prise de rendez-vous';

COMMENT ON COLUMN public.companies.service_sante_travail_email IS
    'Email du service de santé au travail';
