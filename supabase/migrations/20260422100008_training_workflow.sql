-- Workflow d'inscription formation : salarié → manager → RH (Pack Talent Bloc 1)

ALTER TABLE training_enrollments
    ADD COLUMN IF NOT EXISTS requested_by uuid,
    ADD COLUMN IF NOT EXISTS manager_id uuid REFERENCES employees (id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS manager_approved_at timestamptz,
    ADD COLUMN IF NOT EXISTS manager_rejected_at timestamptz,
    ADD COLUMN IF NOT EXISTS manager_rejection_reason text,
    ADD COLUMN IF NOT EXISTS rh_approved_at timestamptz,
    ADD COLUMN IF NOT EXISTS rh_rejected_at timestamptz,
    ADD COLUMN IF NOT EXISTS rh_rejection_reason text;

COMMENT ON COLUMN training_enrollments.requested_by IS 'Profil (auth) ayant initié la demande côté salarié';

COMMENT ON COLUMN training_enrollments.manager_id IS 'Référent équipe (employees.id) attendu pour valider';
