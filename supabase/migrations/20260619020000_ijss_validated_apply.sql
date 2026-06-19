-- Suivi IJSS : montant brut CPAM validé et traçabilité application bulletin

ALTER TABLE public.ijss_expected_lines
    ADD COLUMN IF NOT EXISTS ijss_brut_validated numeric(12, 2),
    ADD COLUMN IF NOT EXISTS validation_source text
        CHECK (validation_source IS NULL OR validation_source IN (
            'cpam_decompte', 'bank_transfer', 'manual'
        )),
    ADD COLUMN IF NOT EXISTS validated_at timestamptz,
    ADD COLUMN IF NOT EXISTS validated_by uuid,
    ADD COLUMN IF NOT EXISTS applied_to_payslip_at timestamptz,
    ADD COLUMN IF NOT EXISTS applied_ijss_brut numeric(12, 2);

COMMENT ON COLUMN public.ijss_expected_lines.ijss_brut_validated IS
    'Montant brut IJSS CPAM retenu pour la paie après rapprochement.';

COMMENT ON COLUMN public.ijss_expected_lines.applied_ijss_brut IS
    'Montant brut IJSS effectivement appliqué sur le bulletin (snapshot).';
