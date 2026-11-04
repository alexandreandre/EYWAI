-- Index manquants (audit de modernisation du 03/11/2026, R4 geste 6 ; temps 2, point 5).
-- Vérifiés le 04/11/2026 sur la base de test, en lecture seule (pg_stat_statements,
-- index existants, volumes). Aucune donnée ne change ; rejouable sans effet.
-- Appliquée par deploy-test-env.yml dans une seule transaction : pas de
-- CONCURRENTLY. Le plus gros index (schedule_import_items) se construit en
-- quelques secondes, pendant lesquelles les imports de pointages attendent.

-- Garde de reprise à chaque génération : « ce salarié a-t-il un lot DSN validé ? »
-- (item_type, target_id, status). Aucun index sur target_id : 678 appels,
-- 76 ms en moyenne, 2,3 s au pire, lecture de toute la table (21 Mo).
-- 1 319 lignes sur 16 243 ont un target_id : index partiel.
CREATE INDEX IF NOT EXISTS idx_dsn_import_items_target
    ON public.dsn_import_items (target_id, item_type)
    WHERE target_id IS NOT NULL;

-- Absences d'un salarié, des plus récentes aux plus anciennes : plus de 360 000
-- appels (employee_id = … ORDER BY created_at DESC), chacun relit toute la table.
-- Seul index sur employee_id : partiel (pièce jointe), inutilisable ici.
CREATE INDEX IF NOT EXISTS idx_absence_requests_employee_created
    ON public.absence_requests (employee_id, created_at DESC);

-- Clé étrangère employee_id → employees ON DELETE SET NULL sans index utilisable
-- (l'index existant commence par batch_id) : supprimer une fiche salarié lit les
-- 126 Mo de la table (781 850 lignes). 639 227 lignes ont un employee_id.
CREATE INDEX IF NOT EXISTS idx_schedule_import_items_employee_seul
    ON public.schedule_import_items (employee_id)
    WHERE employee_id IS NOT NULL;

-- Non retenus après vérification :
-- - trial_periods (employee_id) : 6 lignes, une page ; un index ne sert à rien.
-- - monthly_inputs (contract_period_id) et payslips (contract_period_id) : la
--   colonne est vide partout (0 ligne renseignée) ; les lectures du mois filtrent
--   d'abord le salarié et la période, déjà indexés.
