-- Heures sup : règle par salarié (retour d'Elsa, Cartol, examen d'ergonomie du 20/11).
-- Les alternants d'une société à compteur ne suivent pas la règle de la société.
-- null (défaut) = règle de la société (company_modulation_settings.hs_routing_policy) ;
-- 'pay_all' = toujours payées (rien n'alimente le compteur) ;
-- 'account_all' = toujours au compteur.
-- Aucune donnée modifiée : personne n'est coché ici.
alter table public.employees
  add column if not exists hs_routing_override text null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'employees_hs_routing_override_check'
      and conrelid = 'public.employees'::regclass
  ) then
    alter table public.employees
      add constraint employees_hs_routing_override_check
      check (hs_routing_override is null or hs_routing_override in ('pay_all', 'account_all'));
  end if;
end $$;

comment on column public.employees.hs_routing_override is
  'Règle des heures sup propre au salarié : null = règle de la société, pay_all = toujours payées, account_all = toujours au compteur.';
