-- Relecture IA des bulletins d'un mois : les relectures, le résultat par bulletin,
-- les points marqués « vu, c'est normal » et les règles de chaque société.
-- Aucune lecture directe depuis le navigateur : RLS active sans politique, seul
-- le serveur (service_role) y accède. Aucune clé étrangère vers payslips : une
-- relecture ne doit jamais gêner une régénération ni une suppression de bulletin.

CREATE TABLE IF NOT EXISTS public.relectures_ia (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    year integer NOT NULL,
    month integer NOT NULL CHECK (month BETWEEN 1 AND 12),
    company_ids uuid[] NOT NULL,
    statut text NOT NULL DEFAULT 'en_cours'
        CHECK (statut IN ('en_cours', 'terminee', 'echec')),
    total integer NOT NULL DEFAULT 0,
    traites integer NOT NULL DEFAULT 0,
    echecs integer NOT NULL DEFAULT 0,
    points integer NOT NULL DEFAULT 0,
    lance_par uuid,
    cout_estime_eur numeric(10, 2),
    cout_reel_usd numeric(10, 4),
    message text,
    battement_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    termine_at timestamptz
);

-- Une seule relecture à la fois.
CREATE UNIQUE INDEX IF NOT EXISTS relectures_ia_une_seule_en_cours
    ON public.relectures_ia ((true))
    WHERE statut = 'en_cours';

CREATE INDEX IF NOT EXISTS relectures_ia_mois_idx
    ON public.relectures_ia (year, month, created_at DESC);

CREATE TABLE IF NOT EXISTS public.relectures_ia_bulletins (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    relecture_id uuid NOT NULL REFERENCES public.relectures_ia(id) ON DELETE CASCADE,
    payslip_id uuid NOT NULL,
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    year integer NOT NULL,
    month integer NOT NULL CHECK (month BETWEEN 1 AND 12),
    contract_period_id uuid,
    payslip_updated_at timestamptz,
    statut text NOT NULL DEFAULT 'a_faire'
        CHECK (statut IN ('a_faire', 'fait', 'echec')),
    signalements jsonb NOT NULL DEFAULT '[]'::jsonb,
    ecartes jsonb NOT NULL DEFAULT '{}'::jsonb,
    cout_usd numeric(10, 6),
    message text,
    termine_at timestamptz,
    CONSTRAINT relectures_ia_bulletins_unique UNIQUE (relecture_id, payslip_id)
);

CREATE INDEX IF NOT EXISTS relectures_ia_bulletins_relecture_idx
    ON public.relectures_ia_bulletins (relecture_id, statut);

CREATE INDEX IF NOT EXISTS relectures_ia_bulletins_mois_idx
    ON public.relectures_ia_bulletins (company_id, year, month, statut);

CREATE TABLE IF NOT EXISTS public.relectures_ia_vus (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    ligne_normalisee text NOT NULL,
    ligne text NOT NULL,
    raison text,
    year integer,
    month integer,
    vu_par uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT relectures_ia_vus_unique UNIQUE (company_id, employee_id, ligne_normalisee)
);

CREATE TABLE IF NOT EXISTS public.relecture_ia_regles (
    company_id uuid PRIMARY KEY REFERENCES public.companies(id) ON DELETE CASCADE,
    texte text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.relectures_ia IS
    'Relecture IA de la paie d''un mois : une seule en cours, avancement et battement pour la reprise.';
COMMENT ON TABLE public.relectures_ia_bulletins IS
    'Résultat de la relecture d''un bulletin. payslip_updated_at : la version relue.';
COMMENT ON TABLE public.relectures_ia_vus IS
    'Points marqués « vu, c''est normal » : retenus d''un mois sur l''autre, par salarié et ligne.';
COMMENT ON TABLE public.relecture_ia_regles IS
    'Texte des règles de chaque société envoyé à l''IA. Hors dépôt public.';

ALTER TABLE public.relectures_ia ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relectures_ia_bulletins ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relectures_ia_vus ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relecture_ia_regles ENABLE ROW LEVEL SECURITY;
