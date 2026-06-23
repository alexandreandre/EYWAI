-- Statut CSE par entreprise (carence électorale, élus, obligation).
-- Complète le module CSE : archivage PV carence (Cerfa 15248) sans parser OCR.

CREATE TABLE IF NOT EXISTS public.company_cse_settings (
    company_id uuid PRIMARY KEY REFERENCES public.companies(id) ON DELETE CASCADE,
    cse_status text NOT NULL DEFAULT 'unknown'
        CHECK (cse_status IN ('unknown', 'not_required', 'obligation_pending', 'carence', 'elected')),
    carence_pv_document_id uuid REFERENCES public.cse_bdes_documents(id) ON DELETE SET NULL,
    carence_valid_until date,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_cse_settings IS
    'Paramétrage statut CSE entreprise (carence électorale, élus actifs, obligation légale).';

COMMENT ON COLUMN public.company_cse_settings.cse_status IS
    'unknown = non renseigné ; not_required = effectif < 11 ; carence = PV carence valide ; elected = CSE en place.';

ALTER TABLE public.company_cse_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_cse_settings_select ON public.company_cse_settings;
CREATE POLICY company_cse_settings_select ON public.company_cse_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_cse_settings_write ON public.company_cse_settings;
CREATE POLICY company_cse_settings_write ON public.company_cse_settings
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
