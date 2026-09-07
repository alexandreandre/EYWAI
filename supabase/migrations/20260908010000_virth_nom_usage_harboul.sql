-- MAJI : nom d'usage de Marie VIRTH = HARBOUL (liste du personnel fournie
-- par la déclarante le 08/09/2026 ; la DSN n'avait pas porté la rubrique
-- S21.G00.30.003 pour elle). Ciblage par id (identique prod/test, la base
-- de test est une copie de la prod).
--
-- Idempotente : le garde IS NULL ne réécrit jamais une valeur posée depuis.
UPDATE employees
SET nom_usage = 'HARBOUL'
WHERE id = '33656570-42c8-4d03-ab3e-700e2926af04'
  AND (nom_usage IS NULL OR nom_usage = '');
