-- Médailles du travail : autoriser la base d'ancienneté « date d'ancienneté reprise ».
-- Elsa (01/08/2026) : sur toutes les sociétés l'ancienneté retenue est l'ancienneté
-- reprise, pas le seul temps passé dans l'entreprise depuis l'embauche.

ALTER TABLE public.company_work_medal_settings
    DROP CONSTRAINT IF EXISTS company_work_medal_settings_seniority_basis_check;

ALTER TABLE public.company_work_medal_settings
    ADD CONSTRAINT company_work_medal_settings_seniority_basis_check
        CHECK (seniority_basis IN (
            'total_career', 'company_only', 'seniority_reference_date'
        ));
