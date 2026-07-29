-- Neutralisation de la base de test après copie depuis la production.
--
-- Les adresses e-mail des salariés sont VOLONTAIREMENT conservées : les
-- réécrire reviendrait à fabriquer des adresses, ce que la règle du projet
-- interdit, et rendrait le test infidèle à la production. La protection vient
-- de EMAIL_FORCE_REDIRECT_TO, sans lequel le backend refuse de démarrer.

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
