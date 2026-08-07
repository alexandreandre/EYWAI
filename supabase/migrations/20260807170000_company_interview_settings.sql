-- Politique d'entretien annuel par société.
--
-- Le classeur transmis par Elsa le 27/07/2026 donne une règle de campagne différente
-- pour chacune des sept sociétés : mois fixe pour six d'entre elles (octobre, novembre
-- ou décembre), date d'ancienneté pour la septième, et un cycle de deux ans pour une
-- seule. Ces règles vivent ici plutôt que dans le script de reprise : sinon il faut
-- rejouer un script à la main chaque automne pour proposer la campagne suivante.
--
-- enabled vaut false par défaut, comme pour le JTC : tant qu'une société n'est pas
-- réglée, ni ses écrans ni ses suggestions de planification ne changent.

CREATE TABLE IF NOT EXISTS public.company_interview_settings (
    company_id uuid PRIMARY KEY REFERENCES public.companies(id) ON DELETE CASCADE,
    enabled boolean NOT NULL DEFAULT false,
    campaign_mode text NOT NULL DEFAULT 'mois_fixe',
    campaign_month integer,
    periodicity_years integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT company_interview_settings_mode_connu
        CHECK (campaign_mode IN ('mois_fixe', 'anniversaire_embauche')),

    -- Un mois est obligatoire en mois fixe, et interdit sur l'anniversaire d'embauche :
    -- laisser les deux cohabiter ferait dépendre la date d'un ordre de lecture.
    CONSTRAINT company_interview_settings_mois_coherent
        CHECK (
            (campaign_mode = 'mois_fixe'
                AND campaign_month IS NOT NULL
                AND campaign_month BETWEEN 1 AND 12)
            OR
            (campaign_mode = 'anniversaire_embauche' AND campaign_month IS NULL)
        ),

    CONSTRAINT company_interview_settings_periodicite_bornee
        CHECK (periodicity_years BETWEEN 1 AND 6)
);

COMMENT ON TABLE public.company_interview_settings IS
    'Politique de campagne des entretiens annuels, une ligne par société.';
COMMENT ON COLUMN public.company_interview_settings.enabled IS
    'Faux par défaut : aucune suggestion de campagne tant que la société n''est pas réglée.';
COMMENT ON COLUMN public.company_interview_settings.campaign_mode IS
    'mois_fixe : campagne groupée sur un mois. anniversaire_embauche : à la date d''ancienneté.';
COMMENT ON COLUMN public.company_interview_settings.periodicity_years IS
    'Nombre d''années entre deux entretiens. 6 au maximum, borne du bilan L6315-1.';

ALTER TABLE public.company_interview_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_interview_settings_select
    ON public.company_interview_settings;
CREATE POLICY company_interview_settings_select
    ON public.company_interview_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

-- Écriture réservée au backend (service_role) : pas de policy INSERT/UPDATE client.

-- Provenance d'une reprise : distingue un entretien repris d'un entretien saisi dans
-- EYWAI, et permet de rejouer l'import sans jamais créer de doublon.
ALTER TABLE public.annual_reviews
    ADD COLUMN IF NOT EXISTS import_source text;

COMMENT ON COLUMN public.annual_reviews.import_source IS
    'Renseigné pour une ligne issue d''une reprise de données (ex. planif_entretiens_2026-07-27). NULL si saisi dans EYWAI.';

CREATE INDEX IF NOT EXISTS annual_reviews_company_year_type
    ON public.annual_reviews (company_id, year, interview_type);
