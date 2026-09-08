-- COTTE Léo (Colorplast) : régularisation de +4 h supplémentaires de JUIN,
-- payées sur le mois de paie JUILLET (feuille « DETAIL HEURES SUP 07-2026 »
-- du service paie : « + 4H EN JUIN FAIRE REGUL »).
--
-- Mécanisme : saisie mensuelle avec payroll_quantity — le générateur la
-- détecte par son libellé (« heures sup », sans « 50 » → majoration 25 %,
-- sans « struct ») et l'ajoute aux HS conjoncturelles du bulletin avec les
-- bonnes cotisations/exonérations ; la ligne est exclue des primes (pas de
-- ligne fantôme à 0 €). Les saisies mensuelles se lisent au mois de PAIE,
-- la fenêtre d'arrêté ne s'applique pas.
-- Idempotente (garde NOT EXISTS) ; mêmes données voulues en prod et en test.
INSERT INTO monthly_inputs (
  employee_id, company_id, year, month,
  name, description, amount,
  is_socially_taxed, is_taxable, payroll_quantity
)
SELECT
  'e6d1588d-6b4a-4ff4-992f-279cdadd3c46',  -- COTTE Léo
  'dbe2b9f5-44dd-41bc-a625-36ed33d160f7',  -- Colorplast
  2026, 7,
  'Heures sup 25 % — régularisation juin',
  'Régule +4 h de juin (feuille service paie du 07/09/2026)',
  0,
  true, true, 4
WHERE NOT EXISTS (
  SELECT 1 FROM monthly_inputs
  WHERE employee_id = 'e6d1588d-6b4a-4ff4-992f-279cdadd3c46'
    AND year = 2026 AND month = 7
    AND payroll_quantity IS NOT NULL
    AND name ILIKE '%régularisation juin%'
);
