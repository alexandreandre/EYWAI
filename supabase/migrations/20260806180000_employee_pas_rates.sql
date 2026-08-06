-- Historique daté des taux de prélèvement à la source.
--
-- Jusqu'ici le taux vivait uniquement dans employees.specificites_paie, sans
-- date de validité : impossible de savoir de quel mois il venait, et certains
-- salariés mélangeaient des champs issus de mois différents. Cette table garde
-- la trace de chaque taux reçu, avec sa période d'origine et le fichier dont il
-- provient. specificites_paie continue de porter le taux courant, seul champ lu
-- par le moteur de paie.

CREATE TABLE IF NOT EXISTS public.employee_pas_rates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,

    periode text NOT NULL,
    taux numeric(5, 2) NOT NULL,
    type_taux text,
    identifiant_taux text,

    source text NOT NULL,
    source_fichier text,

    applied_at timestamptz NOT NULL DEFAULT now(),
    applied_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,

    CONSTRAINT employee_pas_rates_periode_format
        CHECK (periode ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    CONSTRAINT employee_pas_rates_taux_range
        CHECK (taux >= 0 AND taux <= 100),
    CONSTRAINT employee_pas_rates_source_check
        CHECK (source IN ('dsn', 'crm', 'manuel'))
);

COMMENT ON TABLE public.employee_pas_rates IS
    'Taux de prélèvement à la source reçus, datés de leur période d''origine.';

COMMENT ON COLUMN public.employee_pas_rates.periode IS
    'Période du fichier d''où vient le taux (AAAA-MM), pas la date du dépôt.';

COMMENT ON COLUMN public.employee_pas_rates.type_taux IS
    'Nomenclature DSN S21.G00.50.007 : 01 taux personnalisé transmis par la DGFiP, 13 taux barème appliqué faute de taux personnalisé.';

COMMENT ON COLUMN public.employee_pas_rates.source IS
    'dsn : DSN mensuelle. crm : compte rendu métier net-entreprises. manuel : saisie RH.';

-- Redéposer le même fichier ne doit rien dupliquer.
CREATE UNIQUE INDEX IF NOT EXISTS employee_pas_rates_unique_periode
    ON public.employee_pas_rates (employee_id, periode, source);

CREATE INDEX IF NOT EXISTS employee_pas_rates_company_periode
    ON public.employee_pas_rates (company_id, periode DESC);

ALTER TABLE public.employee_pas_rates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS employee_pas_rates_select ON public.employee_pas_rates;
CREATE POLICY employee_pas_rates_select ON public.employee_pas_rates
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

-- Écriture réservée au backend (service_role) : pas de policy INSERT/UPDATE client.
