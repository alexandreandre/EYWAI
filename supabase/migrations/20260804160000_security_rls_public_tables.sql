-- ============================================================================
-- Sécurité — fermeture de l'accès anonyme aux tables publiques (04/08/2026)
--
-- CONTEXTE : vérifié en prod avec la clé publique `sb_publishable_…` (celle
-- embarquée dans le bundle front, donc publique) :
--   GET /rest/v1/user_permissions                    -> 200 (569 lignes, + INSERT/UPDATE/DELETE autorisés)
--   GET /rest/v1/_backup_profiles_before_migration_17 -> 200 (PII : noms, rôles)
--   GET /rest/v1/payroll_config                       -> 200 (tous les barèmes, modifiables)
-- Cause : 16 tables du schéma public sans RLS + GRANT ALL à anon/authenticated.
--
-- Remplace 20260722120000_security_rls_advisor_fixes.sql : ce fichier est
-- enregistré comme appliqué dans supabase_migrations des deux côtés alors que
-- le schéma réel montre l'inverse (RLS toujours off) — il ne sera jamais rejoué.
--
-- SÛRETÉ : `service_role` a rolbypassrls = true (vérifié) et le backend tourne
-- avec cette clé (SUPABASE_KEY, en local comme sur Cloud Run). 23 tables sont
-- déjà en RLS sans policy et l'application fonctionne : la démonstration est
-- faite. Le front n'utilise pas supabase-js (aucun createClient dans src/).
--
-- Deux écarts volontaires avec la version du 22/07 :
--   * les tables _backup_* sont DÉPLACÉES (schéma `archive`, hors PostgREST)
--     et non supprimées : même effet sécurité, sans perte de données ;
--   * `security_invoker` n'est PAS activé sur user_permissions_view :
--     service_role n'a pas SELECT sur auth.users (vérifié), la vue deviendrait
--     illisible même pour le backend. Le REVOKE suffit à fermer la fuite.
--
-- Idempotent : ré-exécutable sans erreur.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) Tables de sauvegarde de migration : hors du schéma exposé par PostgREST.
--    `archive` n'est pas dans les schémas exposés -> inatteignable via l'API,
--    mais les données restent lisibles en SQL (service_role / postgres).
-- ----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS archive;
REVOKE ALL ON SCHEMA archive FROM PUBLIC, anon, authenticated;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public'
               AND tablename = '_backup_profiles_before_migration_17') THEN
        ALTER TABLE public._backup_profiles_before_migration_17 SET SCHEMA archive;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public'
               AND tablename = '_backup_migration_c_salarie') THEN
        ALTER TABLE public._backup_migration_c_salarie SET SCHEMA archive;
    END IF;
END $$;

REVOKE ALL ON ALL TABLES IN SCHEMA archive FROM anon, authenticated;

-- ----------------------------------------------------------------------------
-- 2) RLS + retrait des droits sur les 13 tables sans policy.
--    Deux verrous indépendants : la RLS (deny-all faute de policy) et le
--    retrait des GRANT. service_role continue de tout faire (bypassrls).
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    t text;
    tables text[] := ARRAY[
        -- Catalogue RBAC
        'permissions',
        'permission_actions',
        'permission_categories',
        'role_templates',
        'role_template_permissions',
        -- Droits par utilisateur : écriture anon = escalade de privilèges
        'user_permissions',
        -- Référentiels & templates
        'cc_evenements_familiaux',
        'evenements_familiaux_reference',
        'document_template_versions',
        'interview_template_questions',
        'interview_template_sections',
        -- Objectifs / entretiens (données RH salarié)
        'objective_checkins',
        'objective_milestones'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = t) THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
            EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', t);
        END IF;
    END LOOP;
END $$;

-- ----------------------------------------------------------------------------
-- 3) payroll_config : possède déjà 3 policies, dormantes tant que la RLS est
--    off. Les deux policies « métier » ciblent le rôle `public`, qui inclut
--    anon : les activer telles quelles laisserait un anonyme lire les barèmes
--    globaux (company_id IS NULL). On les recrée sur `authenticated`.
--    Lecture authenticated conservée, écriture retirée (réservée au backend).
-- ----------------------------------------------------------------------------
ALTER TABLE public.payroll_config ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users view relevant configs"   ON public.payroll_config;
DROP POLICY IF EXISTS "Admins manage company configs" ON public.payroll_config;

CREATE POLICY "Users view relevant configs"
    ON public.payroll_config
    FOR SELECT
    TO authenticated
    USING ((company_id IS NULL) OR (company_id = get_user_company_id()));

CREATE POLICY "Admins manage company configs"
    ON public.payroll_config
    FOR ALL
    TO authenticated
    USING      (is_company_admin() AND ((company_id IS NULL) OR (company_id = get_user_company_id())))
    WITH CHECK (is_company_admin() AND ((company_id IS NULL) OR (company_id = get_user_company_id())));

-- La policy service_role_full_access (ALL / true) est laissée intacte.

REVOKE ALL          ON public.payroll_config FROM anon;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
                    ON public.payroll_config FROM authenticated;

-- ----------------------------------------------------------------------------
-- 4) Vues exposant auth.users / le RBAC (alertes auth_users_exposed et
--    security_definer_view). Aucun code ne les interroge (vérifié : aucune
--    occurrence hors migrations). On retire simplement les droits API.
-- ----------------------------------------------------------------------------
REVOKE ALL ON public.user_permissions_view FROM anon, authenticated;
REVOKE ALL ON public.role_templates_view   FROM anon, authenticated;
