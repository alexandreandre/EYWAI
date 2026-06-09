-- Terminaux badgeuse kiosque (jeton dédié, indépendant de la session RH).

CREATE TABLE IF NOT EXISTS public.badgeuse_terminal_devices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    label text NOT NULL,
    token_hash text NOT NULL UNIQUE,
    token_prefix text NOT NULL,
    created_by uuid NOT NULL,
    last_used_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_badgeuse_terminal_devices_company_active
    ON public.badgeuse_terminal_devices (company_id)
    WHERE revoked_at IS NULL;

ALTER TABLE public.employee_time_entries
    ADD COLUMN IF NOT EXISTS terminal_device_id uuid
        REFERENCES public.badgeuse_terminal_devices(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_employee_time_entries_terminal_device
    ON public.employee_time_entries (terminal_device_id)
    WHERE terminal_device_id IS NOT NULL;

ALTER TABLE public.badgeuse_terminal_devices ENABLE ROW LEVEL SECURITY;

CREATE POLICY badgeuse_terminal_devices_select ON public.badgeuse_terminal_devices
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

CREATE POLICY badgeuse_terminal_devices_write ON public.badgeuse_terminal_devices
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
