-- Politique de routage HS par entreprise (indépendante de l'accord de modulation).

ALTER TABLE public.company_modulation_settings
    ADD COLUMN IF NOT EXISTS hs_routing_policy text NOT NULL DEFAULT 'franchise';

ALTER TABLE public.company_modulation_settings
    DROP CONSTRAINT IF EXISTS company_modulation_settings_hs_routing_policy_check;

ALTER TABLE public.company_modulation_settings
    ADD CONSTRAINT company_modulation_settings_hs_routing_policy_check
    CHECK (hs_routing_policy IN ('pay_all', 'account_all', 'franchise', 'manual'));

COMMENT ON COLUMN public.company_modulation_settings.hs_routing_policy IS
    'Routage HS : pay_all (bulletin), account_all (compte), franchise (plafond période), manual (décision RH).';
