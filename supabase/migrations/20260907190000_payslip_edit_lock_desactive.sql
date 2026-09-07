-- Désactivation (temporaire, phase de recette) du verrou d'édition manuelle
-- des bulletins.
--
-- La règle « édition verrouillée à partir du 15 du mois suivant » est globale
-- (payroll_config, clé payslip_edit_lock, jour borné 1-28 sans interrupteur) :
-- impossible de déverrouiller juillet 2026 par le seul réglage du jour. Le
-- backend comprend désormais config_data.enabled = false = verrou coupé
-- (period_edit_lock._resolve_lock_settings) ; l'écran admin
-- /admin/eywai/payroll-settings permet de le réarmer quand la recette sera
-- terminée.
--
-- Idempotente : le || jsonb réécrit la même valeur au rejeu.
UPDATE payroll_config
SET config_data = config_data || '{"enabled": false}'::jsonb
WHERE config_key = 'payslip_edit_lock'
  AND is_active = true
  AND company_id IS NULL;
