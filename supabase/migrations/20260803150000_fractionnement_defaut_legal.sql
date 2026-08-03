-- Fractionnement CP : méthode légale par défaut, exclusion des cadres réglable.
--
-- La méthode « MBC » était le calcul par défaut des sept sociétés alors qu'elle
-- reproduit le tableur d'une seule d'entre elles et réclame une saisie RH que
-- rien ne permet de reconstituer. La méthode légale se calcule à partir des
-- congés réellement posés.
--
-- L'exclusion des cadres au forfait-jours était figée dans le code : c'est un
-- usage d'entreprise, pas une règle de droit. On la remonte en réglage, avec
-- le comportement actuel comme valeur par défaut.
--
-- Aucune société n'ayant de ligne de paramétrage à ce jour, ces changements ne
-- modifient aucun droit existant.

alter table public.company_cp_fractionnement_settings
  add column if not exists exclude_forfait_jours boolean not null default true;

comment on column public.company_cp_fractionnement_settings.exclude_forfait_jours is
  'Exclut les cadres au forfait-jours du fractionnement (usage d''entreprise).';

alter table public.company_cp_fractionnement_settings
  alter column calculation_method set default 'legal';
