-- Dérogation RH au plafond 50 % du net de référence (acompte/avance exceptionnelle).

ALTER TABLE IF EXISTS public.salary_advances
    ADD COLUMN IF NOT EXISTS plafond_net_override boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS plafond_net_override_reason text;

COMMENT ON COLUMN public.salary_advances.plafond_net_override IS
    'Dérogation RH au plafond 50 % du net de référence.';

COMMENT ON COLUMN public.salary_advances.plafond_net_override_reason IS
    'Motif obligatoire lorsque plafond_net_override est true.';
