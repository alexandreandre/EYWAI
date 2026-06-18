-- Supprime le groupe « Groupe Lewis » créé automatiquement par un ancien import DSN.
-- Conteneur organisationnel mono-établissement devenu inutile (is_scaffold côté import).

DO $$
DECLARE
    g record;
BEGIN
    FOR g IN
        SELECT id, group_name
        FROM public.company_groups
        WHERE group_name = 'Groupe Lewis'
           OR (
               group_name ILIKE 'Groupe Lewis%'
               AND description ILIKE 'Conteneur EYWAI%'
           )
    LOOP
        UPDATE public.companies
        SET
            group_id = NULL,
            group_display_order = NULL
        WHERE group_id = g.id;

        DELETE FROM public.company_groups
        WHERE id = g.id;

        RAISE NOTICE 'Groupe DSN supprimé : % (%)', g.group_name, g.id;
    END LOOP;
END $$;
