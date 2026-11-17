-- Date d'effet de la convention collective d'une société (relevé du 16/11/2026).
--
-- Zone 404 passe de « sans convention » (9999) à Syntec (1486) à une date
-- d'effet ; ses bulletins de juillet à octobre sont repris et validés. Sans
-- date, rattacher Syntec l'appliquerait aux mois passés.
--
-- Lecture : app/modules/collective_agreements/domain/convention_datee.py.
-- Une ligne sans date vaut toujours (comportement d'avant : rien ne bouge pour
-- les sociétés déjà rattachées). Une ligne datée vaut de date_debut à date_fin
-- incluses et l'emporte, dès qu'elle commence, sur une ligne sans date.
-- Un mois de paie se lit à son dernier jour.

alter table public.company_collective_agreements
  add column if not exists date_debut date,
  add column if not exists date_fin date;

alter table public.company_collective_agreements
  drop constraint if exists company_collective_agreements_dates_ordonnees;
alter table public.company_collective_agreements
  add constraint company_collective_agreements_dates_ordonnees
  check (date_debut is null or date_fin is null or date_debut <= date_fin);

comment on column public.company_collective_agreements.date_debut is
  'Premier jour où la convention s''applique à la société ; vide = depuis toujours.';
comment on column public.company_collective_agreements.date_fin is
  'Dernier jour où la convention s''applique à la société ; vide = sans fin.';
