-- Connexion par lien, sans mot de passe : un lien envoyé par e-mail (ou remis à la main pour
-- une invitation) ouvre la session d'un compte, une seule fois, avant son échéance.
-- Seule l'empreinte SHA-256 du jeton est gardée ; le jeton en clair n'existe que dans le lien.
-- Lue et écrite par le serveur seul (service_role) : RLS active, aucune politique.
create table if not exists public.liens_de_connexion (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    jeton_hash text not null unique,
    origine text not null check (origine in ('invitation', 'demande')),
    expires_at timestamptz not null,
    used_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists idx_liens_de_connexion_user on public.liens_de_connexion (user_id);

alter table public.liens_de_connexion enable row level security;
revoke all on public.liens_de_connexion from anon, authenticated;

comment on table public.liens_de_connexion is
    'Liens de connexion sans mot de passe : empreinte du jeton, usage unique, échéance (backend/app/modules/auth/application/liens_de_connexion.py).';
