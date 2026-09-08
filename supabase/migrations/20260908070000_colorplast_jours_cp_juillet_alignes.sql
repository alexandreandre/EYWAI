-- Colorplast, juillet 2026 : garantir que les jours couverts par une demande
-- de CP VALIDÉE sont bien typés « conges_payes » au calendrier (GAUTHERON
-- 13 et 21/07, ESPINOSA 13/07 — retours service paie 07/09). Sans ce type,
-- le bulletin régénéré n'affiche pas la ligne CP datée : la projection a eu
-- lieu à la validation, mais des retouches (imports de pointages, éditions)
-- ont pu retyper les jours depuis.
--
-- Auto-adaptative par environnement : le retypage n'a lieu QUE si une
-- demande validée couvre la date pour ce salarié (les demandes n'existent
-- que sur la base de test → aucun effet en production). Idempotente : un
-- jour déjà conges_payes/origine=absence est laissé tel quel.
UPDATE employee_schedules es
SET planned_calendar = jsonb_set(
  es.planned_calendar,
  '{calendrier_prevu}',
  (
    SELECT jsonb_agg(
      CASE
        WHEN EXISTS (
          SELECT 1
          FROM absence_requests ar
          WHERE ar.employee_id = es.employee_id
            AND ar.type = 'conge_paye'
            AND ar.status = 'validated'
            AND make_date(es.year, es.month, (elem->>'jour')::int)
                = ANY (ar.selected_days)
        )
        AND NOT (
          elem->>'type' = 'conges_payes'
          AND elem->>'origine' = 'absence'
        )
        THEN jsonb_build_object(
          'jour', (elem->>'jour')::int,
          'type', 'conges_payes',
          'manuel', true,
          'heures_prevues', 0,
          'origine', 'absence'
        )
        ELSE elem
      END
      ORDER BY ord
    )
    FROM jsonb_array_elements(es.planned_calendar->'calendrier_prevu')
      WITH ORDINALITY AS t(elem, ord)
  )
)
WHERE es.year = 2026 AND es.month = 7
  AND es.employee_id IN (
    '1c4cc8b6-5f55-4d71-bba5-5acb8fa3efd2',  -- GAUTHERON Marion
    '53c92e83-4a1a-4214-b30d-577cd1ab9d2d'   -- ESPINOSA Anthony
  )
  AND jsonb_typeof(es.planned_calendar->'calendrier_prevu') = 'array';
