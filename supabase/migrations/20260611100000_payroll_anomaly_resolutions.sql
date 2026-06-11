-- Résolutions RH sur anomalies pré-paie et trace des acquittements de lancement

CREATE TABLE IF NOT EXISTS public.payroll_anomaly_resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    year INT NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month INT NOT NULL CHECK (month >= 1 AND month <= 12),
    anomaly_type TEXT NOT NULL CHECK (
        anomaly_type IN ('ecart_heures', 'heures_non_saisies', 'pointage', 'conflit_absence')
    ),
    status TEXT NOT NULL CHECK (status IN ('justifie', 'resolu')),
    motif TEXT NOT NULL CHECK (
        motif IN ('directeur_site', 'heures_sup', 'erreur_pointage_corrigee', 'autre')
    ),
    commentaire TEXT,
    resolved_by UUID NOT NULL REFERENCES auth.users(id),
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, employee_id, year, month, anomaly_type)
);

CREATE INDEX IF NOT EXISTS payroll_anomaly_resolutions_company_period_idx
    ON public.payroll_anomaly_resolutions (company_id, year, month);

CREATE TABLE IF NOT EXISTS public.payroll_preflight_acknowledgements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    year INT NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month INT NOT NULL CHECK (month >= 1 AND month <= 12),
    open_anomalies_count INT NOT NULL DEFAULT 0 CHECK (open_anomalies_count >= 0),
    anomaly_types_summary TEXT[] NOT NULL DEFAULT '{}',
    commentaire TEXT,
    acknowledged_by UUID NOT NULL REFERENCES auth.users(id),
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS payroll_preflight_acknowledgements_company_period_idx
    ON public.payroll_preflight_acknowledgements (company_id, year, month);

ALTER TABLE public.payroll_anomaly_resolutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payroll_preflight_acknowledgements ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS payroll_anomaly_resolutions_select ON public.payroll_anomaly_resolutions;
CREATE POLICY payroll_anomaly_resolutions_select ON public.payroll_anomaly_resolutions
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS payroll_anomaly_resolutions_write ON public.payroll_anomaly_resolutions;
CREATE POLICY payroll_anomaly_resolutions_write ON public.payroll_anomaly_resolutions
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

DROP POLICY IF EXISTS payroll_preflight_acknowledgements_select ON public.payroll_preflight_acknowledgements;
CREATE POLICY payroll_preflight_acknowledgements_select ON public.payroll_preflight_acknowledgements
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS payroll_preflight_acknowledgements_write ON public.payroll_preflight_acknowledgements;
CREATE POLICY payroll_preflight_acknowledgements_write ON public.payroll_preflight_acknowledgements
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
