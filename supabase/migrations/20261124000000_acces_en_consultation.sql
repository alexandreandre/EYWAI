-- Accès en consultation : un compte qui voit la paie d'une société sans rien y modifier
-- (expert-comptable qui contrôle les paies). Le serveur refuse toute modification
-- à un compte dont un accès porte ce marqueur (backend/app/core/consultation.py).
alter table public.user_company_accesses
    add column if not exists lecture_seule boolean not null default false;

comment on column public.user_company_accesses.lecture_seule is
    'Accès en consultation : le compte voit tout ce que son rôle voit, mais le serveur refuse toute modification.';
