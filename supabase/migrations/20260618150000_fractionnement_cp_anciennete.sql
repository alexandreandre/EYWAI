-- Retrait CP ancienneté dans le calcul fractionnement MBC (saisie par salarié).

ALTER TABLE public.employee_cp_fractionnement_inputs
    ADD COLUMN IF NOT EXISTS cp_seniority_deduction_ouvres numeric(10, 2) NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.employee_cp_fractionnement_inputs.cp_seniority_deduction_ouvres IS
    'Jours ouvrés CP ancienneté déduits du solde au 31/10 avant calcul fractionnement.';
