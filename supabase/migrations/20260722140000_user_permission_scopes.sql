-- =============================================================================
-- Permissions scopées : périmètre entreprise / équipes + exceptions individuelles
-- Migration additive (pas de DROP destructif métier). Idempotente.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0. Conflit de nom : table legacy vide user_permission_targets (autre schéma)
--    Colonnes observées : id, user_id, company_id, permission_id, created_at
--    Sans user_permission_id → incompatible avec le modèle scopé.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'user_permission_targets'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'user_permission_targets'
          AND column_name = 'user_permission_id'
    ) THEN
        -- Libère le nom sans perdre l'éventuel historique (table actuellement vide).
        ALTER TABLE public.user_permission_targets
            RENAME TO user_permission_targets_legacy_pre_scopes;
        COMMENT ON TABLE public.user_permission_targets_legacy_pre_scopes IS
            'Ancien stub (schéma incompatible) renommé lors de 20260722140000_user_permission_scopes.';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 1. Mode de périmètre sur chaque grant user_permissions
-- -----------------------------------------------------------------------------
ALTER TABLE public.user_permissions
    ADD COLUMN IF NOT EXISTS scope_mode text NOT NULL DEFAULT 'company';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'user_permissions_scope_mode_check'
    ) THEN
        ALTER TABLE public.user_permissions
            ADD CONSTRAINT user_permissions_scope_mode_check
            CHECK (scope_mode IN ('company', 'teams', 'none'));
    END IF;
END $$;

COMMENT ON COLUMN public.user_permissions.scope_mode IS
    'Périmètre du grant : company (toute l''entreprise), teams (équipes listées), none (exceptions individuelles uniquement).';

CREATE INDEX IF NOT EXISTS idx_user_permissions_user_company
    ON public.user_permissions (user_id, company_id);

-- -----------------------------------------------------------------------------
-- 2. Scopes équipes (uniquement si scope_mode = teams)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_permission_team_scopes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    user_permission_id uuid NOT NULL REFERENCES public.user_permissions (id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
    team_id uuid NOT NULL REFERENCES public.teams (id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now (),
    CONSTRAINT user_permission_team_scopes_unique UNIQUE (user_permission_id, team_id)
);

-- Si une table homonyme existait sans la colonne (cas théorique), l'ajouter
ALTER TABLE public.user_permission_team_scopes
    ADD COLUMN IF NOT EXISTS user_permission_id uuid REFERENCES public.user_permissions (id) ON DELETE CASCADE;

ALTER TABLE public.user_permission_team_scopes
    ADD COLUMN IF NOT EXISTS company_id uuid REFERENCES public.companies (id) ON DELETE CASCADE;

ALTER TABLE public.user_permission_team_scopes
    ADD COLUMN IF NOT EXISTS team_id uuid REFERENCES public.teams (id) ON DELETE CASCADE;

ALTER TABLE public.user_permission_team_scopes
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now ();

CREATE INDEX IF NOT EXISTS idx_upts_user_permission_id
    ON public.user_permission_team_scopes (user_permission_id);

CREATE INDEX IF NOT EXISTS idx_upts_company_team
    ON public.user_permission_team_scopes (company_id, team_id);

CREATE OR REPLACE FUNCTION public.enforce_upts_same_company ()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    AS $func$
DECLARE
    grant_company uuid;
    team_company uuid;
BEGIN
    SELECT
        up.company_id INTO grant_company
    FROM
        public.user_permissions up
    WHERE
        up.id = NEW.user_permission_id;
    IF grant_company IS NULL THEN
        RAISE EXCEPTION 'user_permission % introuvable', NEW.user_permission_id;
    END IF;
    IF NEW.company_id IS DISTINCT FROM grant_company THEN
        RAISE EXCEPTION 'company_id du scope (%) != company_id du grant (%)', NEW.company_id, grant_company;
    END IF;
    SELECT
        t.company_id INTO team_company
    FROM
        public.teams t
    WHERE
        t.id = NEW.team_id;
    IF team_company IS NULL THEN
        RAISE EXCEPTION 'équipe % introuvable', NEW.team_id;
    END IF;
    IF team_company IS DISTINCT FROM NEW.company_id THEN
        RAISE EXCEPTION 'équipe % n''appartient pas à l''entreprise %', NEW.team_id, NEW.company_id;
    END IF;
    RETURN NEW;
END;
$func$;

DROP TRIGGER IF EXISTS user_permission_team_scopes_same_company ON public.user_permission_team_scopes;

CREATE TRIGGER user_permission_team_scopes_same_company
    BEFORE INSERT OR UPDATE ON public.user_permission_team_scopes
    FOR EACH ROW
    EXECUTE PROCEDURE public.enforce_upts_same_company ();

COMMENT ON TABLE public.user_permission_team_scopes IS
    'Équipes autorisées pour un grant user_permissions en scope_mode=teams.';

-- -----------------------------------------------------------------------------
-- 3. Exceptions individuelles allow / deny
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_permission_targets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    user_permission_id uuid NOT NULL REFERENCES public.user_permissions (id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees (id) ON DELETE CASCADE,
    effect text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now (),
    CONSTRAINT user_permission_targets_effect_check CHECK (effect IN ('allow', 'deny')),
    CONSTRAINT user_permission_targets_unique UNIQUE (user_permission_id, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_upt_user_permission_id
    ON public.user_permission_targets (user_permission_id);

CREATE INDEX IF NOT EXISTS idx_upt_company_employee
    ON public.user_permission_targets (company_id, employee_id);

CREATE OR REPLACE FUNCTION public.enforce_upt_same_company ()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    AS $func$
DECLARE
    grant_company uuid;
    emp_company uuid;
BEGIN
    SELECT
        up.company_id INTO grant_company
    FROM
        public.user_permissions up
    WHERE
        up.id = NEW.user_permission_id;
    IF grant_company IS NULL THEN
        RAISE EXCEPTION 'user_permission % introuvable', NEW.user_permission_id;
    END IF;
    IF NEW.company_id IS DISTINCT FROM grant_company THEN
        RAISE EXCEPTION 'company_id de la cible (%) != company_id du grant (%)', NEW.company_id, grant_company;
    END IF;
    SELECT
        e.company_id INTO emp_company
    FROM
        public.employees e
    WHERE
        e.id = NEW.employee_id;
    IF emp_company IS NULL THEN
        RAISE EXCEPTION 'salarié % introuvable', NEW.employee_id;
    END IF;
    IF emp_company IS DISTINCT FROM NEW.company_id THEN
        RAISE EXCEPTION 'salarié % n''appartient pas à l''entreprise %', NEW.employee_id, NEW.company_id;
    END IF;
    RETURN NEW;
END;
$func$;

DROP TRIGGER IF EXISTS user_permission_targets_same_company ON public.user_permission_targets;

CREATE TRIGGER user_permission_targets_same_company
    BEFORE INSERT OR UPDATE ON public.user_permission_targets
    FOR EACH ROW
    EXECUTE PROCEDURE public.enforce_upt_same_company ();

COMMENT ON TABLE public.user_permission_targets IS
    'Exceptions individuelles allow/deny pour un grant user_permissions (priorité deny > allow > scope).';

-- -----------------------------------------------------------------------------
-- 4. RLS — lecture authentifiée via accès entreprise ; écriture service_role
-- -----------------------------------------------------------------------------
ALTER TABLE public.user_permission_team_scopes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_permission_targets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS upts_select_company ON public.user_permission_team_scopes;
CREATE POLICY upts_select_company ON public.user_permission_team_scopes
    FOR SELECT
    TO authenticated
    USING (
        company_id IN (
            SELECT
                uca.company_id
            FROM
                public.user_company_accesses uca
            WHERE
                uca.user_id = auth.uid ()
        )
    );

DROP POLICY IF EXISTS upt_select_company ON public.user_permission_targets;
CREATE POLICY upt_select_company ON public.user_permission_targets
    FOR SELECT
    TO authenticated
    USING (
        company_id IN (
            SELECT
                uca.company_id
            FROM
                public.user_company_accesses uca
            WHERE
                uca.user_id = auth.uid ()
        )
    );

-- Écritures via service_role (backend) uniquement — pas de policy INSERT/UPDATE/DELETE pour authenticated.

-- -----------------------------------------------------------------------------
-- 5. Catalogue : catégories / actions / permissions manquantes
-- -----------------------------------------------------------------------------
INSERT INTO public.permission_categories (id, code, label, description, display_order, is_active)
VALUES
    ('a1b2c3d4-e5f6-4789-a012-3456789abc01', 'bank_dispatch', 'Dispatch bancaire', 'Envoi des fichiers de virement / paie vers la banque', 90, true),
    ('a1b2c3d4-e5f6-4789-a012-3456789abc02', 'group', 'Groupe', 'Accès consolidés multi-entreprises', 91, true),
    ('a1b2c3d4-e5f6-4789-a012-3456789abc03', 'participation', 'Participation', 'Participation aux résultats (financier et répartition)', 92, true)
ON CONFLICT (code) DO UPDATE
SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    is_active = true,
    updated_at = now();

-- Actions dédiées : la contrainte UNIQUE (category_id, action_id) n'autorise
-- qu'une permission par couple catégorie/action. On ne peut donc pas réutiliser
-- view_all / manage deux fois sous la même catégorie participation.
INSERT INTO public.permission_actions (id, code, label, description, is_active)
VALUES
    (
        'b1b2c3d4-e5f6-4789-a012-3456789abc11',
        'manage',
        'Gérer',
        'Gestion complète (créer, modifier, supprimer)',
        true
    ),
    (
        'b1b2c3d4-e5f6-4789-a012-3456789abc12',
        'view_financials',
        'Voir les données financières',
        'Consultation des montants / paramètres financiers',
        true
    ),
    (
        'b1b2c3d4-e5f6-4789-a012-3456789abc13',
        'manage_financials',
        'Gérer les données financières',
        'Modification des montants / paramètres financiers',
        true
    ),
    (
        'b1b2c3d4-e5f6-4789-a012-3456789abc14',
        'view_allocation',
        'Voir la répartition',
        'Consultation de la répartition individuelle / RH',
        true
    ),
    (
        'b1b2c3d4-e5f6-4789-a012-3456789abc15',
        'manage_allocation',
        'Gérer la répartition',
        'Modification de la répartition individuelle / RH',
        true
    )
ON CONFLICT (code) DO UPDATE
SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    is_active = true;

INSERT INTO public.permissions (
    id, category_id, action_id, code, label, description, required_role, is_active
)
SELECT
    v.id::uuid,
    c.id,
    a.id,
    v.code,
    v.label,
    v.description,
    v.required_role,
    true
FROM (
    VALUES
        (
            'c1b2c3d4-e5f6-4789-a012-3456789abc21',
            'bank_dispatch',
            'send',
            'bank_dispatch.send',
            'Envoyer le dispatch bancaire',
            'Autorise l''envoi des virements / fichiers banque',
            'admin'
        ),
        (
            'c1b2c3d4-e5f6-4789-a012-3456789abc22',
            'group',
            'view_all',
            'group.consolidated.view',
            'Voir le consolidé groupe',
            'Accès aux vues consolidées multi-entreprises (administrateurs)',
            'admin'
        ),
        (
            'c1b2c3d4-e5f6-4789-a012-3456789abc23',
            'participation',
            'view_financials',
            'participation.financials.view',
            'Voir les données financières de participation',
            'Consultation des montants / paramètres financiers de participation',
            'admin'
        ),
        (
            'c1b2c3d4-e5f6-4789-a012-3456789abc24',
            'participation',
            'manage_financials',
            'participation.financials.manage',
            'Gérer les données financières de participation',
            'Modification des montants / paramètres financiers de participation',
            'admin'
        ),
        (
            'c1b2c3d4-e5f6-4789-a012-3456789abc25',
            'participation',
            'view_allocation',
            'participation.allocation.view',
            'Voir la répartition RH de participation',
            'Consultation de la répartition individuelle / RH',
            'rh'
        ),
        (
            'c1b2c3d4-e5f6-4789-a012-3456789abc26',
            'participation',
            'manage_allocation',
            'participation.allocation.manage',
            'Gérer la répartition RH de participation',
            'Modification de la répartition individuelle / RH',
            'rh'
        )
) AS v(id, cat_code, act_code, code, label, description, required_role)
JOIN public.permission_categories c ON c.code = v.cat_code
JOIN public.permission_actions a ON a.code = v.act_code
ON CONFLICT (code) DO UPDATE
SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    required_role = EXCLUDED.required_role,
    is_active = true,
    updated_at = now();

-- -----------------------------------------------------------------------------
-- 6. Flag changement de mot de passe obligatoire (profiles)
-- -----------------------------------------------------------------------------
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS must_change_password boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.profiles.must_change_password IS
    'Si true, l''utilisateur doit changer son mot de passe à la prochaine connexion.';

-- -----------------------------------------------------------------------------
-- 7. Désactivation douce des accès entreprise (sans DELETE)
-- -----------------------------------------------------------------------------
ALTER TABLE public.user_company_accesses
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_uca_user_active
    ON public.user_company_accesses (user_id, is_active);

COMMENT ON COLUMN public.user_company_accesses.is_active IS
    'False = accès désactivé (doublon / départ) sans suppression de la ligne.';
