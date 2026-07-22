-- ============================================================================
-- Correctifs sécurité — Supabase Security Advisor (20/07/2026)
-- Projet SIRH (slleauhyjnmiawosvlcg).
--
-- Alertes couvertes :
--   * rls_disabled_in_public  -> 14 tables publiques sans RLS
--   * auth_users_exposed      -> vue user_permissions_view exposant auth.users.email
--
-- SÛRETÉ : le client backend utilise la clé service_role, or service_role a
-- rolbypassrls=true (vérifié en base). Activer la RLS ci-dessous NE bloque donc
-- PAS le backend ; cela bloque uniquement les rôles anon/authenticated (rolbypassrls=false),
-- c.-à-d. l'accès direct via la clé anon — exactement la faille signalée.
-- Le frontend n'accède à aucune de ces tables directement (aucun client Supabase côté front).
-- Idempotent : ré-exécutable sans erreur.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) rls_disabled_in_public : activer la RLS (deny-all anon/authenticated,
--    service_role continue de bypasser). Réservé au backend.
-- ----------------------------------------------------------------------------

-- Catalogue RBAC (référentiel géré par le backend)
ALTER TABLE public.permissions              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permission_actions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permission_categories    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.role_templates           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.role_template_permissions ENABLE ROW LEVEL SECURITY;

-- Droits par utilisateur (company-scoped) — écriture anon = escalade de privilèges : à fermer en priorité
ALTER TABLE public.user_permissions         ENABLE ROW LEVEL SECURITY;

-- Config paie : possède déjà 3 policies (dormantes tant que la RLS est off) ;
-- l'activation les rend effectives (lecture authenticated scoped par entreprise, service_role plein accès).
ALTER TABLE public.payroll_config           ENABLE ROW LEVEL SECURITY;

-- Référentiels & templates
ALTER TABLE public.cc_evenements_familiaux         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evenements_familiaux_reference  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_template_versions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_template_questions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_template_sections     ENABLE ROW LEVEL SECURITY;

-- Objectifs / entretiens (données RH salarié)
ALTER TABLE public.objective_checkins       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.objective_milestones     ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 2) auth_users_exposed : la vue user_permissions_view joint auth.users (email)
--    et tourne avec les droits du propriétaire (postgres). On la passe en
--    security_invoker (elle respecte alors les droits de l'appelant : anon/authenticated
--    n'ont aucun accès à auth.users) et on retire les grants API superflus.
--    Le backend (service_role) continue de la lire normalement.
-- ----------------------------------------------------------------------------
ALTER VIEW IF EXISTS public.user_permissions_view SET (security_invoker = on);
REVOKE ALL ON public.user_permissions_view FROM anon, authenticated;

-- ----------------------------------------------------------------------------
-- 3) Tables de sauvegarde de migration (reliquats), sans RLS, lisibles ET
--    supprimables par anon. _backup_profiles_before_migration_17 contient des PII
--    (first_name, last_name, role, company_id ; 9 lignes).
--    Décision : suppression (élimine la faille + la dette de migration).
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS public._backup_profiles_before_migration_17;
DROP TABLE IF EXISTS public._backup_migration_c_salarie;
