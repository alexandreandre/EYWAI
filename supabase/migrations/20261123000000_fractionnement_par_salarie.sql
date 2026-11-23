-- Fractionnement : case par salarié (arbitrages du 23/11). Cochée par défaut ;
-- décochée = aucun jour de fractionnement (renonciation écrite du salarié).
alter table public.employees
  add column if not exists cp_fractionnement_actif boolean not null default true;
comment on column public.employees.cp_fractionnement_actif is
  'Fractionnement des congés payés activé pour ce salarié (décoché : renonciation, aucun jour).';
