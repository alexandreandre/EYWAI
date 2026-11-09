-- R-658 (2/2) : retirer aux comptes connectés l'exécution directe des 8 fonctions
-- SECURITY DEFINER exposées en RPC.
--
-- Constat sur la base de test (lecture du 09/11/2026) : aucune de ces fonctions n'est
-- appelée en RPC par le code ; les politiques RLS qui les citent ne s'évaluent jamais
-- pour `authenticated`, qui n'a plus aucun droit sur les tables depuis
-- 20261103230000_fermer_les_tables_aux_roles_publics. Le serveur passe par service_role.
--
-- À APPLIQUER APRÈS 20261103230000 : si `authenticated` a encore un droit sur une table de
-- `public`, ses politiques appelleraient ces fonctions et échoueraient. La migration refuse.
-- Idempotente ; une fonction absente passe.
-- Retour arrière : GRANT EXECUTE ON FUNCTION ... TO authenticated, sur les mêmes signatures.

DO $$
DECLARE
  signature text;
  droits_restants integer;
BEGIN
  SELECT count(*) INTO droits_restants
  FROM information_schema.role_table_grants
  WHERE table_schema = 'public' AND grantee = 'authenticated';

  IF droits_restants > 0 THEN
    RAISE EXCEPTION
      'authenticated a encore % droit(s) sur des tables de public : appliquer d''abord 20261103230000.',
      droits_restants;
  END IF;

  FOREACH signature IN ARRAY ARRAY[
    'public.get_user_accessible_companies(uuid)',
    'public.get_user_company_id()',
    'public.get_user_employee_id()',
    'public.has_rh_access()',
    'public.is_company_admin()',
    'public.is_company_manager()',
    'public.is_elected_member(uuid)',
    'public.is_super_admin()'
  ]
  LOOP
    IF to_regprocedure(signature) IS NOT NULL THEN
      EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC, anon, authenticated', signature);
    END IF;
  END LOOP;
END $$;
