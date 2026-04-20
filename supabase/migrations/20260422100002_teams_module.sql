-- =============================================================================
-- Module Équipes (teams) — référentiel par entreprise + lien optionnel employés
-- Migration additive (pas de DROP TABLE).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Référentiel teams
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.teams (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
    name text NOT NULL,
    description text,
    color text DEFAULT '#6366f1',
    manager_employee_id uuid REFERENCES public.employees (id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT teams_status_check CHECK (status IN ('active', 'archived')),
    CONSTRAINT teams_company_name_unique UNIQUE (company_id, name)
);

COMMENT ON TABLE public.teams IS 'Équipes par entreprise (V1 : responsable optionnel, statut active/archived).';

CREATE INDEX IF NOT EXISTS idx_teams_company_id ON public.teams (company_id);

CREATE INDEX IF NOT EXISTS idx_teams_company_status ON public.teams (company_id, status);

-- -----------------------------------------------------------------------------
-- 2. Lien employé → équipe (suppression équipe → NULL)
-- -----------------------------------------------------------------------------
ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS team_id uuid REFERENCES public.teams (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_employees_team_id ON public.employees (team_id);

-- -----------------------------------------------------------------------------
-- 3. Trigger updated_at (fonction générique réutilisable)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at ()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    AS $func$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$func$;

DROP TRIGGER IF EXISTS teams_set_updated_at ON public.teams;

CREATE TRIGGER teams_set_updated_at
    BEFORE UPDATE ON public.teams
    FOR EACH ROW
    EXECUTE PROCEDURE public.set_updated_at ();

-- -----------------------------------------------------------------------------
-- 4. RLS — teams
-- -----------------------------------------------------------------------------
ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;

-- SELECT : entreprise accessible (accès multi-entreprises OU fiche employé = auth.uid())
CREATE POLICY teams_select_company ON public.teams
    FOR SELECT
    TO authenticated
    USING ((
        company_id IN (
            SELECT
                uca.company_id
            FROM
                public.user_company_accesses uca
            WHERE
                uca.user_id = auth.uid ())
        OR company_id IN (
            SELECT
                e.company_id
            FROM
                public.employees e
            WHERE
                e.id = auth.uid ())));

-- INSERT / UPDATE / DELETE : roles admin ou rh sur la company cible (user_company_accesses)
CREATE POLICY teams_insert_rh_admin ON public.teams
    FOR INSERT
    TO authenticated
    WITH CHECK (company_id IN (
        SELECT
            uca.company_id
        FROM
            public.user_company_accesses uca
        WHERE
            uca.user_id = auth.uid ()
            AND uca.role IN ('admin', 'rh')));

CREATE POLICY teams_update_rh_admin ON public.teams
    FOR UPDATE
    TO authenticated
    USING (company_id IN (
        SELECT
            uca.company_id
        FROM
            public.user_company_accesses uca
        WHERE
            uca.user_id = auth.uid ()
            AND uca.role IN ('admin', 'rh')))
    WITH CHECK (company_id IN (
        SELECT
            uca.company_id
        FROM
            public.user_company_accesses uca
        WHERE
            uca.user_id = auth.uid ()
            AND uca.role IN ('admin', 'rh')));

CREATE POLICY teams_delete_rh_admin ON public.teams
    FOR DELETE
    TO authenticated
    USING (company_id IN (
        SELECT
            uca.company_id
        FROM
            public.user_company_accesses uca
        WHERE
            uca.user_id = auth.uid ()
            AND uca.role IN ('admin', 'rh')));
