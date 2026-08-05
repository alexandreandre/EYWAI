-- Suivi des périodes d'essai. Remplace employees.periode_essai (jsonb), vide
-- sur les 241 salariés actifs : rien à reprendre.
--
-- end_date est une colonne réelle et non générée : le calcul relève du droit
-- du travail (veille du quantième, dernier jour du mois quand le quantième
-- n'existe pas, prolongation par renouvellement) et vit dans le domaine
-- Python, où il se teste cas par cas.

CREATE TABLE IF NOT EXISTS public.trial_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,

    start_date date NOT NULL,
    duration_value integer NOT NULL,
    duration_unit text NOT NULL DEFAULT 'mois',
    renewal_allowed boolean NOT NULL DEFAULT false,

    renewed_at date,
    renewal_duration_value integer,
    renewal_duration_unit text,
    renewed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,

    end_date date NOT NULL,
    status text NOT NULL DEFAULT 'en_cours',

    confirmed_at timestamptz,
    confirmed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,

    CONSTRAINT trial_periods_duration_positive CHECK (duration_value > 0),
    CONSTRAINT trial_periods_duration_unit_check
        CHECK (duration_unit IN ('jours', 'semaines', 'mois')),
    CONSTRAINT trial_periods_renewal_unit_check
        CHECK (renewal_duration_unit IS NULL
               OR renewal_duration_unit IN ('jours', 'semaines', 'mois')),
    CONSTRAINT trial_periods_renewal_positive
        CHECK (renewal_duration_value IS NULL OR renewal_duration_value > 0),
    CONSTRAINT trial_periods_renewal_complete
        CHECK (num_nulls(renewed_at, renewal_duration_value, renewal_duration_unit) IN (0, 3)),
    CONSTRAINT trial_periods_status_check
        CHECK (status IN ('en_cours', 'confirmee', 'rompue')),
    CONSTRAINT trial_periods_end_after_start CHECK (end_date >= start_date)
);

COMMENT ON TABLE public.trial_periods IS
    'Périodes d''essai : paramétrage, renouvellement effectif et issue.';

COMMENT ON COLUMN public.trial_periods.start_date IS
    'Début de la période, initialisé à la date d''entrée mais modifiable : un contrat peut débuter après l''embauche déclarée.';

COMMENT ON COLUMN public.trial_periods.end_date IS
    'Dernier jour inclus, calculé côté backend. Une rupture notifiée après cette date est hors période d''essai.';

COMMENT ON COLUMN public.trial_periods.renewal_allowed IS
    'Le renouvellement est-il ouvert par la convention : une possibilité, pas une décision.';

COMMENT ON COLUMN public.trial_periods.renewed_at IS
    'Date de la décision de renouvellement, qui doit être notifiée avant le terme initial.';

COMMENT ON COLUMN public.trial_periods.status IS
    'rompue est écrit par le module des sorties (type fin_periode_essai).';

-- Une seule période active par salarié ; une réembauche crée la sienne.
CREATE UNIQUE INDEX IF NOT EXISTS trial_periods_one_active_per_employee
    ON public.trial_periods (employee_id)
    WHERE status = 'en_cours';

CREATE INDEX IF NOT EXISTS trial_periods_company_status_end
    ON public.trial_periods (company_id, status, end_date);

ALTER TABLE public.trial_periods ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS trial_periods_select ON public.trial_periods;
CREATE POLICY trial_periods_select ON public.trial_periods
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

-- Écriture réservée au backend (service_role) : pas de policy INSERT/UPDATE client.
