-- Neutralisation de la base de test après copie depuis la production.
--
-- Les adresses e-mail des salariés sont VOLONTAIREMENT conservées : les
-- réécrire reviendrait à fabriquer des adresses, ce que la règle du projet
-- interdit, et rendrait le test infidèle à la production. La protection vient
-- de EMAIL_FORCE_REDIRECT_TO, sans lequel le backend refuse de démarrer.

-- --------------------------------------------------------------------------
-- Autorisations des rôles d'API Supabase sur le schéma public.
--
-- INDISPENSABLE : la resynchro fait DROP SCHEMA public CASCADE, ce qui efface
-- les GRANT que Supabase accorde d'origine à anon / authenticated /
-- service_role. Le dump est pris avec --no-privileges et ne les rétablit pas.
-- Sans ce bloc, toute l'API REST du projet de test répond
-- « permission denied for schema public » : l'environnement paraît déployé
-- mais ne peut rien lire ni écrire.
-- --------------------------------------------------------------------------
GRANT ALL ON SCHEMA public TO postgres;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

GRANT ALL ON ALL TABLES    IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON FUNCTIONS TO anon, authenticated, service_role;

-- --------------------------------------------------------------------------
-- Journal des resynchros.
-- Créé ici parce que la purge du schéma public l'efface à chaque copie.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.test_env_refresh_log (
  id bigserial PRIMARY KEY,
  finished_at timestamptz NOT NULL DEFAULT now(),
  employees_count integer
);

-- --------------------------------------------------------------------------
-- Configuration SMTP.
-- Sans cela, le test hérite des identifiants d'envoi de la production :
-- SmtpMailSender lit sa configuration en base (platform_email_settings, ligne
-- singleton id = 1) avant de se replier sur l'environnement.
-- La ligne est supprimée plutôt que vidée colonne par colonne : le résolveur
-- ne lit la base que si is_active est vrai, donc l'absence de ligne fait
-- retomber proprement sur les variables d'environnement du service de test.
-- --------------------------------------------------------------------------
DELETE FROM public.platform_email_settings;

-- --------------------------------------------------------------------------
-- Notifications en attente : elles porteraient sur des événements de
-- production et n'ont aucun sens dans un bac à sable.
-- --------------------------------------------------------------------------
TRUNCATE TABLE public.notifications;

-- --------------------------------------------------------------------------
-- Recharge du cache de schéma de PostgREST : les tables créées ou modifiées
-- par SQL brut restent invisibles de l'API REST tant qu'il n'a pas rechargé.
-- --------------------------------------------------------------------------
NOTIFY pgrst, 'reload schema';
