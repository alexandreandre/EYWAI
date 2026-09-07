-- Demi-journée de congé payé (demande RH Gaëlle du 04/09/2026).
--
-- 1) jours_payes passe d'integer à numeric : une demande avec demi-journées
--    paie en pas de 0,5 (2,5 jours). C'est aussi la correction de fond du bug
--    22P02 du 03/09 (un float écrit dans une colonne integer).
-- 2) demi_journees : {"2026-09-14": "matin"} — un jour absent du dict est un
--    jour plein. NULL = demande sans demi-journée (rétrocompat totale, aucun
--    backfill nécessaire).
--
-- Idempotente : re-typer une colonne déjà numeric et ADD COLUMN IF NOT EXISTS
-- sont sans effet au rejeu.
ALTER TABLE public.absence_requests
  ALTER COLUMN jours_payes TYPE numeric(6,2);

ALTER TABLE public.absence_requests
  ADD COLUMN IF NOT EXISTS demi_journees jsonb;

COMMENT ON COLUMN public.absence_requests.demi_journees IS
  'Demi-journées de CP : {"YYYY-MM-DD": "matin"|"apres_midi"}. Jour absent = jour plein. NULL = aucune.';
