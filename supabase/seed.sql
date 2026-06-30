-- Seed minimal pour Supabase local EYWAI.
-- Idempotent : relancable apres chaque reset local.

DO $$
DECLARE
  dev_user_id uuid := '00000000-0000-4000-8000-000000000001';
  dev_company_id uuid := '00000000-0000-4000-8000-000000000101';
BEGIN
  INSERT INTO auth.users (
    instance_id,
    id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    recovery_sent_at,
    last_sign_in_at,
    raw_app_meta_data,
    raw_user_meta_data,
    created_at,
    updated_at,
    confirmation_token,
    email_change,
    email_change_token_new,
    recovery_token
  )
  VALUES (
    '00000000-0000-0000-0000-000000000000',
    dev_user_id,
    'authenticated',
    'authenticated',
    'rh.dev@eywai.local',
    crypt('DevPassword123!', gen_salt('bf')),
    now(),
    now(),
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"first_name":"RH","last_name":"Local"}'::jsonb,
    now(),
    now(),
    '',
    '',
    '',
    ''
  )
  ON CONFLICT (id) DO UPDATE SET
    email = excluded.email,
    encrypted_password = excluded.encrypted_password,
    email_confirmed_at = excluded.email_confirmed_at,
    raw_app_meta_data = excluded.raw_app_meta_data,
    raw_user_meta_data = excluded.raw_user_meta_data,
    updated_at = now();

  INSERT INTO auth.identities (
    id,
    user_id,
    identity_data,
    provider,
    provider_id,
    last_sign_in_at,
    created_at,
    updated_at
  )
  VALUES (
    dev_user_id,
    dev_user_id,
    jsonb_build_object(
      'sub', dev_user_id::text,
      'email', 'rh.dev@eywai.local',
      'email_verified', true,
      'phone_verified', false
    ),
    'email',
    'rh.dev@eywai.local',
    now(),
    now(),
    now()
  )
  ON CONFLICT (provider, provider_id) DO UPDATE SET
    user_id = excluded.user_id,
    identity_data = excluded.identity_data,
    updated_at = now();

  IF to_regclass('public.companies') IS NOT NULL THEN
    INSERT INTO public.companies (id, company_name, siret)
    VALUES (dev_company_id, 'EYWAI Local Dev', '00000000000000')
    ON CONFLICT (id) DO UPDATE SET
      company_name = excluded.company_name,
      siret = excluded.siret;
  END IF;

  IF to_regclass('public.profiles') IS NOT NULL THEN
    INSERT INTO public.profiles (id, first_name, last_name, role, company_id)
    VALUES (dev_user_id, 'RH', 'Local', 'admin', dev_company_id)
    ON CONFLICT (id) DO UPDATE SET
      first_name = excluded.first_name,
      last_name = excluded.last_name,
      role = excluded.role,
      company_id = excluded.company_id;
  END IF;

  IF to_regclass('public.user_company_accesses') IS NOT NULL THEN
    DELETE FROM public.user_company_accesses
    WHERE user_id = dev_user_id AND company_id = dev_company_id;

    INSERT INTO public.user_company_accesses (user_id, company_id, role, is_primary)
    VALUES (dev_user_id, dev_company_id, 'admin', true);
  END IF;

  IF to_regclass('public.super_admins') IS NOT NULL THEN
    DELETE FROM public.super_admins
    WHERE user_id = dev_user_id;

    INSERT INTO public.super_admins (
      user_id,
      email,
      first_name,
      last_name,
      is_active
    )
    VALUES (
      dev_user_id,
      'rh.dev@eywai.local',
      'RH',
      'Local',
      true
    );
  END IF;

END $$;

CREATE OR REPLACE FUNCTION public.user_is_company_admin_for(
  p_company_id uuid,
  p_user_id uuid DEFAULT auth.uid()
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT public.is_super_admin()
    OR EXISTS (
      SELECT 1
      FROM public.user_company_accesses
      WHERE user_id = p_user_id
        AND company_id = p_company_id
        AND role = 'admin'
    );
$$;

DROP POLICY IF EXISTS "Company admins can view accesses to their company"
ON public.user_company_accesses;

CREATE POLICY "Company admins can view accesses to their company"
ON public.user_company_accesses
FOR SELECT
USING (
  public.user_is_company_admin_for(company_id, auth.uid())
);

CREATE OR REPLACE FUNCTION public.user_can_view_profile(
  p_profile_id uuid,
  p_company_id uuid
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT public.is_super_admin()
    OR p_profile_id = auth.uid()
    OR EXISTS (
      SELECT 1
      FROM public.user_company_accesses
      WHERE user_id = auth.uid()
        AND company_id = p_company_id
    );
$$;

CREATE OR REPLACE FUNCTION public.user_can_manage_profile(
  p_profile_id uuid,
  p_company_id uuid
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT public.is_super_admin()
    OR p_profile_id = auth.uid()
    OR EXISTS (
      SELECT 1
      FROM public.user_company_accesses
      WHERE user_id = auth.uid()
        AND company_id = p_company_id
        AND role = 'admin'
    );
$$;

DROP POLICY IF EXISTS "Admins can manage company profiles"
ON public.profiles;

DROP POLICY IF EXISTS "Users can update profiles based on role"
ON public.profiles;

DROP POLICY IF EXISTS "Users can view profiles based on role"
ON public.profiles;

CREATE POLICY "Admins can manage company profiles"
ON public.profiles
USING (public.user_can_manage_profile(id, company_id))
WITH CHECK (public.user_can_manage_profile(id, company_id));

CREATE POLICY "Users can update profiles based on role"
ON public.profiles
FOR UPDATE
USING (public.user_can_manage_profile(id, company_id))
WITH CHECK (public.user_can_manage_profile(id, company_id));

CREATE POLICY "Users can view profiles based on role"
ON public.profiles
FOR SELECT
USING (public.user_can_view_profile(id, company_id));
