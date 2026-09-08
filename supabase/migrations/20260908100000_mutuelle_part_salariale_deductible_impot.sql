-- Part salariale de mutuelle : déductible ou non du net imposable.
--
-- Constat sur GIRERD (Colorplast, juillet 2026), bulletin EYWAI comparé à celui
-- du cabinet : net imposable 2 570,73 € chez nous contre 2 668,88 € chez eux,
-- soit exactement le complément « GAN Famille » (98,13 €). Les deux prélèvent
-- la même somme au salarié — le net à payer avant impôt est identique à 4
-- centimes près — mais nous la déduisons du revenu imposable et pas eux. Le PAS
-- s'en trouvait minoré de 4,22 €/mois.
--
-- Le cabinet a raison : les cotisations salariales finançant les garanties
-- frais de santé sont exclues de la déductibilité (art. 83, 1° quater du CGI,
-- exclusion introduite par la loi de finances 2014).
--
-- Le défaut reste `true`, donc AUCUN bulletin existant ne bouge. Le drapeau
-- n'est posé que sur les compléments « Famille » sans part patronale, seul cas
-- où l'écart a été constaté contre un bulletin réel. Les mutuelles « Autre …
-- / 0,00 € » (Cartol, LEWIS, MAJI, Mont Blanc, Zone 404 — une centaine de
-- salariés) posent la même question, mais aucune n'a été recoupée avec un
-- bulletin du cabinet : arbitrage ouvert, à ne pas trancher à l'aveugle.
--
-- Idempotent : ADD COLUMN IF NOT EXISTS, et l'UPDATE ne touche que les lignes
-- pas encore marquées.

ALTER TABLE company_mutuelle_types
  ADD COLUMN IF NOT EXISTS part_salariale_deductible_impot boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN company_mutuelle_types.part_salariale_deductible_impot IS
  'False = la part salariale ne réduit pas le net imposable (frais de santé, art. 83 1° quater CGI). Défaut true.';

UPDATE company_mutuelle_types
SET part_salariale_deductible_impot = false,
    updated_at = now()
WHERE libelle ILIKE '%famille%'
  AND montant_patronal = 0
  AND part_salariale_deductible_impot IS DISTINCT FROM false;
