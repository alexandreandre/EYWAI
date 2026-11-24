-- ============================================================================
-- Types de poste par société (lot C, 24/11)
--
-- Jusqu'ici un type de poste (`shift_types`) n'appartenait qu'à une convention
-- planning, partagée par toutes les sociétés qui l'ont choisie : modifier les
-- postes d'une usine les aurait changés pour toute la convention.
--
-- Désormais :
--   - company_id renseigné  → type propre à la société (créé ou copié depuis elle) ;
--   - company_id NULL       → type de convention, partagé en lecture.
-- Modifier ou désactiver un type de convention depuis une société crée une copie
-- propre à la société (replaces_shift_type_id = le type partagé), jamais une
-- écriture sur le type partagé (backend : planning/application/shift_type_commands.py).
--
-- Aucune donnée existante n'est modifiée : les types actuels gardent leur
-- convention et company_id NULL.
-- Le backend écrit avec service_role ; les politiques ci-dessous ne valent que
-- pour un accès direct (authenticated / anon).
-- Idempotent.
-- ============================================================================

alter table public.shift_types
    add column if not exists company_id uuid null
        references public.companies (id) on delete cascade;

alter table public.shift_types
    add column if not exists replaces_shift_type_id uuid null
        references public.shift_types (id) on delete set null;

comment on column public.shift_types.company_id is
    'Société propriétaire du type de poste ; NULL = type de la convention planning, partagé en lecture.';
comment on column public.shift_types.replaces_shift_type_id is
    'Type de convention que cette copie de la société remplace (pour elle seule).';

-- Un type de société n'a pas de convention (le planning ne propose que son
-- propre référentiel ; la société peut en changer sans perdre ses postes).
alter table public.shift_types
    alter column collective_agreement_id drop not null;

alter table public.shift_types
    drop constraint if exists shift_types_proprietaire_check;
alter table public.shift_types
    add constraint shift_types_proprietaire_check
        check (company_id is not null or collective_agreement_id is not null);

-- Unicité du code : par convention pour les types partagés, par société pour
-- les autres (deux sociétés d'une même convention peuvent avoir chacune MATIN).
alter table public.shift_types
    drop constraint if exists shift_types_collective_agreement_id_code_key;
create unique index if not exists shift_types_convention_code_key
    on public.shift_types (collective_agreement_id, code)
    where company_id is null;
create unique index if not exists shift_types_societe_code_key
    on public.shift_types (company_id, upper(code))
    where company_id is not null;

create index if not exists idx_shift_types_company_id
    on public.shift_types (company_id)
    where company_id is not null;
create index if not exists idx_shift_types_replaces
    on public.shift_types (replaces_shift_type_id)
    where replaces_shift_type_id is not null;

-- --- RLS -------------------------------------------------------------------
-- Lecture : les types de convention restent publics (référentiel sans donnée
-- personnelle, cf. 20260804170000) ; ceux d'une société, ses seuls membres.
drop policy if exists planning_shift_types_select_public on public.shift_types;
create policy planning_shift_types_select_public
    on public.shift_types
    for select
    to anon, authenticated
    using (company_id is null);

drop policy if exists planning_shift_types_select_company on public.shift_types;
create policy planning_shift_types_select_company
    on public.shift_types
    for select
    to authenticated
    using (
        company_id is not null
        and exists (
            select 1
            from public.user_company_accesses uca
            where uca.user_id = auth.uid()
              and uca.company_id = shift_types.company_id
        )
    );

-- Écriture : RH / admin de la société, sur les types de la société seulement
-- (mêmes rôles que `shifts`). Les politiques super_admin existantes restent.
drop policy if exists planning_shift_types_insert_company on public.shift_types;
create policy planning_shift_types_insert_company
    on public.shift_types
    for insert
    to authenticated
    with check (
        company_id is not null
        and exists (
            select 1
            from public.user_company_accesses uca
            where uca.user_id = auth.uid()
              and uca.company_id = shift_types.company_id
              and uca.role = any (array['admin'::text, 'rh'::text])
        )
    );

drop policy if exists planning_shift_types_update_company on public.shift_types;
create policy planning_shift_types_update_company
    on public.shift_types
    for update
    to authenticated
    using (
        company_id is not null
        and exists (
            select 1
            from public.user_company_accesses uca
            where uca.user_id = auth.uid()
              and uca.company_id = shift_types.company_id
              and uca.role = any (array['admin'::text, 'rh'::text])
        )
    )
    with check (
        company_id is not null
        and exists (
            select 1
            from public.user_company_accesses uca
            where uca.user_id = auth.uid()
              and uca.company_id = shift_types.company_id
              and uca.role = any (array['admin'::text, 'rh'::text])
        )
    );

drop policy if exists planning_shift_types_delete_company on public.shift_types;
create policy planning_shift_types_delete_company
    on public.shift_types
    for delete
    to authenticated
    using (
        company_id is not null
        and exists (
            select 1
            from public.user_company_accesses uca
            where uca.user_id = auth.uid()
              and uca.company_id = shift_types.company_id
              and uca.role = any (array['admin'::text, 'rh'::text])
        )
    );
