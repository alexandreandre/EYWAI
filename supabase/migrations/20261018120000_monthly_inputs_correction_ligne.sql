-- Théorème de la correction à la main, étape 1 : une saisie du mois peut
-- porter une correction faite depuis le bulletin. Aujourd'hui, une
-- régularisation de cotisation. NULL pour toute saisie ordinaire.
ALTER TABLE public.monthly_inputs
  ADD COLUMN IF NOT EXISTS correction_ligne jsonb;

COMMENT ON COLUMN public.monthly_inputs.correction_ligne IS
  'Correction saisie à la main depuis le bulletin (type, organisme, base et taux ou montant, motif). NULL pour une saisie ordinaire.';
