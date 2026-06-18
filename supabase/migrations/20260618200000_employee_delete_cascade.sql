-- Suppression employé : aligner les FK vers employees (et chaînes enfants) sur ON DELETE CASCADE.
-- Les colonnes manager / remplacement restent en SET NULL.

CREATE OR REPLACE FUNCTION public._eywai_recreate_fk_cascade(
    p_schema text,
    p_table text,
    p_constraint text,
    p_column text,
    p_ref_schema text,
    p_ref_table text,
    p_ref_column text DEFAULT 'id'
) RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE format(
        'ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I',
        p_schema, p_table, p_constraint
    );
    EXECUTE format(
        'ALTER TABLE %I.%I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES %I.%I(%I) ON DELETE CASCADE',
        p_schema, p_table, p_constraint, p_column, p_ref_schema, p_ref_table, p_ref_column
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END;
$$;

-- 1) FK existantes vers employees → CASCADE (sauf colonnes à conserver en SET NULL)
DO $$
DECLARE
    r RECORD;
    set_null_cols text[] := ARRAY[
        'manager_employee_id',
        'replacing_employee_id',
        'original_employee_id',
        'manager_id'
    ];
BEGIN
    FOR r IN
        SELECT
            tc.table_schema,
            tc.table_name,
            tc.constraint_name,
            kcu.column_name,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.referential_constraints AS rc
            ON tc.constraint_name = rc.constraint_name
            AND tc.table_schema = rc.constraint_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON rc.unique_constraint_name = ccu.constraint_name
            AND rc.unique_constraint_schema = ccu.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
            AND ccu.table_schema = 'public'
            AND ccu.table_name = 'employees'
            AND kcu.column_name <> ALL (set_null_cols)
            AND rc.delete_rule IS DISTINCT FROM 'CASCADE'
    LOOP
        PERFORM public._eywai_recreate_fk_cascade(
            r.table_schema,
            r.table_name,
            r.constraint_name,
            r.column_name,
            'public',
            'employees',
            'id'
        );
    END LOOP;
END;
$$;

-- 2) Chaînes enfants (avances, saisies, sorties…) → CASCADE vers le parent
DO $$
DECLARE
    r RECORD;
    parent_tables text[] := ARRAY[
        'salary_advances',
        'salary_seizures',
        'employee_exits',
        'onboarding_checklists',
        'payslips',
        'employee_loans',
        'absence_requests',
        'ijss_tracking_periods'
    ];
BEGIN
    FOR r IN
        SELECT
            tc.table_schema,
            tc.table_name,
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS ref_table,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.referential_constraints AS rc
            ON tc.constraint_name = rc.constraint_name
            AND tc.table_schema = rc.constraint_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON rc.unique_constraint_name = ccu.constraint_name
            AND rc.unique_constraint_schema = ccu.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
            AND ccu.table_schema = 'public'
            AND ccu.table_name = ANY (parent_tables)
            AND rc.delete_rule IS DISTINCT FROM 'CASCADE'
    LOOP
        PERFORM public._eywai_recreate_fk_cascade(
            r.table_schema,
            r.table_name,
            r.constraint_name,
            r.column_name,
            'public',
            r.ref_table,
            'id'
        );
    END LOOP;
END;
$$;

-- 3) Tables sans FK versionnée : ajouter employee_id → employees CASCADE
DO $$
DECLARE
    tbl text;
    col text := 'employee_id';
    constraint_name text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'employee_time_entries',
        'employee_time_entries_validations',
        'employee_badge_credentials',
        'employee_time_day_accounting',
        'shifts',
        'ijss_expected_lines',
        'salary_certificates',
        'employee_competencies',
        'employee_certifications'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = tbl
              AND column_name = col
        ) THEN
            CONTINUE;
        END IF;

        IF EXISTS (
            SELECT 1
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.table_schema = 'public'
              AND tc.table_name = tbl
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = col
              AND ccu.table_name = 'employees'
        ) THEN
            CONTINUE;
        END IF;

        constraint_name := tbl || '_' || col || '_fkey';
        BEGIN
            EXECUTE format(
                'ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES public.employees(id) ON DELETE CASCADE',
                tbl, constraint_name, col
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
            WHEN others THEN
                RAISE NOTICE 'employee_delete_cascade: skip % (%).', tbl, SQLERRM;
        END;
    END LOOP;
END;
$$;

DROP FUNCTION IF EXISTS public._eywai_recreate_fk_cascade(text, text, text, text, text, text, text);
