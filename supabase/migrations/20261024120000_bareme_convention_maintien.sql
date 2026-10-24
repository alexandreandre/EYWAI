-- Barème de la convention du maintien de salaire, par société
-- (conception du 24/10/2026).
--
--   null              : les réglages manuels, le calcul d'avant ;
--   'plasturgie_0292' : les paliers de la plasturgie (avenant non-cadres du
--                       15/05/1991, art. 13 ; accord cadres du 17/12/1992, art. 5).
-- Aucune ligne existante n'est touchée : la colonne naît nulle.
-- Rejouable : la colonne n'est ajoutée que si elle manque, la contrainte est
-- reposée à l'identique.
-- À appliquer AVANT de déployer le code qui l'écrit : sans elle,
-- l'enregistrement des réglages de maintien échoue (colonne inconnue).

alter table public.company_maintenance_settings
  add column if not exists bareme_convention text;

alter table public.company_maintenance_settings
  drop constraint if exists company_maintenance_settings_bareme_convention_check;

alter table public.company_maintenance_settings
  add constraint company_maintenance_settings_bareme_convention_check
  check (bareme_convention is null or bareme_convention in ('plasturgie_0292'));

comment on column public.company_maintenance_settings.bareme_convention is
  'Barème de la convention du maintien : null, les réglages manuels ; plasturgie_0292, les paliers de la plasturgie.';
