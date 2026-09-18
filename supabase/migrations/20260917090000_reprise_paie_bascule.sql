-- Bascule de reprise de paie : le dernier mois payé par le système précédent.
--
-- Reprendre la paie d'une société en cours d'année ne se fait pas en rejouant
-- ses mois passés, mais en important les compteurs de l'ancien logiciel à une
-- date de bascule. Une ligne ici signifie : jusqu'à ce mois inclus, les
-- bulletins sont importés et verrouillés ; le premier mois que nous calculons
-- est le suivant, et il part du solde d'ouverture stocké dans
-- employee_schedules.cumuls du mois de bascule.
--
-- Sans ligne, la société est calculée depuis le début : comportement inchangé.
--
-- Idempotent : ré-exécutable sans erreur.

CREATE TABLE IF NOT EXISTS public.company_payroll_takeover (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    cutoff_year smallint NOT NULL,
    cutoff_month smallint NOT NULL CHECK (cutoff_month BETWEEN 1 AND 12),
    source text NOT NULL DEFAULT 'bulletins'
        CHECK (source IN ('bulletins', 'dsn', 'etat_cumuls', 'declaratif')),
    previous_software text,
    note text,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Une seule bascule par société : la date de reprise est un fait, pas un réglage.
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_payroll_takeover_unicite
    ON public.company_payroll_takeover (company_id);

-- Marque d'origine d'un bulletin : importé de l'ancien logiciel, donc jamais
-- recalculé. Invisible à l'écran, c'est elle qui autorise le verrou serveur.
ALTER TABLE public.payslips
    ADD COLUMN IF NOT EXISTS origine text NOT NULL DEFAULT 'calcule';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'payslips_origine_check'
    ) THEN
        ALTER TABLE public.payslips
            ADD CONSTRAINT payslips_origine_check
            CHECK (origine IN ('calcule', 'importe'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_payslips_origine_importe
    ON public.payslips (company_id, year, month)
    WHERE origine = 'importe';

-- Table qui pilote la paie : aucun accès anonyme ni authentifié direct.
-- La lecture et l'écriture passent par le backend (service role), comme
-- company_variable_periods.
ALTER TABLE public.company_payroll_takeover ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.company_payroll_takeover FROM anon, authenticated;
