-- Complète les règles CCN plasturgie (IDCC 0292) avec la prime d'ancienneté officielle.
-- Source : accord du 28 juin 2011 (barème par paliers sur le salaire de base).

UPDATE convention_collective_rules
SET rules = jsonb_set(
    rules,
    '{prime_anciennete}',
    '{
      "bareme": [
        {"annees_min": 3, "taux": 0.024},
        {"annees_min": 6, "taux": 0.048},
        {"annees_min": 9, "taux": 0.072},
        {"annees_min": 12, "taux": 0.096},
        {"annees_min": 15, "taux": 0.12}
      ],
      "base_de_calcul": {
        "methode": "pourcentage_salaire_de_base",
        "valeur": 1.0
      }
    }'::jsonb,
    true
)
WHERE idcc = '0292'
  AND (rules->'prime_anciennete') IS NULL;
