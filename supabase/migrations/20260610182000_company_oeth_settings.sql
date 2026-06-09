-- Paramétrage OETH par entreprise.

CREATE TABLE IF NOT EXISTS public.company_oeth_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    oeth_assujetti_override boolean,
    date_franchissement_seuil_20 date,
    accord_agree_code text,
    accord_agree_valid_from date,
    accord_agree_valid_to date,
    declaring_establishment_siret text,
    departement text,
    taux_obligation numeric(5, 4) NOT NULL DEFAULT 0.06
        CHECK (taux_obligation > 0 AND taux_obligation <= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_oeth_settings IS
    'Paramétrage OETH entreprise : assujettissement, accord agréé, établissement déclarant.';

ALTER TABLE public.company_oeth_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_oeth_settings_select ON public.company_oeth_settings;
CREATE POLICY company_oeth_settings_select ON public.company_oeth_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_oeth_settings_write ON public.company_oeth_settings;
CREATE POLICY company_oeth_settings_write ON public.company_oeth_settings
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
