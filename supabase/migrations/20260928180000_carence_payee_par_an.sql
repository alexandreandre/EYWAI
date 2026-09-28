-- Carence payée une fois par an (convention de la plasturgie) et maintien en
-- jours ouvrés, par société.
--
-- Chez Colorplast, Comitech Composite et Mont Blanc Composite, l'employeur paie
-- les jours de carence d'un arrêt maladie dans la limite de 3 jours par année
-- civile, pour un salarié d'au moins un an d'ancienneté ; le crédit se
-- consomme jour par jour et repart à zéro en janvier. La journée payée vaut
-- 7 h plus la quote-part d'heures sup structurelles (maintien « en jours
-- ouvrés »), et les IJSS sont versées directement au salarié : la subrogation
-- n'est jamais faite.

alter table public.company_maintenance_settings
  add column if not exists paid_waiting_days_per_year integer,
  add column if not exists paid_waiting_min_seniority_months integer not null default 12,
  add column if not exists maintain_working_days boolean not null default false;

comment on column public.company_maintenance_settings.paid_waiting_days_per_year is
  'Jours de carence payés par l''employeur par année civile (crédit consommé jour par jour, remis à zéro en janvier). Vide : aucun.';
comment on column public.company_maintenance_settings.paid_waiting_min_seniority_months is
  'Ancienneté minimale, en mois, pour bénéficier de la carence payée.';
comment on column public.company_maintenance_settings.maintain_working_days is
  'Maintien valorisé en jours ouvrés : 7 h plus la quote-part d''heures sup structurelles, week-ends non maintenus, IJSS hors bulletin.';

alter table public.company_maintenance_settings
  drop constraint if exists company_maintenance_settings_subrogation_mode_check;
alter table public.company_maintenance_settings
  add constraint company_maintenance_settings_subrogation_mode_check
  check (subrogation_mode = any (array['when_maintien', 'automatic', 'at_mp_only', 'per_case', 'never']));
