-- Campagnes bulletin d'option participation & intéressement

CREATE TABLE IF NOT EXISTS public.participation_simulations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    year integer NOT NULL CHECK (year >= 2020 AND year <= 2100),
    simulation_name text NOT NULL,
    benefice_net numeric(14, 2) NOT NULL DEFAULT 0,
    capitaux_propres numeric(14, 2) NOT NULL DEFAULT 0,
    salaires_bruts numeric(14, 2) NOT NULL DEFAULT 0,
    valeur_ajoutee numeric(14, 2) NOT NULL DEFAULT 0,
    participation_mode text NOT NULL DEFAULT 'salaire'
        CHECK (participation_mode IN ('uniforme', 'salaire', 'presence', 'combinaison')),
    participation_salaire_percent integer NOT NULL DEFAULT 50
        CHECK (participation_salaire_percent >= 0 AND participation_salaire_percent <= 100),
    participation_presence_percent integer NOT NULL DEFAULT 50
        CHECK (participation_presence_percent >= 0 AND participation_presence_percent <= 100),
    interessement_enabled boolean NOT NULL DEFAULT false,
    interessement_envelope numeric(14, 2),
    interessement_mode text
        CHECK (interessement_mode IS NULL OR interessement_mode IN ('uniforme', 'salaire', 'presence', 'combinaison')),
    interessement_salaire_percent integer NOT NULL DEFAULT 50
        CHECK (interessement_salaire_percent >= 0 AND interessement_salaire_percent <= 100),
    interessement_presence_percent integer NOT NULL DEFAULT 50
        CHECK (interessement_presence_percent >= 0 AND interessement_presence_percent <= 100),
    results_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    UNIQUE (company_id, year, simulation_name)
);

CREATE INDEX IF NOT EXISTS idx_participation_simulations_company_year
    ON public.participation_simulations(company_id, year DESC);

COMMENT ON TABLE public.participation_simulations IS
    'Simulations participation & intéressement (montants par salarié).';

CREATE TABLE IF NOT EXISTS public.participation_campaigns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    simulation_id uuid REFERENCES public.participation_simulations(id) ON DELETE SET NULL,
    year integer NOT NULL CHECK (year >= 2020 AND year <= 2100),
    exercise_label text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'open', 'closed')),
    payroll_year integer CHECK (payroll_year IS NULL OR (payroll_year >= 2020 AND payroll_year <= 2100)),
    payroll_month integer CHECK (payroll_month IS NULL OR (payroll_month >= 1 AND payroll_month <= 12)),
    sent_at timestamptz,
    deadline_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_participation_campaigns_company_year
    ON public.participation_campaigns(company_id, year DESC);

COMMENT ON TABLE public.participation_campaigns IS
    'Campagne bulletin d''option participation/intéressement par exercice.';

CREATE TABLE IF NOT EXISTS public.participation_campaign_advances (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES public.participation_campaigns(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    amount numeric(12, 2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    label text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (campaign_id, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_participation_campaign_advances_campaign
    ON public.participation_campaign_advances(campaign_id);

CREATE TABLE IF NOT EXISTS public.participation_bulletins (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES public.participation_campaigns(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    dispositif_type text NOT NULL
        CHECK (dispositif_type IN ('participation', 'interessement')),
    gross_amount numeric(12, 2) NOT NULL DEFAULT 0,
    csg_non_deductible numeric(12, 2) NOT NULL DEFAULT 0,
    csg_deductible numeric(12, 2) NOT NULL DEFAULT 0,
    advance_amount numeric(12, 2) NOT NULL DEFAULT 0,
    advance_label text NOT NULL DEFAULT '',
    net_amount numeric(12, 2) NOT NULL DEFAULT 0,
    generated_document_id uuid,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'responded', 'default_pee', 'cancelled')),
    choice_type text
        CHECK (choice_type IS NULL OR choice_type IN ('full_cash', 'partial_cash', 'full_pee')),
    choice_cash_amount numeric(12, 2),
    pee_amount numeric(12, 2),
    cash_amount numeric(12, 2),
    responded_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (campaign_id, employee_id, dispositif_type)
);

CREATE INDEX IF NOT EXISTS idx_participation_bulletins_campaign
    ON public.participation_bulletins(campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_participation_bulletins_employee
    ON public.participation_bulletins(employee_id, status);

COMMENT ON TABLE public.participation_bulletins IS
    'Bulletin d''option par salarié et dispositif (participation ou intéressement).';

ALTER TABLE public.monthly_inputs
    ADD COLUMN IF NOT EXISTS participation_campaign_id uuid
        REFERENCES public.participation_campaigns(id) ON DELETE SET NULL;
ALTER TABLE public.monthly_inputs
    ADD COLUMN IF NOT EXISTS participation_bulletin_id uuid
        REFERENCES public.participation_bulletins(id) ON DELETE SET NULL;

ALTER TABLE public.participation_simulations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.participation_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.participation_campaign_advances ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.participation_bulletins ENABLE ROW LEVEL SECURITY;

-- Lecture simulations / campagnes : accès entreprise
DROP POLICY IF EXISTS participation_simulations_select ON public.participation_simulations;
CREATE POLICY participation_simulations_select ON public.participation_simulations
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS participation_simulations_write ON public.participation_simulations;
CREATE POLICY participation_simulations_write ON public.participation_simulations
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid() AND uca.role IN ('admin', 'rh')
        )
    );

DROP POLICY IF EXISTS participation_campaigns_select ON public.participation_campaigns;
CREATE POLICY participation_campaigns_select ON public.participation_campaigns
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS participation_campaigns_write ON public.participation_campaigns;
CREATE POLICY participation_campaigns_write ON public.participation_campaigns
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid() AND uca.role IN ('admin', 'rh')
        )
    );

DROP POLICY IF EXISTS participation_campaign_advances_all ON public.participation_campaign_advances;
CREATE POLICY participation_campaign_advances_all ON public.participation_campaign_advances
    FOR ALL TO authenticated
    USING (
        campaign_id IN (
            SELECT pc.id FROM public.participation_campaigns pc
            JOIN public.user_company_accesses uca ON uca.company_id = pc.company_id
            WHERE uca.user_id = auth.uid() AND uca.role IN ('admin', 'rh')
        )
    );

DROP POLICY IF EXISTS participation_bulletins_select ON public.participation_bulletins;
CREATE POLICY participation_bulletins_select ON public.participation_bulletins
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
        OR employee_id IN (
            SELECT e.id FROM public.employees e
            WHERE e.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS participation_bulletins_write_rh ON public.participation_bulletins;
CREATE POLICY participation_bulletins_write_rh ON public.participation_bulletins
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid() AND uca.role IN ('admin', 'rh')
        )
    );

DROP POLICY IF EXISTS participation_bulletins_update_employee ON public.participation_bulletins;
CREATE POLICY participation_bulletins_update_employee ON public.participation_bulletins
    FOR UPDATE TO authenticated
    USING (
        status = 'sent'
        AND employee_id IN (
            SELECT e.id FROM public.employees e
            WHERE e.user_id = auth.uid()
        )
    )
    WITH CHECK (
        employee_id IN (
            SELECT e.id FROM public.employees e
            WHERE e.user_id = auth.uid()
        )
    );
