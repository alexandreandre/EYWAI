-- Arrêt sans subrogation : déduire ou non du maintien les IJSS des jours
-- maintenus, par société (conception du 23/10/2026).
--
-- Sans subrogation, la CPAM verse les IJSS directement au salarié.
--   true  : Martine ne verse que le complément, IJSS des jours maintenus et
--           indemnisés déduites (règle légale, Code du travail D1226-5) ;
--   false : le salaire garanti en entier, le calcul d'avant ce réglage.
-- Les sociétés qui ont déjà une ligne gardent leur calcul (false) ; une ligne
-- créée ensuite prend la règle légale (true).
--
-- Rejouable sans erreur et sans écraser un choix : la colonne naît sans
-- défaut, les lignes existantes (alors à null) passent à false, puis le défaut
-- true et le not null sont posés. Un second passage ne trouve plus de null.
-- À appliquer AVANT de déployer le code qui l'écrit : sans elle,
-- l'enregistrement des réglages de maintien échoue (colonne inconnue).

alter table public.company_maintenance_settings
  add column if not exists deduire_ijss_sans_subrogation boolean;

update public.company_maintenance_settings
  set deduire_ijss_sans_subrogation = false
  where deduire_ijss_sans_subrogation is null;

alter table public.company_maintenance_settings
  alter column deduire_ijss_sans_subrogation set default true;

alter table public.company_maintenance_settings
  alter column deduire_ijss_sans_subrogation set not null;

comment on column public.company_maintenance_settings.deduire_ijss_sans_subrogation is
  'Arrêt sans subrogation : true, le maintien ne verse que le complément (IJSS des jours maintenus déduites) ; false, le salaire garanti en entier.';
