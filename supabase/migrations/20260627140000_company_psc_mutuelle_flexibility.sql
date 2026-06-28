-- Paramètres PSC entreprise + enrichissement catalogue mutuelle (organisme, note).

ALTER TABLE public.company_mutuelle_types
    ADD COLUMN IF NOT EXISTS organisme_label text;

ALTER TABLE public.company_mutuelle_types
    ADD COLUMN IF NOT EXISTS note text;

COMMENT ON COLUMN public.company_mutuelle_types.organisme_label IS
    'Nom affiché de l''organisme (ex. APICIL). Prioritaire sur le libellé entreprise si renseigné.';

COMMENT ON COLUMN public.company_mutuelle_types.note IS
    'Note d''aide affichée lors de la sélection de formule (optionnel).';

CREATE TABLE IF NOT EXISTS public.company_psc_settings (
    company_id uuid PRIMARY KEY REFERENCES public.companies(id) ON DELETE CASCADE,
    mutuelle_organisme_label text,
    mutuelle_employee_self_service boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_psc_settings IS
    'Paramètres protection sociale complémentaire (mutuelle / prévoyance) par entreprise.';

ALTER TABLE public.company_psc_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_psc_settings_select ON public.company_psc_settings;
CREATE POLICY company_psc_settings_select ON public.company_psc_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_psc_settings_write ON public.company_psc_settings;
CREATE POLICY company_psc_settings_write ON public.company_psc_settings
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
