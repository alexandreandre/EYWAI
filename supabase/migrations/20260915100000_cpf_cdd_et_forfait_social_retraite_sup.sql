-- Deux contributions patronales absentes du calcul, relevées sur les bulletins
-- des cabinets.
--
-- 1. CONTRIBUTION CPF-CDD (1 % de la rémunération des titulaires de CDD,
--    art. L6331-6 du code du travail, code DSN 129).
--
--    Les cabinets la facturent bien, et uniquement aux CDD. Sur Colorplast
--    (Quadra), les 43 bulletins de janvier à juillet 2026 donnent 1,646 % du
--    brut en contributions patronales pour les sept CDI, et 2,646 % pour les
--    deux seuls CDD, Demory et Fuckar. Sur Mont Blanc Composite (Cegid), mai
--    2026 : 4,946 % pour 67 salariés, 5,946 % pour sept — Askari, Isak,
--    Lamotte, Mirzada, Nuhu, Safi, Tarakhil, tous en CDD. Deux sociétés, deux
--    cabinets, exactement un point d'écart, et le CDD comme seul discriminant.
--
--    L'apprentissage, la professionnalisation et les stages en sont exclus :
--    le moteur les écarte (`est_cdd`).
--
-- 2. FORFAIT SOCIAL 20 % SUR LA RETRAITE SUPPLÉMENTAIRE de Girerd, le seul
--    cadre de Colorplast : 19,00 € sur 94,98 € de part patronale, présent sur
--    tous ses bulletins de 2026. Contrairement au forfait social de 8 % sur la
--    prévoyance, celui-ci ne connaît pas d'exonération des moins de 11
--    salariés.
--
-- Ce qui n'est PAS fait ici, faute de réponse : le taux de formation
-- professionnelle et le forfait social de 8 % sur la prévoyance dépendent tous
-- deux de l'effectif de Colorplast, et les deux lignes de Quadra se
-- contredisent — 0,55 % de formation suppose moins de 11 salariés, le forfait
-- social de 8 % suppose 11 ou plus. Question posée à Gaëlle.
--
-- Idempotent.

-- 1. La cotisation au catalogue national.
UPDATE payroll_config
SET config_data = jsonb_set(
      config_data,
      '{cotisations}',
      (config_data->'cotisations') || jsonb_build_object(
        'id', 'cpf_cdd',
        'libelle', 'Contribution CPF des titulaires de CDD',
        'base', 'brut',
        'salarial', NULL,
        'patronal', 0.01
      )
    ),
    created_at = created_at
WHERE config_key = 'cotisations'
  AND is_active
  AND NOT EXISTS (
    SELECT 1 FROM jsonb_array_elements(config_data->'cotisations') c
    WHERE c->>'id' = 'cpf_cdd'
  );

-- 2. Le taux de forfait social sur la ligne de retraite supplémentaire du cadre.
UPDATE employees e
SET specificites_paie = jsonb_set(
      e.specificites_paie,
      '{retraite_sup,lignes_specifiques}',
      (
        SELECT jsonb_agg(
          CASE WHEN l ? 'forfait_social' THEN l
               ELSE l || jsonb_build_object('forfait_social', 0.20) END
        )
        FROM jsonb_array_elements(e.specificites_paie->'retraite_sup'->'lignes_specifiques') l
      )
    ),
    updated_at = now()
FROM companies c
WHERE c.id = e.company_id
  AND c.company_name = 'Colorplast'
  AND e.specificites_paie->'retraite_sup'->'lignes_specifiques' IS NOT NULL
  AND jsonb_array_length(e.specificites_paie->'retraite_sup'->'lignes_specifiques') > 0
  AND NOT (e.specificites_paie->'retraite_sup'->'lignes_specifiques'->0 ? 'forfait_social');
