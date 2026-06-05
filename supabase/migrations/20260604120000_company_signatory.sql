-- Signataire RH pour documents PDF générés (contrats, attestations, etc.)

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS nom_signataire_rh text;

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS qualite_signataire_rh text;

COMMENT ON COLUMN public.companies.nom_signataire_rh IS
    'Nom du signataire RH affiché sur les documents PDF générés';

COMMENT ON COLUMN public.companies.qualite_signataire_rh IS
    'Qualité du signataire RH (ex. Directeur RH, Gérant)';
