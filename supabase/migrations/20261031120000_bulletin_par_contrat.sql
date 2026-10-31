-- Deux contrats le même mois : un bulletin par contrat (D3, spécification
-- docs/superpowers/specs/2026-10-31-deux-contrats-meme-mois-design.md).
--
-- Un CDD finit le 10/11, un nouveau contrat commence le 17/11 : novembre a deux
-- bulletins. La clé du bulletin devient (société, salarié, année, mois, contrat).
-- Le contrat est nul pour celui de la fiche (tous les bulletins existants), et
-- vaut le contrat rangé par « Nouveau contrat » pour le bulletin du mois
-- partagé. `nulls not distinct` : deux bulletins à contrat nul restent
-- impossibles, et l'écriture à contrat nul remplace celui du mois, comme avant.
--
-- Aucune donnée existante n'est modifiée : deux colonnes nulles, l'index
-- remplacé, une fonction. Le code et la migration partent ensemble : l'ancien
-- `on_conflict` (sans contrat) n'a plus d'index après elle.

alter table public.payslips
  add column if not exists contract_period_id uuid
  references public.employee_contract_periods(id) on delete restrict;

alter table public.monthly_inputs
  add column if not exists contract_period_id uuid
  references public.employee_contract_periods(id) on delete restrict;

comment on column public.payslips.contract_period_id is
  'Contrat payé par ce bulletin : nul = le contrat de la fiche ; rempli = le contrat '
  'rangé qui finit dans un mois où le contrat de la fiche commence (D3).';
comment on column public.monthly_inputs.contract_period_id is
  'Bulletin auquel la variable appartient dans un mois à deux contrats : nul = le '
  'contrat de la fiche ; rempli = le contrat rangé (D3).';

drop index if exists public.idx_payslips_company_unique;
create unique index idx_payslips_company_unique
  on public.payslips (company_id, employee_id, year, month, contract_period_id)
  nulls not distinct;

-- « Nouveau contrat » qui commence le mois où le précédent finit : le bulletin
-- et les variables de ce mois, à contrat nul, passent au contrat rangé. En une
-- transaction : sans ce marquage, le premier bulletin du nouveau contrat
-- remplacerait celui de l'ancien. Refuse s'il n'y a aucun bulletin à marquer
-- (le bulletin du dernier mois est exigé avant le nouveau contrat).
create or replace function public.ranger_mois_partage(
  p_period uuid,
  p_employee uuid,
  p_year integer,
  p_month integer
) returns jsonb
language plpgsql
set search_path = public
as $$
declare
  n_bulletins integer;
  n_variables integer;
begin
  update public.payslips
     set contract_period_id = p_period
   where employee_id = p_employee
     and year = p_year
     and month = p_month
     and contract_period_id is null;
  get diagnostics n_bulletins = row_count;
  if n_bulletins = 0 then
    raise exception 'Aucun bulletin de %/% à ranger avec le contrat précédent.',
      lpad(p_month::text, 2, '0'), p_year;
  end if;

  update public.monthly_inputs
     set contract_period_id = p_period
   where employee_id = p_employee
     and year = p_year
     and month = p_month
     and contract_period_id is null;
  get diagnostics n_variables = row_count;

  return jsonb_build_object('bulletins', n_bulletins, 'variables', n_variables);
end;
$$;

revoke all on function public.ranger_mois_partage(uuid, uuid, integer, integer)
  from public, anon, authenticated;
grant execute on function public.ranger_mois_partage(uuid, uuid, integer, integer)
  to service_role;
