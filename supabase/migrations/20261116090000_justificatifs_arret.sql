-- Écran « Arrêts et IJ » (retour d'Elsa du 16/11) : pièces facultatives jointes
-- à un arrêt — virement de la CPAM (subrogation), IJ transmises par le salarié,
-- décompte CPAM. Le fichier vit dans le seau des justificatifs d'absence ; la
-- table n'est lue et écrite que par le serveur (aucun droit aux rôles publics).
create table if not exists public.absence_request_justificatifs (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  absence_request_id uuid not null references public.absence_requests(id) on delete cascade,
  kind text not null check (kind in ('virement_cpam', 'ij_salarie', 'decompte_cpam', 'autre')),
  storage_path text not null,
  filename text,
  created_by uuid,
  created_at timestamptz not null default now()
);

create index if not exists absence_request_justificatifs_absence_idx
  on public.absence_request_justificatifs (absence_request_id);

alter table public.absence_request_justificatifs enable row level security;
revoke all on public.absence_request_justificatifs from anon, authenticated;

comment on table public.absence_request_justificatifs is
  'Pièces facultatives d''un arrêt (virement CPAM, IJ transmises par le salarié, décompte CPAM).';
