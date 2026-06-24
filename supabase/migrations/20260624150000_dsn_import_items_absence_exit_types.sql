-- Étend les types d'items DSN staging (absences et sorties historiques).

ALTER TABLE public.dsn_import_items
    DROP CONSTRAINT IF EXISTS dsn_import_items_item_type_check;

ALTER TABLE public.dsn_import_items
    ADD CONSTRAINT dsn_import_items_item_type_check
    CHECK (item_type IN (
        'group',
        'establishment',
        'employee',
        'cumul',
        'collective_agreement',
        'absence',
        'exit'
    ));
