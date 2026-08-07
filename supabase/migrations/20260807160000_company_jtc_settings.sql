-- JTC (Jour de Temps de Change) — accord d'entreprise propre à Mont Blanc
-- Composite. Aucune convention de branche ne le prévoit : le défaut est donc
-- désactivé, et aucune des sept sociétés ne voit de compteur apparaître tant
-- qu'on ne l'a pas activé explicitement.
--
-- jtc_opening_balance porte le droit de l'année, figé : saisi à la main pour
-- 2026 (EYWAI n'a aucune donnée 2025 pour le recalculer), produit par la
-- commande de calcul de janvier à partir de 2027. Le solde affiché en découle
-- par simple soustraction des jours posés, ce qui exclut tout double compte
-- entre un droit repris et un droit calculé.

ALTER TABLE public.company_leave_settings
    ADD COLUMN IF NOT EXISTS jtc_enabled boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS jtc_annual_days integer NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS jtc_absence_threshold_days integer NOT NULL DEFAULT 30,
    ADD COLUMN IF NOT EXISTS jtc_absence_types text[] NOT NULL
        DEFAULT ARRAY['arret_maladie', 'arret_at', 'arret_maladie_pro',
                      'arret_maternite', 'sans_solde']::text[];

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'company_leave_settings_jtc_annual_days_positif'
    ) THEN
        ALTER TABLE public.company_leave_settings
            ADD CONSTRAINT company_leave_settings_jtc_annual_days_positif
                CHECK (jtc_annual_days >= 0 AND jtc_annual_days <= 30);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'company_leave_settings_jtc_seuil_absences_positif'
    ) THEN
        ALTER TABLE public.company_leave_settings
            ADD CONSTRAINT company_leave_settings_jtc_seuil_absences_positif
                CHECK (jtc_absence_threshold_days >= 0
                       AND jtc_absence_threshold_days <= 365);
    END IF;
END
$$;

ALTER TABLE public.employee_leave_adjustments
    ADD COLUMN IF NOT EXISTS jtc_opening_balance numeric NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.company_leave_settings.jtc_enabled IS
    'Compteur JTC actif pour la société (accord d''entreprise MBC).';
COMMENT ON COLUMN public.employee_leave_adjustments.jtc_opening_balance IS
    'Droit JTC de l''année, figé en janvier sur les données N-1.';
