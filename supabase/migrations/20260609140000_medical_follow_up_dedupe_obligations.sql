-- Supprime les doublons actifs d'obligations de suivi médical (même salarié, type, déclencheur, échéance).
WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY employee_id, visit_type, trigger_type, due_date
      ORDER BY created_at NULLS LAST, id
    ) AS rn
  FROM medical_follow_up_obligations
  WHERE status IN ('a_faire', 'planifiee')
)
UPDATE medical_follow_up_obligations AS o
SET
  status = 'annulee',
  justification = COALESCE(NULLIF(o.justification, ''), 'Doublon supprimé')
FROM ranked AS r
WHERE o.id = r.id
  AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS medical_follow_up_obligations_active_uniq
  ON medical_follow_up_obligations (employee_id, visit_type, trigger_type, due_date)
  WHERE status IN ('a_faire', 'planifiee');
