-- Repos compensateur pris en HEURES (demande RH du 07/09/2026).
--
-- heures_par_jour : {"2026-09-14": 2.0} — nombre d'heures de repos prises ce
-- jour-là. Jour absent du dict = journée entière (convertie via le réglage
-- société hours_per_rest_day). Réservé aux demandes repos_compensateur : la
-- journée reste TRAVAILLÉE au calendrier (aucune projection), seul le
-- compteur est débité — c'est la pratique paie (« je pars 2 h plus tôt »).
--
-- Idempotente : ADD COLUMN IF NOT EXISTS.
ALTER TABLE public.absence_requests
  ADD COLUMN IF NOT EXISTS heures_par_jour jsonb;

COMMENT ON COLUMN public.absence_requests.heures_par_jour IS
  'Repos compensateur en heures : {"YYYY-MM-DD": heures}. Jour absent = journée entière. NULL = demande en jours.';
