-- Fermer deux vues d'administration aux rôles publics de l'API.
--
-- user_permissions_view et role_templates_view servent à l'administration des
-- droits. Ni le serveur ni le site ne les lisent : le serveur passe par la clé
-- service_role, que cette migration ne touche pas. Les migrations du 22/07 et
-- du 04/08 retiraient déjà ces droits, mais une resynchro restaurée sans les
-- privilèges les a rendus aux rôles `anon` et `authenticated` sur la base de
-- test. Idempotente : rejouer ne change rien, et une base sans ces vues
-- (base locale neuve) passe sans erreur.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = 'user_permissions_view') THEN
    REVOKE ALL ON public.user_permissions_view FROM anon, authenticated;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = 'role_templates_view') THEN
    REVOKE ALL ON public.role_templates_view FROM anon, authenticated;
  END IF;
END $$;
