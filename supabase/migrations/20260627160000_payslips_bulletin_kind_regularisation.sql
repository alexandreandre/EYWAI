-- Marqueur de nature du bulletin de paie.
-- Permet de distinguer les bulletins « normaux » des bulletins de régularisation
-- (ex. participation versée l'année suivant un départ) afin :
--   - d'autoriser leur génération pour un salarié déjà sorti (statut parti/en_sortie) ;
--   - de les protéger du nettoyage automatique à l'archivage d'une sortie.
--
-- NULL = bulletin de paie mensuel standard.
-- 'regularisation_participation' = versement participation / intéressement post-paie.

ALTER TABLE public.payslips
    ADD COLUMN IF NOT EXISTS bulletin_kind text;

COMMENT ON COLUMN public.payslips.bulletin_kind IS
    'Nature du bulletin : NULL = mensuel standard ; '
    '''regularisation_participation'' = régularisation participation/intéressement '
    '(notamment pour un salarié déjà parti). Exclu du nettoyage d''archivage de sortie.';

CREATE INDEX IF NOT EXISTS idx_payslips_bulletin_kind
    ON public.payslips(company_id, employee_id, bulletin_kind)
    WHERE bulletin_kind IS NOT NULL;
