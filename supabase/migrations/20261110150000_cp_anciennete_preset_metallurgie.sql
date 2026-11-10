-- Congés d'ancienneté : la base refusait le préréglage « métallurgie ».
--
-- La contrainte company_cp_seniority_settings_preset_check de la base de test
-- ne connaît que 'plasturgie_idcc_0292', 'lewis_agreement' et 'custom' (la
-- version de 20260618170000), bien que 20260619120000, qui y ajoutait la
-- métallurgie, soit notée appliquée. Choisir « métallurgie » à l'écran finissait
-- en refus de la base (23514), rendu « Erreur base de données » (502).
--
-- On repose la contrainte avec les quatre préréglages que le code accepte
-- (cp_seniority_repository._VALID_PRESETS). Rejouable sans effet.

ALTER TABLE public.company_cp_seniority_settings
    DROP CONSTRAINT IF EXISTS company_cp_seniority_settings_preset_check;

ALTER TABLE public.company_cp_seniority_settings
    ADD CONSTRAINT company_cp_seniority_settings_preset_check
    CHECK (preset IN (
        'plasturgie_idcc_0292', 'lewis_agreement', 'metallurgie_idcc_3248', 'custom'
    ));
