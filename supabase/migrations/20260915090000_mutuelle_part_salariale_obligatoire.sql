-- Part salariale de mutuelle : cotisation obligatoire ou extension facultative.
--
-- Le montant net social (arrêté du 31/01/2023) retranche des sommes versées au
-- salarié les seules cotisations et contributions sociales OBLIGATOIRES. La
-- couverture collective frais de santé en est une : l'employeur la finance pour
-- moitié au moins (art. L911-7 du code de la sécurité sociale). Une extension
-- facultative intégralement à la charge du salarié — le complément « Famille »
-- — n'en est pas une : elle se retient après le net social, sur le net à payer.
--
-- Constat sur Colorplast, bulletins du cabinet de janvier à juillet 2026. Pour
-- les trois salariés qui paient le complément « GAN Famille », la relation
--
--     montant net social − net à payer avant impôt − acompte = 98,13
--
-- se vérifie sur les 21 bulletins concernés, et vaut zéro pour les salariés
-- sans complément. EYWAI retranchait la retenue des deux : Espinosa janvier
-- 2026, montant net social 2 440,05 € au lieu de 2 538,18 €.
--
-- C'est la seule donnée du rapprochement de janvier qui sorte de l'entreprise :
-- le montant net social est transmis aux organismes sociaux et sert au calcul
-- des prestations (RSA, prime d'activité).
--
-- Le défaut reste `true`, donc AUCUN bulletin existant ne bouge. Le drapeau
-- n'est posé que sur les compléments « Famille » sans part patronale, seul cas
-- recoupé avec des bulletins réels — mêmes critères que pour
-- `part_salariale_deductible_impot` (migration 20260908100000). Les mutuelles
-- « Autre … / 0,00 € » des autres sociétés du groupe posent la même question
-- sans référence cabinet : arbitrage ouvert, à ne pas trancher à l'aveugle.
--
-- Idempotent : ADD COLUMN IF NOT EXISTS, et l'UPDATE ne touche que les lignes
-- pas encore marquées.

ALTER TABLE company_mutuelle_types
  ADD COLUMN IF NOT EXISTS part_salariale_obligatoire boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN company_mutuelle_types.part_salariale_obligatoire IS
  'False = adhésion facultative : la part salariale ne réduit pas le montant net social (arrêté du 31/01/2023, cotisations obligatoires seules). Elle reste prélevée sur le net à payer. Défaut true.';

UPDATE company_mutuelle_types
SET part_salariale_obligatoire = false,
    updated_at = now()
WHERE libelle ILIKE '%famille%'
  AND montant_patronal = 0
  AND part_salariale_obligatoire IS DISTINCT FROM false;
