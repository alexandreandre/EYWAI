-- Paliers de prime d'ancienneté libres (retour d'Elsa du 13/11 : 10, 20, 30, 40 ans).
-- Les quatre échelons officiels (20, 30, 35, 40 ans) gardent leur nom ; un autre
-- palier s'appelle « palier_<années> ». Un dossier reste unique par salarié et palier.
ALTER TABLE public.employee_work_medal_cases
    DROP CONSTRAINT IF EXISTS employee_work_medal_cases_medal_level_check,
    DROP CONSTRAINT IF EXISTS employee_work_medal_cases_milestone_years_check;

ALTER TABLE public.employee_work_medal_cases
    ADD CONSTRAINT employee_work_medal_cases_medal_level_check
        CHECK (medal_level ~ '^(argent|vermeil|or|grand_or|palier_[0-9]{1,2})$'),
    ADD CONSTRAINT employee_work_medal_cases_milestone_years_check
        CHECK (milestone_years BETWEEN 1 AND 50);
