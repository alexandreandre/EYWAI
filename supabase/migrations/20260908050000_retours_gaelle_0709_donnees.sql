-- Retours Gaëlle 07/09 (soir) — corrections de DONNÉES Colorplast/Comitech.
-- Ciblage par id (identiques prod/test : la base de test est une copie).
-- Chaque bloc est idempotent (gardes sur l'état à corriger).

-- 1) GAUTHERON Marion, 30/06/2026 : la reprise DSN avait posé un jour
--    « absence non rémunérée » artificiel (net-neutre pour juin, mois miroir),
--    mais la fenêtre de paie de JUILLET (22/06→26/07) le ramasse et crée une
--    retenue fictive. Un mardi normal pour elle = travail 8,5 h.
--    (En prod le jour avait déjà été retypé travail mais à 7,0 h ; sur test
--    c'est encore l'absence de reprise — la reconstruction couvre les deux.)
UPDATE employee_schedules
SET planned_calendar = jsonb_set(
  planned_calendar,
  '{calendrier_prevu}',
  (
    SELECT jsonb_agg(
      CASE WHEN (elem->>'jour')::int = 30
        THEN jsonb_build_object(
          'jour', 30,
          'type', 'travail',
          'manuel', true,
          'heures_prevues', 8.5
        )
        ELSE elem
      END
      ORDER BY ord
    )
    FROM jsonb_array_elements(planned_calendar->'calendrier_prevu')
      WITH ORDINALITY AS t(elem, ord)
  )
)
WHERE employee_id = '1c4cc8b6-5f55-4d71-bba5-5acb8fa3efd2'
  AND year = 2026 AND month = 6
  AND jsonb_typeof(planned_calendar->'calendrier_prevu') = 'array';

-- 2) Mutuelle « Famille » (répartition GAN actée 2024 : 156,60 € au total,
--    part salariale supplémentaire 98,13 €, part patronale 0 — elle S'AJOUTE
--    à la formule Isolé 29,24/29,23 que le salarié conserve).
--    Colorplast n'avait pas la formule ; Comitech l'avait à 98,12 (centime).
INSERT INTO company_mutuelle_types (
  company_id, libelle, montant_salarial, montant_patronal,
  part_patronale_soumise_a_csg, is_active, statut_categoriel, source, note
)
SELECT
  'dbe2b9f5-44dd-41bc-a625-36ed33d160f7',
  'GAN Famille 2026 (EMU3+SMU2)',
  98.13, 0.0, true, true, 'tous', 'manual',
  'Complément Famille : s''ajoute à la formule Isolé (GAN, répartition actée '
  || '2024 — 156,60 € au total, part salariale 98,13 €). Source : service '
  || 'paie, 07/09/2026.'
WHERE NOT EXISTS (
  SELECT 1 FROM company_mutuelle_types
  WHERE company_id = 'dbe2b9f5-44dd-41bc-a625-36ed33d160f7'
    AND libelle = 'GAN Famille 2026 (EMU3+SMU2)'
);

UPDATE company_mutuelle_types
SET montant_salarial = 98.13
WHERE id = 'e9e8980a-b283-4b4a-b892-77c53b1d45a5'
  AND montant_salarial = 98.12;

-- 3) BUGNY Michel : compteur repos compensateur à ZÉRO (demande Gaëlle
--    07/09). En prod les crédits sont déjà tous à 0 (no-op) ; la base de
--    test porte encore d'anciens crédits COR — cette remise à zéro les
--    efface sans toucher aux autres salariés.
UPDATE repos_compensateur_credits
SET heures = 0.0, jours = 0.0
WHERE employee_id = 'f8e431a3-350b-471e-9b78-9bc9fd1ce8b9';

-- 4) GIRERD Fabrice (Cadre, Colorplast) : l'import DSN lui avait posé la
--    ligne de prévoyance NON-CADRE (0,465/0,465). Barème GAN cadre (feuille
--    de répartition 2026) : TA 2,19 % = 1,825 pat + 0,365 sal ;
--    TB 2,85 % = 1,710 pat + 1,140 sal — même modèle que les cadres Comitech.
UPDATE employees
SET specificites_paie = jsonb_set(
  specificites_paie,
  '{prevoyance,lignes_specifiques}',
  '[
    {"id": "prev_ta", "base": "brut_plafonne",
     "libelle": "Prévoyance cadre TA (GAN)",
     "patronal": 0.01825, "salarial": 0.00365},
    {"id": "prev_tb", "base": "tranche_2",
     "libelle": "Prévoyance cadre TB (GAN)",
     "patronal": 0.01710, "salarial": 0.01140}
  ]'::jsonb
)
WHERE id = 'bceb467d-d0ac-454a-9084-4b20d3cd0e9e'
  AND specificites_paie->'prevoyance'->'lignes_specifiques'
      @> '[{"id": "prevoyance_dsn"}]'::jsonb;
