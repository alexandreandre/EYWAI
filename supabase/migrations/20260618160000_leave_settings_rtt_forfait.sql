-- RTT forfait jours cadres : formule jours ouvrés travaillables − forfait annuel.

ALTER TABLE public.company_leave_settings
    ADD COLUMN IF NOT EXISTS rtt_use_forfait_jours_formula boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS rtt_forfait_annual_days integer NOT NULL DEFAULT 214
        CHECK (rtt_forfait_annual_days >= 180 AND rtt_forfait_annual_days <= 250),
    ADD COLUMN IF NOT EXISTS rtt_forfait_cp_ouvres_deduction numeric(6, 2) NOT NULL DEFAULT 25
        CHECK (
            rtt_forfait_cp_ouvres_deduction >= 0
            AND rtt_forfait_cp_ouvres_deduction <= 30
        );

COMMENT ON COLUMN public.company_leave_settings.rtt_use_forfait_jours_formula IS
    'RTT = jours ouvrés travaillables − forfait annuel (cadres forfait jours).';
COMMENT ON COLUMN public.company_leave_settings.rtt_forfait_annual_days IS
    'Forfait annuel en jours (ex. 214).';
COMMENT ON COLUMN public.company_leave_settings.rtt_forfait_cp_ouvres_deduction IS
    'CP ouvrés déduits du dénominateur (ex. 25).';
