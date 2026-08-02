-- Situation de restauration d'une prime de type panier/repas, qui détermine le
-- plafond d'exonération URSSAF applicable (7,50 € sur le lieu de travail,
-- 10,40 € hors locaux sans restaurant, 21,40 € hors locaux avec restaurant).
--
-- NULL = non déclaré : le moteur retient alors le plafond le plus élevé plutôt
-- que de réintégrer à tort des repas hors locaux légitimes (paniers chauffeur
-- à 15 €). Le durcissement se fait entreprise par entreprise, en déclarant.
--
-- Déclarée sur le catalogue, recopiée sur la saisie au moment de la génération
-- — même schéma que export_code, ce qui évite une jointure au calcul du
-- bulletin (payslip_generator lit monthly_inputs en select *).
alter table public.company_bonus_types
  add column if not exists situation_repas text;

alter table public.monthly_inputs
  add column if not exists situation_repas text;

alter table public.company_bonus_types
  drop constraint if exists company_bonus_types_situation_repas_check;

alter table public.company_bonus_types
  add constraint company_bonus_types_situation_repas_check
  check (
    situation_repas is null
    or situation_repas in (
      'sur_lieu_travail',
      'hors_locaux_sans_restaurant',
      'hors_locaux_avec_restaurant'
    )
  );

alter table public.monthly_inputs
  drop constraint if exists monthly_inputs_situation_repas_check;

alter table public.monthly_inputs
  add constraint monthly_inputs_situation_repas_check
  check (
    situation_repas is null
    or situation_repas in (
      'sur_lieu_travail',
      'hors_locaux_sans_restaurant',
      'hors_locaux_avec_restaurant'
    )
  );

comment on column public.company_bonus_types.situation_repas is
  'Situation de restauration déterminant le plafond d''exonération. NULL = non déclaré, repli sur le plafond le plus élevé.';

comment on column public.monthly_inputs.situation_repas is
  'Recopie de company_bonus_types.situation_repas à la génération. NULL = non déclaré.';
