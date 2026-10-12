-- Maintien de salaire pendant les congés de maternité, de paternité et
-- d'adoption : un réglage par société, ÉTEINT par défaut.
--
-- Ces congés se saisissent désormais à l'écran avec leur propre type d'arrêt
-- (maternite, paternite, adoption) au lieu de « maladie simple ». Le maintien
-- n'y est pas une obligation légale (Code du travail L1226-1 vise la maladie
-- et l'accident) : il dépend de la convention. Éteint, le congé est retenu,
-- sans carence ni maintien, et les indemnités journalières sont versées au
-- salarié par la caisse (ce que faisait Quadra chez Comitech). Allumé, le
-- salaire est maintenu à 100 % dès le premier jour, sous la condition
-- d'ancienneté du maintien.
--
-- Aucune donnée n'est réécrite : la colonne vaut false partout.
-- À appliquer AVANT de déployer le code qui l'écrit : sans elle,
-- l'enregistrement des réglages de maintien échoue (colonne inconnue).
-- Idempotente.

alter table public.company_maintenance_settings
  add column if not exists maintain_parental_leave boolean not null default false;

comment on column public.company_maintenance_settings.maintain_parental_leave is
  'Maintien de salaire à 100 % pendant les congés de maternité, de paternité et d''adoption (convention). Éteint : congé retenu, IJ versées au salarié.';
