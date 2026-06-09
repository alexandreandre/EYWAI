-- Profils BOETH salariés et historique des changements de statut.

CREATE TABLE IF NOT EXISTS public.employee_boeth_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    boeth_code text NOT NULL CHECK (boeth_code IN (
        '01', '02', '03', '04', '05', '06', '07', '08', '09', '11', '12'
    )),
    valid_from date NOT NULL,
    valid_to date,
    document_type text,
    document_expires_at date,
    notes text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT employee_boeth_profiles_valid_range CHECK (
        valid_to IS NULL OR valid_to >= valid_from
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS employee_boeth_profiles_active_unique
    ON public.employee_boeth_profiles (employee_id)
    WHERE is_active = true;

CREATE INDEX IF NOT EXISTS employee_boeth_profiles_company_idx
    ON public.employee_boeth_profiles (company_id);

COMMENT ON TABLE public.employee_boeth_profiles IS
    'Statut BOETH actif ou historique par salarié (DSN S21.G00.40.072).';

CREATE TABLE IF NOT EXISTS public.employee_boeth_status_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    previous_boeth_code text,
    new_boeth_code text,
    changed_at date NOT NULL DEFAULT CURRENT_DATE,
    changed_in_period text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS employee_boeth_status_history_employee_idx
    ON public.employee_boeth_status_history (employee_id, changed_at DESC);

ALTER TABLE public.employee_boeth_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_boeth_status_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS employee_boeth_profiles_select ON public.employee_boeth_profiles;
CREATE POLICY employee_boeth_profiles_select ON public.employee_boeth_profiles
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_boeth_profiles_write ON public.employee_boeth_profiles;
CREATE POLICY employee_boeth_profiles_write ON public.employee_boeth_profiles
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

DROP POLICY IF EXISTS employee_boeth_status_history_select ON public.employee_boeth_status_history;
CREATE POLICY employee_boeth_status_history_select ON public.employee_boeth_status_history
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_boeth_status_history_write ON public.employee_boeth_status_history;
CREATE POLICY employee_boeth_status_history_write ON public.employee_boeth_status_history
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
