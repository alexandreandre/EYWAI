-- Fermer les tables du schéma public aux rôles publics de l'API (03/11/2026,
-- audit de modernisation, alerte A2).
--
-- Constat sur la base de test (lecture du 03/11) : `anon` avait des droits sur 204
-- tables sur 215, `authenticated` sur 207 ; la RLS était la seule serrure contre
-- quiconque détient la clé anon. Or personne ne lit les tables sous ces rôles :
-- le serveur passe par la clé service_role (qui garde tous ses droits ici), la
-- clé anon ne sert qu'à l'API d'authentification (connexion, rafraîchissement),
-- et le site n'embarque plus de client Supabase. La RLS devient une seconde serrure.
--
-- 1. Retirer tous les droits d'`anon` et `authenticated` sur les tables, vues et
--    séquences de `public`, et sur celles que `postgres` créera ensuite.
-- 2. Activer la RLS sur `test_env_refresh_log` (seule table sans RLS ; écrite par
--    le propriétaire et lue par service_role, qui ne sont pas soumis à la RLS).
-- 3. Supprimer `public.execute_sql(text)` : exécutable par PUBLIC, appelée par
--    aucun code du dépôt.
--
-- Hors champ : le droit EXECUTE sur les fonctions (RPC) reste tel quel.
-- Idempotente : rejouer ne change rien ; une base sans ces objets passe.
-- Retour arrière : 20261103230000_fermer_les_tables_aux_roles_publics.retour.sql
-- (dans data/_rapports/audit-modernisation/, hors dépôt), qui rend les droits d'avant.

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM anon, authenticated;

DO $$
BEGIN
  IF to_regclass('public.test_env_refresh_log') IS NOT NULL THEN
    ALTER TABLE public.test_env_refresh_log ENABLE ROW LEVEL SECURITY;
  END IF;
END $$;

DROP FUNCTION IF EXISTS public.execute_sql(text);
