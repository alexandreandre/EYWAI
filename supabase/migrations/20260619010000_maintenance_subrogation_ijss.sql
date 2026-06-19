-- Maintien / subrogation : ancienneté AT/MP distincte + mode when_maintien

ALTER TABLE public.company_maintenance_settings
    ADD COLUMN IF NOT EXISTS min_seniority_months_at_mp integer NOT NULL DEFAULT 3;

COMMENT ON COLUMN public.company_maintenance_settings.min_seniority_months_at_mp IS
    'Ancienneté minimale (mois) pour le maintien employeur en AT/MP. Défaut 3 (conventionnel groupe).';

-- Étendre le CHECK subrogation_mode (drop + recreate idempotent)
ALTER TABLE public.company_maintenance_settings
    DROP CONSTRAINT IF EXISTS company_maintenance_settings_subrogation_mode_check;

UPDATE public.company_maintenance_settings
SET subrogation_mode = 'when_maintien'
WHERE subrogation_mode = 'automatic';

ALTER TABLE public.company_maintenance_settings
    ADD CONSTRAINT company_maintenance_settings_subrogation_mode_check
    CHECK (subrogation_mode IN ('when_maintien', 'automatic', 'at_mp_only', 'per_case'));

COMMENT ON COLUMN public.company_maintenance_settings.subrogation_mode IS
    'when_maintien = subrogation si maintien applicable ; per_case = choix RH ; at_mp_only = AT/MP + maintien.';
