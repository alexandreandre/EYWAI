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

-- Maintien après réception des IJ (retour d'Elsa du 13/11, plasturgie) : sans
-- subrogation, le maintien n'est versé qu'une fois le montant des IJ du mois
-- saisi (suivi IJSS ou bulletin). Éteint partout : rien ne change sans décision.
alter table public.company_maintenance_settings
  add column if not exists maintien_apres_ij_recues boolean not null default false;

comment on column public.company_maintenance_settings.maintien_apres_ij_recues is
  'Sans subrogation : maintien versé seulement quand les IJ du mois sont saisies (déclarées par le salarié).';
