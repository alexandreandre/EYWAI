-- R-658 (1/2) : fixer le search_path des 71 fonctions signalées par l'audit Supabase.
--
-- Constat sur la base de test (lecture du 09/11/2026) : 71 fonctions de `public` sans
-- search_path, dont les fonctions SECURITY DEFINER, où le chemin de l'appelant décide de
-- ce qui s'exécute. La valeur reproduit le chemin d'aujourd'hui (public, puis extensions),
-- avec pg_temp en dernier : aucun corps de fonction n'est réécrit.
-- Vérifié : aucune de ces fonctions n'appelle unaccent, crypt, uuid_generate ni pgcrypto
-- sans préfixe ; aucun index ne dépend de remove_accents.
-- Idempotente ; une fonction absente de la base passe.
-- Retour arrière : ALTER FUNCTION ... RESET search_path sur la même liste.

DO $$
DECLARE
  f record;
BEGIN
  FOR f IN
    SELECT p.oid::regprocedure AS signature
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.prokind = 'f'
      AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
      AND p.proname = ANY (ARRAY[
    'add_employee_to_company',
    'audit_company_access',
    'calculate_seizable_amount',
    'check_company_data_integrity',
    'check_employee_exit_status_before_absence',
    'check_role_hierarchy',
    'cleanup_expired_password_resets',
    'company_maintenance_settings_set_updated_at',
    'copy_template_permissions_to_user',
    'create_company_with_admin',
    'create_permission_if_not_exists',
    'enforce_upt_same_company',
    'enforce_upts_same_company',
    'get_active_company_id',
    'get_company_info',
    'get_company_statistics',
    'get_group_company_comparison',
    'get_group_consolidated_dashboard',
    'get_group_employees_stats',
    'get_group_payroll_evolution',
    'get_group_payroll_stats',
    'get_scraping_stats',
    'get_super_admin_permissions',
    'get_user_accessible_companies',
    'get_user_company_id',
    'get_user_company_role',
    'get_user_employee_id',
    'get_user_primary_company',
    'get_user_role_in_active_company',
    'handle_new_user',
    'has_rh_access',
    'increment_edit_count',
    'initialize_scraping_sources',
    'is_company_admin',
    'is_company_rh',
    'is_elected_member',
    'is_group_admin',
    'is_meeting_participant',
    'is_super_admin',
    'module_documents_set_updated_at',
    'planning_module_set_updated_at',
    'remove_accents',
    'set_session_company',
    'set_updated_at',
    'sync_primary_company',
    'transfer_employee_to_company',
    'trigger_update_company_effectif',
    'update_annual_reviews_updated_at',
    'update_catalog_updated_at',
    'update_collective_agreement_texts_updated_at',
    'update_collective_agreement_updated_at',
    'update_companies_timestamp',
    'update_company_effectif',
    'update_convention_classifications_updated_at',
    'update_cse_tables_updated_at',
    'update_employee_documents_updated_at',
    'update_employee_exits_updated_at',
    'update_employee_schedules_timestamp',
    'update_medical_obligations_updated_at',
    'update_monthly_inputs_timestamp',
    'update_payslips_timestamp',
    'update_promotions_updated_at',
    'update_recruitment_updated_at',
    'update_timestamp',
    'update_updated_at_column',
    'user_can_manage_company_data',
    'user_has_company_access',
    'validate_company_context',
    'validate_edit_history',
    'validate_employee_company_match',
    'validate_internal_notes'
      ])
  LOOP
    EXECUTE format('ALTER FUNCTION %s SET search_path = public, extensions, pg_temp', f.signature);
  END LOOP;
END $$;
