-- Verrou de génération de bulletin : une seule génération à la fois pour un
-- salarié et un mois (deux onglets, un double clic, une régénération IJSS
-- pendant une génération). Le verrou expire seul : une instance arrêtée en
-- pleine génération ne bloque personne au-delà de la durée demandée.
--
-- Additive : une table neuve et deux fonctions. Aucune donnée existante n'est
-- lue ni modifiée. Le serveur fonctionne sans cette migration (il génère alors
-- sans verrou, comme avant, et le signale dans ses journaux).

create table if not exists public.payslip_generation_locks (
  employee_id uuid not null,
  year integer not null,
  month integer not null check (month between 1 and 12),
  jeton uuid not null,
  locked_until timestamptz not null,
  created_at timestamptz not null default now(),
  primary key (employee_id, year, month)
);

alter table public.payslip_generation_locks enable row level security;
revoke all on table public.payslip_generation_locks from anon, authenticated;
-- Seul le serveur (clé service_role) s'en sert ; droit explicite, sans dépendre
-- des privilèges par défaut du projet.
grant select, insert, update, delete on table public.payslip_generation_locks to service_role;

-- Prend le verrou s'il est libre ou expiré. Rend true si pris, false sinon.
create or replace function public.prendre_verrou_generation_bulletin(
  p_employee_id uuid,
  p_year integer,
  p_month integer,
  p_jeton uuid,
  p_duree_secondes integer
) returns boolean
language sql
set search_path = public
as $$
  with pris as (
    insert into public.payslip_generation_locks as v
      (employee_id, year, month, jeton, locked_until)
    values
      (p_employee_id, p_year, p_month, p_jeton,
       now() + make_interval(secs => p_duree_secondes))
    on conflict (employee_id, year, month) do update
      set jeton = excluded.jeton,
          locked_until = excluded.locked_until,
          created_at = now()
      where v.locked_until < now()
    returning 1
  )
  select exists (select 1 from pris);
$$;

-- Rend le verrou, seulement s'il appartient encore à ce jeton.
create or replace function public.rendre_verrou_generation_bulletin(
  p_employee_id uuid,
  p_year integer,
  p_month integer,
  p_jeton uuid
) returns void
language sql
set search_path = public
as $$
  delete from public.payslip_generation_locks
  where employee_id = p_employee_id
    and year = p_year
    and month = p_month
    and jeton = p_jeton;
$$;

revoke all on function public.prendre_verrou_generation_bulletin(uuid, integer, integer, uuid, integer)
  from public, anon, authenticated;
revoke all on function public.rendre_verrou_generation_bulletin(uuid, integer, integer, uuid)
  from public, anon, authenticated;
grant execute on function public.prendre_verrou_generation_bulletin(uuid, integer, integer, uuid, integer)
  to service_role;
grant execute on function public.rendre_verrou_generation_bulletin(uuid, integer, integer, uuid)
  to service_role;
