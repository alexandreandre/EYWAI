-- Fenêtre des variables (heures sup, paniers) d'une société pour un mois donné.
--
-- Sans ligne ici, la fenêtre reste celle de la règle société
-- (companies.paie_jour_de_fin / paie_occurrence). Une ligne signifie que la
-- gestionnaire de paie a arrêté les compteurs à une autre date ce mois-là.
--
-- Idempotent : ré-exécutable sans erreur.

CREATE TABLE IF NOT EXISTS public.company_variable_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    year smallint NOT NULL,
    month smallint NOT NULL CHECK (month BETWEEN 1 AND 12),
    start_date date NOT NULL,
    end_date date NOT NULL,
    origin text NOT NULL DEFAULT 'manuel' CHECK (origin IN ('regle', 'manuel')),
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT company_variable_periods_bornes CHECK (end_date >= start_date)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_company_variable_periods_unicite
    ON public.company_variable_periods (company_id, year, month);

-- Table qui pilote la paie : aucun accès anonyme ni authentifié direct.
-- La lecture et l'écriture passent par le backend (service role), comme
-- company_work_time_periods depuis le 23/08/2026.
ALTER TABLE public.company_variable_periods ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.company_variable_periods FROM anon, authenticated;
