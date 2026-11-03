-- Barème de la métallurgie (IDCC 3248) ajouté au choix du maintien de salaire
-- (conception du 03/11/2026). La contrainte accepte désormais :
--
--   null              : les réglages manuels, le calcul d'avant ;
--   'plasturgie_0292' : les paliers de la plasturgie ;
--   'metallurgie_3248': les paliers de la métallurgie (art. 91.1.1 à 91.1.3,
--                       convention du 7 février 2022).
-- Aucune ligne existante n'est touchée. Rejouable : la contrainte est reposée
-- à l'identique. À appliquer AVANT de déployer le code qui écrit la valeur.

alter table public.company_maintenance_settings
  drop constraint if exists company_maintenance_settings_bareme_convention_check;

alter table public.company_maintenance_settings
  add constraint company_maintenance_settings_bareme_convention_check
  check (bareme_convention is null or bareme_convention in ('plasturgie_0292', 'metallurgie_3248'));

comment on column public.company_maintenance_settings.bareme_convention is
  'Barème de la convention du maintien : null, les réglages manuels ; plasturgie_0292 ; metallurgie_3248.';
