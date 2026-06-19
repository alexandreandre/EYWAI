-- CP ancienneté & fractionnement : preset métallurgie, statuts grants, préremplissage.

-- seniority_basis : autoriser seniority_reference_date (preset métallurgie / LEWIS)
ALTER TABLE public.company_cp_seniority_settings
    DROP CONSTRAINT IF EXISTS company_cp_seniority_settings_seniority_basis_check;

ALTER TABLE public.company_cp_seniority_settings
    ADD CONSTRAINT company_cp_seniority_settings_seniority_basis_check
    CHECK (seniority_basis IN (
        'company_only', 'include_prior_service', 'seniority_reference_date'
    ));

-- Preset métallurgie IDCC 3248
ALTER TABLE public.company_cp_seniority_settings
    DROP CONSTRAINT IF EXISTS company_cp_seniority_settings_preset_check;

ALTER TABLE public.company_cp_seniority_settings
    ADD CONSTRAINT company_cp_seniority_settings_preset_check
    CHECK (preset IN (
        'plasturgie_idcc_0292', 'lewis_agreement', 'metallurgie_idcc_3248', 'custom'
    ));

-- Statut grant CP ancienneté
ALTER TABLE public.employee_cp_seniority_grants
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'computed'
        CHECK (status IN ('computed', 'validated', 'overridden'));

ALTER TABLE public.employee_cp_seniority_grants
    ADD COLUMN IF NOT EXISTS validated_at timestamptz;

ALTER TABLE public.employee_cp_seniority_grants
    ADD COLUMN IF NOT EXISTS validated_by uuid;

COMMENT ON COLUMN public.employee_cp_seniority_grants.status IS
    'computed = preview auto ; validated = validé RH ; overridden = correction manuelle.';

-- Fractionnement : méthode de calcul + statut grant
ALTER TABLE public.company_cp_fractionnement_settings
    ADD COLUMN IF NOT EXISTS calculation_method text NOT NULL DEFAULT 'mbc'
        CHECK (calculation_method IN ('mbc', 'manual', 'legal'));

COMMENT ON COLUMN public.company_cp_fractionnement_settings.calculation_method IS
    'mbc = formule Excel client ; manual = solde saisi ; legal = calcul depuis absences.';

ALTER TABLE public.employee_cp_fractionnement_grants
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'computed'
        CHECK (status IN ('computed', 'validated'));

ALTER TABLE public.employee_cp_fractionnement_grants
    ADD COLUMN IF NOT EXISTS validated_at timestamptz;

ALTER TABLE public.employee_cp_fractionnement_grants
    ADD COLUMN IF NOT EXISTS validated_by uuid;

-- Overrides explicites sur les saisies fractionnement
ALTER TABLE public.employee_cp_fractionnement_inputs
    ADD COLUMN IF NOT EXISTS report_june_manual_override boolean NOT NULL DEFAULT false;

ALTER TABLE public.employee_cp_fractionnement_inputs
    ADD COLUMN IF NOT EXISTS seniority_manual_override boolean NOT NULL DEFAULT false;

ALTER TABLE public.employee_cp_fractionnement_inputs
    ADD COLUMN IF NOT EXISTS manual_solde_ouvrables numeric(10, 2);
