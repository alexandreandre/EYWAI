-- Import DSN admin : staging batches/items + salariés importables sans compte Auth

-- Permettre salariés importés sans compte Auth (id généré côté serveur)
DO $$
BEGIN
    IF to_regclass('public.employees') IS NOT NULL THEN
        ALTER TABLE public.employees
            ALTER COLUMN user_id DROP NOT NULL;
    END IF;
EXCEPTION
    WHEN others THEN
        RAISE NOTICE 'employees.user_id nullable : %', SQLERRM;
END $$;

-- SIREN sur les groupes (entité juridique)
ALTER TABLE public.company_groups
    ADD COLUMN IF NOT EXISTS siren text;

CREATE INDEX IF NOT EXISTS company_groups_siren_idx
    ON public.company_groups (siren)
    WHERE siren IS NOT NULL;

COMMENT ON COLUMN public.company_groups.siren IS
    'SIREN de l''entité juridique (groupe multi-établissements).';

-- Batches d''import DSN
CREATE TABLE IF NOT EXISTS public.dsn_import_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    uploaded_by uuid NOT NULL,
    file_names jsonb NOT NULL DEFAULT '[]'::jsonb,
    siren text,
    period_min text,
    period_max text,
    status text NOT NULL DEFAULT 'parsed'
        CHECK (status IN ('parsed', 'previewed', 'committed', 'failed')),
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    preview jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dsn_import_batches_status_idx
    ON public.dsn_import_batches (status, created_at DESC);

CREATE INDEX IF NOT EXISTS dsn_import_batches_uploaded_by_idx
    ON public.dsn_import_batches (uploaded_by, created_at DESC);

COMMENT ON TABLE public.dsn_import_batches IS
    'Sessions d''import DSN (super-admin) : upload, preview, commit.';

-- Items de staging par batch
CREATE TABLE IF NOT EXISTS public.dsn_import_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL,
    item_type text NOT NULL
        CHECK (item_type IN (
            'group', 'establishment', 'employee', 'cumul', 'collective_agreement'
        )),
    source_ref text NOT NULL,
    action text NOT NULL DEFAULT 'create'
        CHECK (action IN ('create', 'update', 'skip')),
    mapped_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    target_id uuid,
    anomalies jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'committed', 'skipped', 'failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dsn_import_items_batch_idx
    ON public.dsn_import_items (batch_id, item_type);

CREATE UNIQUE INDEX IF NOT EXISTS dsn_import_items_batch_source_ref_idx
    ON public.dsn_import_items (batch_id, source_ref);

DO $$
BEGIN
    IF to_regclass('public.dsn_import_batches') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conname = 'dsn_import_items_batch_id_fkey'
       )
    THEN
        ALTER TABLE public.dsn_import_items
            ADD CONSTRAINT dsn_import_items_batch_id_fkey
            FOREIGN KEY (batch_id) REFERENCES public.dsn_import_batches(id) ON DELETE CASCADE;
    END IF;
END $$;

COMMENT ON TABLE public.dsn_import_items IS
    'Lignes de staging pour un import DSN (établissement, salarié, cumul, CC).';

ALTER TABLE public.dsn_import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dsn_import_items ENABLE ROW LEVEL SECURITY;

-- Accès réservé aux super-admins (lecture/écriture via backend service_role en pratique)
DO $$
BEGIN
    IF to_regclass('public.super_admins') IS NULL THEN
        RAISE NOTICE 'dsn_import : policies RLS non créées (super_admins absent).';
        RETURN;
    END IF;

    DROP POLICY IF EXISTS dsn_import_batches_super_admin ON public.dsn_import_batches;
    CREATE POLICY dsn_import_batches_super_admin ON public.dsn_import_batches
        FOR ALL TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM public.super_admins sa
                WHERE sa.user_id = auth.uid() AND sa.is_active = true
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM public.super_admins sa
                WHERE sa.user_id = auth.uid() AND sa.is_active = true
            )
        );

    DROP POLICY IF EXISTS dsn_import_items_super_admin ON public.dsn_import_items;
    CREATE POLICY dsn_import_items_super_admin ON public.dsn_import_items
        FOR ALL TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM public.super_admins sa
                WHERE sa.user_id = auth.uid() AND sa.is_active = true
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM public.super_admins sa
                WHERE sa.user_id = auth.uid() AND sa.is_active = true
            )
        );
END $$;
