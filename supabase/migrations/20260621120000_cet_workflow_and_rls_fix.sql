-- CET workflow manager + correction RLS deposit_cp + extension validation_mode.

ALTER TABLE public.employee_cet_movements
    ADD COLUMN IF NOT EXISTS workflow_step text NOT NULL DEFAULT 'pending'
        CHECK (workflow_step IN (
            'pending',
            'pending_manager',
            'approved_manager',
            'rejected_manager',
            'approved_rh',
            'rejected_rh'
        )),
    ADD COLUMN IF NOT EXISTS manager_id uuid REFERENCES public.employees(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS manager_approved_at timestamptz,
    ADD COLUMN IF NOT EXISTS manager_rejected_at timestamptz,
    ADD COLUMN IF NOT EXISTS manager_rejection_reason text;

COMMENT ON COLUMN public.employee_cet_movements.workflow_step IS
    'Circuit validation CET : manager puis RH selon company_cet_settings.validation_mode.';

CREATE INDEX IF NOT EXISTS idx_employee_cet_movements_company_workflow
    ON public.employee_cet_movements (company_id, workflow_step)
    WHERE status = 'pending';

-- Backfill workflow_step depuis status existant
UPDATE public.employee_cet_movements
SET workflow_step = CASE
    WHEN status = 'pending' THEN 'pending'
    WHEN status = 'rejected' THEN 'rejected_rh'
    WHEN status IN ('validated', 'applied_payroll') THEN 'approved_rh'
    ELSE workflow_step
END
WHERE workflow_step = 'pending' AND status <> 'pending';

-- Extension validation_mode
ALTER TABLE public.company_cet_settings
    DROP CONSTRAINT IF EXISTS company_cet_settings_validation_mode_check;

ALTER TABLE public.company_cet_settings
    ADD CONSTRAINT company_cet_settings_validation_mode_check
    CHECK (validation_mode IN ('auto', 'rh', 'manager', 'manager_then_rh'));

-- RLS : inclure deposit_cp pour les employés
DROP POLICY IF EXISTS employee_cet_movements_write ON public.employee_cet_movements;

CREATE POLICY employee_cet_movements_write ON public.employee_cet_movements
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
        OR (
            employee_id IN (
                SELECT e.id FROM public.employees e
                WHERE e.user_id = auth.uid()
            )
            AND status = 'pending'
            AND movement_type IN ('deposit_hs', 'deposit_cp', 'withdraw_rest')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
        OR (
            employee_id IN (
                SELECT e.id FROM public.employees e
                WHERE e.user_id = auth.uid()
            )
            AND status = 'pending'
            AND movement_type IN ('deposit_hs', 'deposit_cp', 'withdraw_rest')
        )
    );
