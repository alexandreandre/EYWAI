-- Date de référence de la reprise des soldes CP.
--
-- Les soldes d'ouverture sont calibrés sur un bulletin : ils encodent déjà tous
-- les congés pris jusqu'à la date de ce bulletin. Le module congés va désormais
-- lire les congés payés saisis dans le planning ; sans cette date, il déduirait
-- une seconde fois ceux qui sont antérieurs à la reprise.
--
-- Jusqu'ici l'information ne vivait que dans le libellé (« Import CP bulletin
-- Mai 2026 (…) »), donc illisible par le moteur.

alter table public.employee_leave_adjustments
  add column if not exists cp_opening_reference_date date;

comment on column public.employee_leave_adjustments.cp_opening_reference_date is
  'Date du bulletin ayant servi à calibrer les soldes d''ouverture CP. '
  'Les congés pris jusqu''à cette date sont déjà intégrés au solde.';

-- Reprise de l'existant : tous les imports en base proviennent des bulletins de
-- mai 2026, dont la période se clôt le 31/05/2026.
update public.employee_leave_adjustments
   set cp_opening_reference_date = date '2026-05-31'
 where cp_opening_reference_date is null
   and note like 'Import CP bulletin Mai 2026%';
