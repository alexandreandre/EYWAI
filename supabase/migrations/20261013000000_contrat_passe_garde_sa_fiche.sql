-- [D4, vidéo H] Après « Nouveau contrat », les mois de l'ancien contrat restaient
-- sans correction possible : la fiche décrit le nouveau contrat (entrée, type,
-- fin, durée…), et un bulletin validé de l'ancien ne se régénérait plus, donc ne
-- se supprimait plus.
--
-- Le contrat rangé garde désormais les champs de la fiche qu'il avait (ceux que
-- « Nouveau contrat » remplace) : un mois de ce contrat se recalcule sur eux.
-- Colonne vide pour un contrat passé saisi à la main : ses mois restent refusés.
-- Aucune donnée existante ne change.
ALTER TABLE public.employee_contract_periods
  ADD COLUMN IF NOT EXISTS fiche jsonb;

COMMENT ON COLUMN public.employee_contract_periods.fiche IS
  'Champs de la fiche du salarié propres à ce contrat, rangés par « Nouveau contrat » (type, entrée, fin, durée, poste, ancienneté…). Un mois de ce contrat se recalcule sur eux.';
