-- Formules de prévoyance de la société (conception du 02/11/2026).
--
-- La RH les crée une fois ; sur la fiche, choisir une formule copie ses lignes
-- dans specificites_paie.prevoyance.lignes_specifiques et pose
-- specificites_paie.prevoyance.formule_id. Le moteur de paie ne lit que les
-- lignes de la fiche : cette table ne change aucun calcul.
--
-- `lignes` : même forme que les lignes de la fiche (libelle, salarial,
-- patronal, forfait_social en fraction, base facultative : brut_plafonne par
-- défaut, tranche_2, brut).
--
-- Rejouable sans erreur (IF NOT EXISTS, DROP POLICY IF EXISTS).

create table if not exists public.company_prevoyance_formules (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references public.companies(id) on delete cascade,
    libelle text not null,
    statut_categoriel text not null default 'tous'
        check (statut_categoriel in ('cadre', 'non_cadre', 'tous')),
    lignes jsonb not null default '[]'::jsonb
        check (jsonb_typeof(lignes) = 'array'),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by uuid references auth.users(id)
);

comment on table public.company_prevoyance_formules is
    'Formules de prévoyance de la société, copiées sur la fiche au choix (specificites_paie.prevoyance.formule_id).';

create index if not exists idx_company_prevoyance_formules_company
    on public.company_prevoyance_formules (company_id);

alter table public.company_prevoyance_formules enable row level security;

drop policy if exists company_prevoyance_formules_select on public.company_prevoyance_formules;
create policy company_prevoyance_formules_select on public.company_prevoyance_formules
    for select to authenticated
    using (
        company_id in (
            select uca.company_id from public.user_company_accesses uca
            where uca.user_id = auth.uid()
        )
    );

drop policy if exists company_prevoyance_formules_write on public.company_prevoyance_formules;
create policy company_prevoyance_formules_write on public.company_prevoyance_formules
    for all to authenticated
    using (
        company_id in (
            select uca.company_id from public.user_company_accesses uca
            where uca.user_id = auth.uid()
            and uca.role in ('admin', 'rh', 'collaborateur_rh')
        )
    )
    with check (
        company_id in (
            select uca.company_id from public.user_company_accesses uca
            where uca.user_id = auth.uid()
            and uca.role in ('admin', 'rh', 'collaborateur_rh')
        )
    );
