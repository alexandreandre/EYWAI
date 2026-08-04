-- Seuil de présence en deçà duquel aucune pause n'est déduite d'une journée
-- pointée. Répond aux organisations où la pause déjeuner ne s'applique pas aux
-- demi-journées (Colorplast : 30 min au-delà de 6 h de présence).
--
-- Valeur par défaut 0 : aucune journée n'est exemptée, comportement inchangé
-- pour les entreprises déjà paramétrées.

ALTER TABLE public.company_punch_accounting_settings
    ADD COLUMN IF NOT EXISTS break_threshold_minutes integer NOT NULL DEFAULT 0
        CHECK (break_threshold_minutes >= 0 AND break_threshold_minutes <= 960);

COMMENT ON COLUMN public.company_punch_accounting_settings.break_threshold_minutes IS
    'Présence brute (minutes) en deçà ou égale à laquelle aucune pause n''est déduite. 0 = jamais d''exemption.';
