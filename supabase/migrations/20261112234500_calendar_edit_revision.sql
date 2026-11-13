-- Calendrier : révision des entrées et réservation courte de l'enregistrement.
-- Préparée localement ; ne pas appliquer sans la livraison backend/frontend.
-- Les écritures d'imports/absences passent par le même trigger que l'éditeur.
-- Aucun taux, horaire, absence ou solde existant n'est modifié.

alter table public.employee_schedules
  add column if not exists calendar_revision uuid not null default gen_random_uuid();

create table if not exists public.calendar_edit_locks (
  employee_id uuid not null,
  year integer not null,
  month integer not null check (month between 1 and 12),
  token uuid not null,
  locked_until timestamptz not null,
  primary key (employee_id, year, month)
);
alter table public.calendar_edit_locks enable row level security;
revoke all on table public.calendar_edit_locks from public, anon, authenticated;
grant select, insert, update, delete on table public.calendar_edit_locks to service_role;

create or replace function public.calendar_edit_key(p_employee_id uuid, p_year integer, p_month integer)
returns bigint language sql immutable set search_path = '' as $$
  select pg_catalog.hashtextextended('calendar:' || p_employee_id::text || ':' || p_year::text || ':' || p_month::text, 0);
$$;

-- La révision change pour toutes les sources d'entrées, pas pour un simple
-- recalcul des événements/cumuls. Le client ne peut pas choisir sa révision.
-- SECURITY INVOKER : aucun contournement RLS. Les écritures passent par le
-- serveur service_role ; les rôles navigateur ne lisent pas les réservations.
create or replace function public.guard_calendar_edit()
returns trigger language plpgsql security invoker set search_path = '' as $$
declare
  e uuid;
  y integer;
  m integer;
  held public.calendar_edit_locks%rowtype;
  target record;
  supplied text := coalesce(nullif(pg_catalog.current_setting('request.headers', true), ''), '{}')::jsonb ->> 'x-eywai-calendar-token';
begin
  if tg_op = 'DELETE' then e := old.employee_id; y := old.year; m := old.month;
  else e := new.employee_id; y := new.year; m := new.month;
  end if;
  -- Un déplacement libre reste possible. Les deux clés sont contrôlées,
  -- dans le même ordre, pour ne pas déplacer une ligne réservée à une RH.
  for target in
    select distinct * from (
      select e as employee_id, y as year, m as month
      union all
      select old.employee_id, old.year, old.month where tg_op = 'UPDATE'
    ) as keys_to_guard order by employee_id, year, month
  loop
    -- UPDATE peut déjà tenir la ligne, UPSERT commencer par INSERT : ne
    -- jamais attendre ici avec l'ordre inverse.
    if not pg_catalog.pg_try_advisory_xact_lock(public.calendar_edit_key(target.employee_id, target.year, target.month)) then
      raise exception using errcode = 'PT409', message = 'Une écriture de ce calendrier est en cours. Réessayez.';
    end if;
    select * into held from public.calendar_edit_locks where employee_id = target.employee_id and year = target.year and month = target.month;
    if supplied is not null then
      if held.token is null or held.token::text <> supplied or held.locked_until <= pg_catalog.clock_timestamp() then
        raise exception using errcode = 'PT409', message = 'La réservation du calendrier a expiré. Rechargez le calendrier avant de reprendre.';
      end if;
    elsif held.locked_until > pg_catalog.clock_timestamp() then
      raise exception using errcode = 'PT409', message = 'Un enregistrement de ce calendrier est en cours. Réessayez après son achèvement.';
    end if;
  end loop;
  if tg_op = 'DELETE' then return old; end if;
  if tg_op = 'INSERT' then new.calendar_revision := pg_catalog.gen_random_uuid();
  elsif (new.planned_calendar, new.actual_hours, new.company_id, new.employee_id, new.year, new.month) is distinct from (old.planned_calendar, old.actual_hours, old.company_id, old.employee_id, old.year, old.month) then
    new.calendar_revision := pg_catalog.gen_random_uuid();
  else new.calendar_revision := old.calendar_revision;
  end if;
  return new;
end;
$$;
drop trigger if exists guard_calendar_edit on public.employee_schedules;
create trigger guard_calendar_edit before insert or update or delete on public.employee_schedules
  for each row execute function public.guard_calendar_edit();

create or replace function public.read_calendar_snapshot(p_employee_id uuid, p_company_id uuid, p_year integer, p_month integer)
returns jsonb language sql volatile security invoker set search_path = '' as $$
  select jsonb_build_object(
    'revision', s.calendar_revision,
    'planned_calendar', coalesce(s.planned_calendar, '{}'::jsonb),
    'actual_hours', coalesce(s.actual_hours, '{}'::jsonb),
    'busy', coalesce(l.locked_until > pg_catalog.clock_timestamp() and
      l.token::text is distinct from (coalesce(nullif(pg_catalog.current_setting('request.headers', true), ''), '{}')::jsonb ->> 'x-eywai-calendar-token'), false)
  )
  from public.employees e
  left join public.employee_schedules s on s.employee_id = e.id and s.company_id = e.company_id and s.year = p_year and s.month = p_month
  left join public.calendar_edit_locks l on l.employee_id = e.id and l.year = p_year and l.month = p_month
  where e.id = p_employee_id and e.company_id = p_company_id;
$$;

-- La comparaison et la réservation sont dans la même transaction. Les
-- triggers des autres auteurs prennent la même clé, même pour un mois neuf.
create or replace function public.begin_calendar_edit(
  p_employee_id uuid, p_company_id uuid, p_year integer, p_month integer,
  p_expected_revision uuid, p_token uuid, p_seconds integer
) returns text language plpgsql security invoker set search_path = '' as $$
declare
  current_revision uuid;
  held public.calendar_edit_locks%rowtype;
begin
  if p_token is null or p_seconds is null or p_year is null or p_month is null or p_seconds not between 5 and 120 or p_month not between 1 and 12 or p_year not between 2000 and 2100 then
    raise exception using errcode = '22023', message = 'Réservation de calendrier invalide.';
  end if;
  perform pg_catalog.pg_advisory_xact_lock(public.calendar_edit_key(p_employee_id, p_year, p_month));
  if not exists (select 1 from public.employees where id = p_employee_id and company_id = p_company_id) then return 'not_found'; end if;
  select * into held from public.calendar_edit_locks where employee_id = p_employee_id and year = p_year and month = p_month;
  if held.locked_until > pg_catalog.clock_timestamp() then return 'busy'; end if;
  select calendar_revision into current_revision from public.employee_schedules where employee_id = p_employee_id and year = p_year and month = p_month;
  if current_revision is distinct from p_expected_revision then return 'conflict'; end if;
  insert into public.calendar_edit_locks (employee_id, year, month, token, locked_until)
  values (p_employee_id, p_year, p_month, p_token, pg_catalog.clock_timestamp() + pg_catalog.make_interval(secs => p_seconds))
  on conflict (employee_id, year, month) do update set token = excluded.token, locked_until = excluded.locked_until;
  return 'acquired';
end;
$$;

create or replace function public.renew_calendar_edit(p_employee_id uuid, p_year integer, p_month integer, p_token uuid, p_seconds integer)
returns boolean language plpgsql security invoker set search_path = '' as $$
begin
  if p_seconds not between 5 and 120 then return false; end if;
  perform pg_catalog.pg_advisory_xact_lock(public.calendar_edit_key(p_employee_id, p_year, p_month));
  update public.calendar_edit_locks set locked_until = pg_catalog.clock_timestamp() + pg_catalog.make_interval(secs => p_seconds)
  where employee_id = p_employee_id and year = p_year and month = p_month and token = p_token and locked_until > pg_catalog.clock_timestamp();
  return found;
end;
$$;

create or replace function public.end_calendar_edit(p_employee_id uuid, p_year integer, p_month integer, p_token uuid)
returns void language plpgsql security invoker set search_path = '' as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(public.calendar_edit_key(p_employee_id, p_year, p_month));
  delete from public.calendar_edit_locks where employee_id = p_employee_id and year = p_year and month = p_month and token = p_token;
end;
$$;

revoke all on function public.calendar_edit_key(uuid, integer, integer) from public, anon, authenticated;
revoke all on function public.guard_calendar_edit() from public, anon, authenticated;
revoke all on function public.read_calendar_snapshot(uuid, uuid, integer, integer) from public, anon, authenticated;
revoke all on function public.begin_calendar_edit(uuid, uuid, integer, integer, uuid, uuid, integer) from public, anon, authenticated;
revoke all on function public.renew_calendar_edit(uuid, integer, integer, uuid, integer) from public, anon, authenticated;
revoke all on function public.end_calendar_edit(uuid, integer, integer, uuid) from public, anon, authenticated;
grant execute on function public.calendar_edit_key(uuid, integer, integer), public.guard_calendar_edit(),
  public.read_calendar_snapshot(uuid, uuid, integer, integer),
  public.begin_calendar_edit(uuid, uuid, integer, integer, uuid, uuid, integer),
  public.renew_calendar_edit(uuid, integer, integer, uuid, integer),
  public.end_calendar_edit(uuid, integer, integer, uuid) to service_role;
