-- Enrichissement data prime d'ancienneté IDCC 3248 (métallurgie)
-- Merge idempotent dans convention_collective_rules.rules.prime_anciennete

UPDATE convention_collective_rules
SET rules = jsonb_set(
  COALESCE(rules, '{}'::jsonb),
  '{prime_anciennete}',
  COALESCE(rules->'prime_anciennete', '{}'::jsonb)
    || jsonb_build_object(
      'eligibilite', jsonb_build_object(
        'min_annees', 3,
        'statuts_exclus', '["Cadre"]'::jsonb,
        'classe_max_taux', 10
      ),
      'prorata', jsonb_build_object(
        'enabled', true,
        'mode', 'heures_contrat',
        'inclure_heures_sup', true,
        'maladie_si_maintien', true,
        'sans_pointage_policy', 'plein_mois'
      ),
      'valeurs_point', jsonb_build_array(
        jsonb_build_object(
          'zone_type', 'national',
          'zone_libelle', 'National — valeur du point',
          'departements', '[]'::jsonb,
          'valeur', 5.83
        ),
        jsonb_build_object(
          'zone_type', 'departemental',
          'zone_libelle', 'Deux-Sèvres — valeur du point',
          'departements', '["79"]'::jsonb,
          'valeur', 5.70
        )
      )
    ),
  true
),
updated_at = NOW()
WHERE idcc IN ('3248', '03248');
