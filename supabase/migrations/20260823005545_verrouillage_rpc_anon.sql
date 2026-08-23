-- Verrouillage des fonctions SECURITY DEFINER exposées à l'anonyme (23/08/2026).
--
-- AUDIT SÉCURITÉ AXE A — deux failles prouvées sur la production :
--
-- 1. ÉLÉVATION DE PRIVILÈGES ANONYME (critique). create_super_admin était
--    exécutable par `anon` sans aucun contrôle d'appelant. Chaîne reproduite
--    de bout en bout sur la base de test : inscription publique ouverte →
--    appel anonyme de create_super_admin(p_user_id = son propre uid) →
--    super_admin avec can_view_all_data sur les 7 sociétés.
--
-- 2. FUITE DE LA MASSE SALARIALE (haute). get_group_consolidated_dashboard et
--    get_group_payroll_evolution renvoyaient, en anonyme, la paie consolidée
--    du groupe (brut, net, charges, effectifs) pour tout company_id fourni ;
--    get_company_info livrait raison sociale + SIRET ;
--    get_user_accessible_companies acceptait un p_user_id explicite qui
--    court-circuitait auth.uid().
--
-- PRINCIPE APPLIQUÉ : le frontend n'appelle AUCUN RPC (0 occurrence de
-- `.rpc(` dans le code) — tout passe par le backend, qui tourne en
-- service_role. Le rôle `anon` n'a donc aucune raison d'exécuter quoi que ce
-- soit ici. `authenticated` reste autorisé UNIQUEMENT sur les fonctions
-- évaluées à l'intérieur des policies RLS (elles s'exécutent avec le rôle de
-- l'appelant : les révoquer casserait les accès des utilisateurs connectés).
--
-- Idempotent : ré-exécutable sans erreur.

-- ---------------------------------------------------------------------------
-- 1. anon révoqué partout ; authenticated gardé sur les fonctions de policy
--    (signatures résolues dynamiquement : elles diffèrent selon l'environnement)
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    r RECORD;
    -- Fonctions à conserver pour `authenticated` (policies RLS).
    gardees text[] := ARRAY[
        'get_user_accessible_companies', 'get_user_company_id',
        'get_user_employee_id', 'has_rh_access', 'is_company_admin',
        'is_company_manager', 'is_elected_member', 'is_super_admin'
    ];
BEGIN
    FOR r IN
        SELECT p.oid::regprocedure AS signature, p.proname
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.prosecdef
          AND (
              has_function_privilege('anon', p.oid, 'EXECUTE')
              OR has_function_privilege('authenticated', p.oid, 'EXECUTE')
          )
    LOOP
        -- PUBLIC d'abord : c'est de là que vient le droit par défaut de
        -- Postgres (proacl `=X/postgres`). Révoquer `anon` seul ne suffit
        -- pas — la fonction reste appelable avec la clé anon.
        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', r.signature);
        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM anon', r.signature);
        IF r.proname = ANY(gardees) THEN
            EXECUTE format(
                'GRANT EXECUTE ON FUNCTION %s TO authenticated', r.signature
            );
        ELSE
            EXECUTE format(
                'REVOKE EXECUTE ON FUNCTION %s FROM authenticated', r.signature
            );
        END IF;
        EXECUTE format(
            'GRANT EXECUTE ON FUNCTION %s TO service_role', r.signature
        );
    END LOOP;
END
$$;

-- ---------------------------------------------------------------------------
-- 2. Défense en profondeur : contrôle d'appelant DANS les fonctions critiques
--    (une révocation seule sauterait au premier GRANT malencontreux).
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.create_super_admin(
    p_email text,
    p_first_name text,
    p_last_name text,
    p_user_id uuid DEFAULT NULL::uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_user_id UUID;
    v_super_admin_id UUID;
BEGIN
    -- GARDE : réservé au backend (service_role) ou à un super admin établi.
    -- Sans ce contrôle, tout appelant pouvait se promouvoir lui-même.
    IF current_setting('role', true) IS DISTINCT FROM 'service_role'
       AND NOT COALESCE(public.is_super_admin(), false) THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Opération réservée aux administrateurs de la plateforme.'
        );
    END IF;

    IF p_user_id IS NOT NULL THEN
        v_user_id := p_user_id;
    ELSE
        SELECT id INTO v_user_id FROM auth.users WHERE email = p_email;
        IF v_user_id IS NULL THEN
            RETURN jsonb_build_object(
                'success', false,
                'error', 'Utilisateur non trouvé dans auth.users. Créez d''abord le compte.'
            );
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM public.super_admins WHERE user_id = v_user_id) THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Cet utilisateur est déjà un super admin'
        );
    END IF;

    INSERT INTO public.super_admins (
        user_id, email, first_name, last_name,
        can_create_companies, can_delete_companies, can_view_all_data, is_active
    ) VALUES (
        v_user_id, p_email, p_first_name, p_last_name,
        true, false, true, true
    )
    RETURNING id INTO v_super_admin_id;

    RETURN jsonb_build_object(
        'success', true,
        'super_admin_id', v_super_admin_id,
        'user_id', v_user_id,
        'email', p_email,
        'message', 'Super admin créé avec succès'
    );

EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object('success', false, 'error', SQLERRM);
END;
$function$;

REVOKE ALL ON FUNCTION public.create_super_admin(text, text, text, uuid)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_super_admin(text, text, text, uuid)
    TO service_role;

COMMENT ON FUNCTION public.create_super_admin(text, text, text, uuid) IS
    'Réservée au backend (service_role) ou à un super admin établi. '
    'Était exécutable par anon sans contrôle jusqu''au 23/08/2026 (audit sécurité).';
