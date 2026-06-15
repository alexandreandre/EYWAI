-- Import DSN : statut 'committing' pour reprise de commit en arrière-plan
-- Permet au front de restaurer l'état d'un import en cours après un rechargement de page.

ALTER TABLE public.dsn_import_batches
    DROP CONSTRAINT IF EXISTS dsn_import_batches_status_check;

ALTER TABLE public.dsn_import_batches
    ADD CONSTRAINT dsn_import_batches_status_check
    CHECK (status IN ('parsed', 'previewed', 'committing', 'committed', 'failed'));

COMMENT ON COLUMN public.dsn_import_batches.status IS
    'Cycle de vie : parsed -> previewed -> committing -> committed | failed.';
