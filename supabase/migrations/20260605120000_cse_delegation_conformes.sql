-- =============================================================================
-- Module CSE — heures de délégation conformes (config, transfers, requests, champs)
-- Migration additive.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Config délégation par entreprise (effectif figé à la date des élections)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cse_delegation_config (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
    reference_headcount integer NOT NULL CHECK (reference_headcount >= 0),
    reference_date date NOT NULL,
    report_enabled boolean NOT NULL DEFAULT TRUE,
    mutualisation_enabled boolean NOT NULL DEFAULT TRUE,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT cse_delegation_config_company_unique UNIQUE (company_id)
);

COMMENT ON TABLE public.cse_delegation_config IS
    'Effectif de référence figé et options report/mutualisation pour les heures de délégation CSE.';

CREATE INDEX IF NOT EXISTS idx_cse_delegation_config_company
    ON public.cse_delegation_config (company_id);

-- -----------------------------------------------------------------------------
-- 2. Override crédit par mandat (accord/PAP plus favorable)
-- -----------------------------------------------------------------------------
ALTER TABLE public.cse_elected_members
    ADD COLUMN IF NOT EXISTS monthly_hours_override numeric;

COMMENT ON COLUMN public.cse_elected_members.monthly_hours_override IS
    'Crédit mensuel conventionnel plus favorable (prioritaire sur le barème légal R. 2314-1).';

-- -----------------------------------------------------------------------------
-- 3. Enrichissement heures consommées (source + mois d''origine report)
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cse_delegation_hour_source') THEN
        CREATE TYPE public.cse_delegation_hour_source AS ENUM (
            'propre',
            'reportee',
            'mutualisee',
            'exceptionnelle'
        );
    END IF;
END
$$;

ALTER TABLE public.cse_delegation_hours
    ADD COLUMN IF NOT EXISTS source public.cse_delegation_hour_source NOT NULL DEFAULT 'propre';

ALTER TABLE public.cse_delegation_hours
    ADD COLUMN IF NOT EXISTS origin_month date;

COMMENT ON COLUMN public.cse_delegation_hours.source IS
    'Origine de l''heure : propre, reportée, mutualisée ou exceptionnelle.';

COMMENT ON COLUMN public.cse_delegation_hours.origin_month IS
    'Mois d''origine pour les heures reportées.';

-- -----------------------------------------------------------------------------
-- 4. Mutualisation entre élus (art. L. 2315-9 / R. 2315-6)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cse_delegation_transfers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
    period_year integer NOT NULL CHECK (period_year >= 2000),
    period_month integer NOT NULL CHECK (period_month BETWEEN 1 AND 12),
    from_employee_id uuid NOT NULL REFERENCES public.employees (id) ON DELETE CASCADE,
    to_employee_id uuid NOT NULL REFERENCES public.employees (id) ON DELETE CASCADE,
    hours numeric NOT NULL CHECK (hours > 0),
    employer_notified_at date,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT cse_delegation_transfers_distinct_employees CHECK (from_employee_id <> to_employee_id)
);

CREATE INDEX IF NOT EXISTS idx_cse_delegation_transfers_company
    ON public.cse_delegation_transfers (company_id);

CREATE INDEX IF NOT EXISTS idx_cse_delegation_transfers_period
    ON public.cse_delegation_transfers (company_id, period_year, period_month);

CREATE INDEX IF NOT EXISTS idx_cse_delegation_transfers_from
    ON public.cse_delegation_transfers (from_employee_id);

CREATE INDEX IF NOT EXISTS idx_cse_delegation_transfers_to
    ON public.cse_delegation_transfers (to_employee_id);

-- -----------------------------------------------------------------------------
-- 5. Bons de délégation (prévu / réalisé — L4)
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cse_delegation_request_status') THEN
        CREATE TYPE public.cse_delegation_request_status AS ENUM (
            'planifie',
            'realise',
            'annule'
        );
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.cse_delegation_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees (id) ON DELETE CASCADE,
    planned_date date NOT NULL,
    planned_hours numeric NOT NULL CHECK (planned_hours > 0),
    reason text NOT NULL,
    status public.cse_delegation_request_status NOT NULL DEFAULT 'planifie',
    realized_hours numeric CHECK (realized_hours IS NULL OR realized_hours >= 0),
    employer_notified_at date,
    delegation_hour_id uuid REFERENCES public.cse_delegation_hours (id) ON DELETE SET NULL,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cse_delegation_requests_company
    ON public.cse_delegation_requests (company_id);

CREATE INDEX IF NOT EXISTS idx_cse_delegation_requests_employee
    ON public.cse_delegation_requests (employee_id, planned_date);

-- -----------------------------------------------------------------------------
-- 6. Imputation paie (L5) — lien heures délégation → bulletin
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cse_delegation_payroll_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees (id) ON DELETE CASCADE,
    delegation_hour_id uuid REFERENCES public.cse_delegation_hours (id) ON DELETE SET NULL,
    year integer NOT NULL,
    month integer NOT NULL CHECK (month BETWEEN 1 AND 12),
    hours numeric NOT NULL CHECK (hours > 0),
    is_overrun boolean NOT NULL DEFAULT FALSE,
    rubrique_code text NOT NULL DEFAULT 'DELEGATION_CSE',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cse_delegation_payroll_company_period
    ON public.cse_delegation_payroll_entries (company_id, year, month);

-- -----------------------------------------------------------------------------
-- 7. Triggers updated_at
-- -----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS cse_delegation_config_set_updated_at ON public.cse_delegation_config;

CREATE TRIGGER cse_delegation_config_set_updated_at
    BEFORE UPDATE ON public.cse_delegation_config
    FOR EACH ROW
    EXECUTE PROCEDURE public.set_updated_at ();

DROP TRIGGER IF EXISTS cse_delegation_requests_set_updated_at ON public.cse_delegation_requests;

CREATE TRIGGER cse_delegation_requests_set_updated_at
    BEFORE UPDATE ON public.cse_delegation_requests
    FOR EACH ROW
    EXECUTE PROCEDURE public.set_updated_at ();

-- -----------------------------------------------------------------------------
-- 8. RLS
-- -----------------------------------------------------------------------------
ALTER TABLE public.cse_delegation_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cse_delegation_transfers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cse_delegation_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cse_delegation_payroll_entries ENABLE ROW LEVEL SECURITY;

-- Helper pattern : accès entreprise via user_company_accesses ou fiche employé
CREATE POLICY cse_delegation_config_select ON public.cse_delegation_config
    FOR SELECT TO authenticated
    USING ((
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid())
        OR company_id IN (
            SELECT e.company_id FROM public.employees e WHERE e.id = auth.uid())));

CREATE POLICY cse_delegation_config_write ON public.cse_delegation_config
    FOR ALL TO authenticated
    USING (company_id IN (
        SELECT uca.company_id FROM public.user_company_accesses uca
        WHERE uca.user_id = auth.uid()))
    WITH CHECK (company_id IN (
        SELECT uca.company_id FROM public.user_company_accesses uca
        WHERE uca.user_id = auth.uid()));

CREATE POLICY cse_delegation_transfers_select ON public.cse_delegation_transfers
    FOR SELECT TO authenticated
    USING ((
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid())
        OR company_id IN (
            SELECT e.company_id FROM public.employees e WHERE e.id = auth.uid())));

CREATE POLICY cse_delegation_transfers_write ON public.cse_delegation_transfers
    FOR ALL TO authenticated
    USING (company_id IN (
        SELECT uca.company_id FROM public.user_company_accesses uca
        WHERE uca.user_id = auth.uid()))
    WITH CHECK (company_id IN (
        SELECT uca.company_id FROM public.user_company_accesses uca
        WHERE uca.user_id = auth.uid()));

CREATE POLICY cse_delegation_requests_select ON public.cse_delegation_requests
    FOR SELECT TO authenticated
    USING ((
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid())
        OR employee_id = auth.uid()));

CREATE POLICY cse_delegation_requests_write ON public.cse_delegation_requests
    FOR ALL TO authenticated
    USING ((
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid())
        OR employee_id = auth.uid()))
    WITH CHECK ((
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid())
        OR employee_id = auth.uid()));

CREATE POLICY cse_delegation_payroll_select ON public.cse_delegation_payroll_entries
    FOR SELECT TO authenticated
    USING (company_id IN (
        SELECT uca.company_id FROM public.user_company_accesses uca
        WHERE uca.user_id = auth.uid()));

CREATE POLICY cse_delegation_payroll_write ON public.cse_delegation_payroll_entries
    FOR ALL TO authenticated
    USING (company_id IN (
        SELECT uca.company_id FROM public.user_company_accesses uca
        WHERE uca.user_id = auth.uid()))
    WITH CHECK (company_id IN (
        SELECT uca.company_id FROM public.user_company_accesses uca
        WHERE uca.user_id = auth.uid()));
