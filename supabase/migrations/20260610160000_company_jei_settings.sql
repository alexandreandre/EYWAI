-- Paramétrage JEI par entreprise (statut, date de création établissement, taux d'exonération).

CREATE TABLE IF NOT EXISTS public.company_jei_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    jei_enabled boolean NOT NULL DEFAULT false,
    date_creation_etablissement date,
    taux_exoneration numeric(5, 4) NOT NULL DEFAULT 1.0
        CHECK (taux_exoneration >= 0 AND taux_exoneration <= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_jei_settings IS
    'Paramétrage du statut Jeune Entreprise Innovante (JEI) par entreprise.';
COMMENT ON COLUMN public.company_jei_settings.date_creation_etablissement IS
    'Date de création de l''établissement — sert au calcul de la fenêtre d''éligibilité (7 ans).';
COMMENT ON COLUMN public.company_jei_settings.taux_exoneration IS
    'Taux d''exonération appliqué (1.0 = 100 %, réservé au régime dégressif legacy).';

ALTER TABLE public.company_jei_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_jei_settings_select ON public.company_jei_settings;
CREATE POLICY company_jei_settings_select ON public.company_jei_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_jei_settings_write ON public.company_jei_settings;
CREATE POLICY company_jei_settings_write ON public.company_jei_settings
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );
