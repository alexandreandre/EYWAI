-- Journal des échanges avec l'assistant RH (06/08/2026).
--
-- On ne sait pas ce que les gestionnaires RH demandent réellement à l'assistant :
-- aucune table, aucun log ne conserve les questions. Toute amélioration se fait
-- donc à l'aveugle, sur un banc d'essai reconstitué. Cette table sert à savoir
-- quelles questions arrivent, où elles sont routées, et lesquelles échouent.
--
-- Données conservées : la QUESTION, jamais la réponse — seule sa longueur est
-- enregistrée. Cela suffit à mesurer l'usage sans dupliquer des informations RH
-- dans une seconde table.
--
-- Accès : RLS activée sans policy et droits retirés à anon/authenticated, comme
-- les autres tables du schéma (cf. 20260804160000). Le backend tourne avec
-- service_role, qui contourne la RLS.
--
-- Idempotent : ré-exécutable sans erreur.

CREATE TABLE IF NOT EXISTS public.copilot_interactions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          timestamptz NOT NULL DEFAULT now(),
    company_id          uuid REFERENCES public.companies(id) ON DELETE CASCADE,
    user_id             uuid,
    question            text NOT NULL,
    routage             text,
    outils              text[] NOT NULL DEFAULT '{}',
    latence_ms          integer,
    reponse_caracteres  integer,
    erreur              text
);

COMMENT ON TABLE public.copilot_interactions IS
    'Journal des échanges avec l''assistant RH : question, routage, outils, '
    'latence. La réponse n''est pas conservée (seule sa longueur l''est). '
    'À purger périodiquement.';
COMMENT ON COLUMN public.copilot_interactions.routage IS
    'Branche empruntée : app_help | cc | data | clarif | aucune | erreur.';
COMMENT ON COLUMN public.copilot_interactions.outils IS
    'Outils du catalogue réellement exécutés pendant le tour.';

CREATE INDEX IF NOT EXISTS idx_copilot_interactions_company_date
    ON public.copilot_interactions (company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_copilot_interactions_date
    ON public.copilot_interactions (created_at DESC);

ALTER TABLE public.copilot_interactions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.copilot_interactions FROM anon, authenticated;
