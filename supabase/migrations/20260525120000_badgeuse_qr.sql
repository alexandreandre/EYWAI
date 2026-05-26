-- Badgeuse : pointages, validations, credentials QR signés.

CREATE TABLE IF NOT EXISTS public.employee_time_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id uuid NOT NULL,
    company_id uuid NOT NULL,
    timestamp timestamptz NOT NULL DEFAULT now(),
    event_type text NOT NULL CHECK (event_type IN ('ENTREE', 'SORTIE')),
    source text NOT NULL DEFAULT 'EMPLOYE'
        CHECK (source IN ('EMPLOYE', 'RH', 'QR_SCAN')),
    created_by uuid,
    updated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employee_time_entries_company_employee_ts
    ON public.employee_time_entries (company_id, employee_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_employee_time_entries_company_ts
    ON public.employee_time_entries (company_id, timestamp);

CREATE TABLE IF NOT EXISTS public.employee_time_entries_validations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id uuid NOT NULL,
    company_id uuid NOT NULL,
    day date NOT NULL,
    validated_by uuid NOT NULL,
    validated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (employee_id, company_id, day)
);

CREATE INDEX IF NOT EXISTS idx_employee_time_entries_validations_company_day
    ON public.employee_time_entries_validations (company_id, day);

CREATE TABLE IF NOT EXISTS public.employee_badge_credentials (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id uuid NOT NULL,
    company_id uuid NOT NULL,
    token_version integer NOT NULL DEFAULT 1,
    secret_salt uuid NOT NULL DEFAULT gen_random_uuid(),
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (employee_id, company_id)
);

CREATE INDEX IF NOT EXISTS idx_employee_badge_credentials_company
    ON public.employee_badge_credentials (company_id)
    WHERE revoked_at IS NULL;

-- Étendre la contrainte source si la table existait déjà sans QR_SCAN
ALTER TABLE public.employee_time_entries
    DROP CONSTRAINT IF EXISTS employee_time_entries_source_check;

ALTER TABLE public.employee_time_entries
    ADD CONSTRAINT employee_time_entries_source_check
    CHECK (source IN ('EMPLOYE', 'RH', 'QR_SCAN'));

-- -----------------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------------
ALTER TABLE public.employee_time_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_time_entries_validations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_badge_credentials ENABLE ROW LEVEL SECURITY;

CREATE POLICY employee_time_entries_select ON public.employee_time_entries
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
        OR employee_id = auth.uid()
    );

CREATE POLICY employee_time_entries_insert ON public.employee_time_entries
    FOR INSERT TO authenticated
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
        OR employee_id = auth.uid()
    );

CREATE POLICY employee_time_entries_update ON public.employee_time_entries
    FOR UPDATE TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

CREATE POLICY employee_time_entries_delete ON public.employee_time_entries
    FOR DELETE TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

CREATE POLICY employee_time_entries_validations_select ON public.employee_time_entries_validations
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
        OR employee_id = auth.uid()
    );

CREATE POLICY employee_time_entries_validations_write ON public.employee_time_entries_validations
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

CREATE POLICY employee_badge_credentials_select ON public.employee_badge_credentials
    FOR SELECT TO authenticated
    USING (
        employee_id = auth.uid()
        OR company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

CREATE POLICY employee_badge_credentials_write ON public.employee_badge_credentials
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
