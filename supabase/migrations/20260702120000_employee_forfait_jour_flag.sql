alter table public.employees
  add column if not exists is_forfait_jour boolean not null default false;

comment on column public.employees.is_forfait_jour is
  'Indique que le salarié est géré en forfait jours, séparément du statut catégoriel Cadre/Non-Cadre.';

-- Le forfait jours devient un réglage dédié. Par défaut métier EYWAI :
-- tout salarié catégorisé cadre est au forfait jours.
update public.employees
set
  is_forfait_jour = true,
  statut = 'Cadre'
where lower(replace(replace(coalesce(statut, ''), '-', ''), ' ', '')) like '%cadre%'
  and lower(replace(replace(coalesce(statut, ''), '-', ''), ' ', '')) not like '%noncadre%';

-- Nettoyage des anciens libellés sans perdre l'information forfait jours.
update public.employees
set
  is_forfait_jour = true,
  statut = 'Non-Cadre'
where lower(replace(replace(coalesce(statut, ''), '-', ''), ' ', '')) like '%noncadre%'
  and lower(coalesce(statut, '')) like '%forfait%jour%';

update public.employees
set statut = 'Non-Cadre'
where lower(replace(replace(coalesce(statut, ''), '-', ''), ' ', '')) like '%noncadre%';
