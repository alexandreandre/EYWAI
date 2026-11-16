-- Activité partielle (retour d'Elsa du 16/11 : LEWIS depuis juin) : réglage par
-- société. Le calcul pose deux variables du mois que le moteur sait déjà payer
-- (« Heures chômées (act. part.) » et « Indemnité activité partielle »).
-- Valeurs légales par défaut : service-public F23503 / F13898 (vérifiées le
-- 13/08/2026 et le 16/10/2026) : 60 % du brut horaire, entre 9,74 € et 33,24 €.
create table if not exists public.company_activite_partielle (
  company_id uuid primary key references public.companies(id) on delete cascade,
  active boolean not null default false,
  date_debut date,
  date_fin date,
  taux_indemnite numeric(5,2) not null default 60 check (taux_indemnite > 0 and taux_indemnite <= 100),
  plancher_horaire numeric(8,2) not null default 9.74 check (plancher_horaire >= 0),
  plafond_horaire numeric(8,2) not null default 33.24 check (plafond_horaire > 0),
  heures_par_jour numeric(5,2) check (heures_par_jour is null or (heures_par_jour > 0 and heures_par_jour <= 24)),
  reference_decision text,
  note text,
  updated_by uuid,
  updated_at timestamptz not null default now(),
  constraint activite_partielle_periode check (date_fin is null or date_debut is null or date_fin >= date_debut)
);

alter table public.company_activite_partielle enable row level security;
revoke all on public.company_activite_partielle from anon, authenticated;
