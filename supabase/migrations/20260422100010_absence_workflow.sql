-- Workflow validation absences : manager → RH
ALTER TABLE public.absence_requests
    ADD COLUMN IF NOT EXISTS manager_id uuid,
    ADD COLUMN IF NOT EXISTS manager_approved_at timestamptz,
    ADD COLUMN IF NOT EXISTS manager_rejected_at timestamptz,
    ADD COLUMN IF NOT EXISTS manager_rejection_reason text,
    ADD COLUMN IF NOT EXISTS workflow_step text DEFAULT 'pending'
        CHECK (workflow_step IN (
            'pending',
            'pending_manager',
            'approved_manager',
            'rejected_manager',
            'approved_rh',
            'rejected_rh'
        ));

COMMENT ON COLUMN public.absence_requests.workflow_step IS 'Étape du circuit manager → RH (pending = direct RH).';

CREATE INDEX IF NOT EXISTS idx_absence_requests_company_workflow
    ON public.absence_requests (company_id, workflow_step)
    WHERE status = 'pending';
