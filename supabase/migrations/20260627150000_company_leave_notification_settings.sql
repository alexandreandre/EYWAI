CREATE TABLE IF NOT EXISTS public.company_leave_notification_settings (
    company_id uuid PRIMARY KEY REFERENCES public.companies(id) ON DELETE CASCADE,
    enabled boolean NOT NULL DEFAULT false,
    notify_on_employee_request boolean NOT NULL DEFAULT true,
    notify_after_manager_approval boolean NOT NULL DEFAULT true,
    recipient_roles text[] NOT NULL DEFAULT ARRAY['rh', 'admin']::text[],
    extra_recipient_emails text[] NOT NULL DEFAULT ARRAY[]::text[],
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by uuid NULL
);

COMMENT ON TABLE public.company_leave_notification_settings IS
    'Paramètres entreprise pour les emails envoyés aux RH lors des demandes de congés/absences.';

ALTER TABLE public.company_leave_notification_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_leave_notification_settings_select
    ON public.company_leave_notification_settings;
CREATE POLICY company_leave_notification_settings_select
ON public.company_leave_notification_settings
FOR SELECT
USING (
    EXISTS (
        SELECT 1
        FROM public.user_company_accesses uca
        WHERE uca.company_id = company_leave_notification_settings.company_id
          AND uca.user_id = auth.uid()
          AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
    )
);

DROP POLICY IF EXISTS company_leave_notification_settings_write
    ON public.company_leave_notification_settings;
CREATE POLICY company_leave_notification_settings_write
ON public.company_leave_notification_settings
FOR ALL
USING (
    EXISTS (
        SELECT 1
        FROM public.user_company_accesses uca
        WHERE uca.company_id = company_leave_notification_settings.company_id
          AND uca.user_id = auth.uid()
          AND uca.role IN ('admin', 'rh')
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.user_company_accesses uca
        WHERE uca.company_id = company_leave_notification_settings.company_id
          AND uca.user_id = auth.uid()
          AND uca.role IN ('admin', 'rh')
    )
);
