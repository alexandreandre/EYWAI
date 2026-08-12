-- Compte QA pour les tests E2E Playwright — ENVIRONNEMENT DE TEST UNIQUEMENT.
--
-- Voie normale (automatique) : le workflow refresh-test-from-prod.yml le
-- rejoue après chaque resynchro, mot de passe injecté via
--   psql "$SUPABASE_TEST_DB_URL" -c "select set_config('qa.pw', '<mdp>', false);" -f scripts/qa/seed_qa_user.sql
-- Voie manuelle : SQL Editor du projet Supabase de TEST (tlvkjwleahkmuzcegrde),
-- précédé de : select set_config('qa.pw', '<mot de passe de frontend/.env.e2e>', false);
-- (dans la MÊME exécution). Idempotent : ré-exécutable à volonté.
--
-- ⚠ Ne JAMAIS l'exécuter sur le projet de production.

do $$
declare
  qa_id uuid := 'e2e00000-0000-4000-8000-000000000001';
  qa_email text := 'qa.playwright@eywai.access.local';
  qa_pw text := nullif(current_setting('qa.pw', true), '');
begin
  if qa_pw is null then
    raise exception 'Mot de passe absent : exécuter d''abord select set_config(''qa.pw'', ''...'', false); dans la même session';
  end if;

  delete from public.super_admins where user_id = qa_id;
  delete from public.profiles where id = qa_id;
  delete from auth.identities where user_id = qa_id;
  delete from auth.users where id = qa_id;

  insert into auth.users (
    instance_id, id, aud, role, email, encrypted_password,
    email_confirmed_at, created_at, updated_at,
    raw_app_meta_data, raw_user_meta_data,
    confirmation_token, recovery_token, email_change,
    email_change_token_new, email_change_token_current
  ) values (
    '00000000-0000-0000-0000-000000000000', qa_id, 'authenticated', 'authenticated',
    qa_email, extensions.crypt(qa_pw, extensions.gen_salt('bf')),
    now(), now(), now(),
    '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb,
    '', '', '', '', ''
  );

  insert into auth.identities (
    id, user_id, provider_id, provider, identity_data,
    last_sign_in_at, created_at, updated_at
  ) values (
    gen_random_uuid(), qa_id, qa_id::text, 'email',
    jsonb_build_object('sub', qa_id::text, 'email', qa_email, 'email_verified', true),
    now(), now(), now()
  );

  -- Même modèle d'accès que le compte plateforme existant : super_admin,
  -- sans lignes user_company_accesses / user_permissions.
  insert into public.profiles (id, first_name, last_name, role)
  values (qa_id, 'QA', 'Playwright', 'super_admin');

  -- Le statut admin plateforme (accès RH toutes sociétés) vient de la table
  -- super_admins, pas de profiles.role : sans cette ligne, le compte tombe
  -- dans l'Espace Collaborateur.
  insert into public.super_admins (
    user_id, email, first_name, last_name,
    can_create_companies, can_delete_companies, can_view_all_data,
    can_impersonate, is_active, notes
  ) values (
    qa_id, qa_email, 'QA', 'Playwright',
    false, false, true,
    false, true, 'Compte automatisé tests E2E Playwright — recréé par scripts/qa/seed_qa_user.sql'
  );

  raise notice 'Compte QA prêt : %', qa_email;
end $$;
