-- Cache de la synthèse IA des conventions collectives (PDF "synthèse expliquée").
-- Régénérée uniquement si le texte source (pdf_hash) change.

ALTER TABLE public.collective_agreement_texts
    ADD COLUMN IF NOT EXISTS synthesis_md text;

ALTER TABLE public.collective_agreement_texts
    ADD COLUMN IF NOT EXISTS synthesis_source_hash text;

ALTER TABLE public.collective_agreement_texts
    ADD COLUMN IF NOT EXISTS synthesis_model text;

ALTER TABLE public.collective_agreement_texts
    ADD COLUMN IF NOT EXISTS synthesis_generated_at timestamptz;

COMMENT ON COLUMN public.collective_agreement_texts.synthesis_md IS
    'Synthèse pédagogique de la convention (markdown) générée par IA et mise en cache';

COMMENT ON COLUMN public.collective_agreement_texts.synthesis_source_hash IS
    'Hash du texte source au moment de la génération de la synthèse (invalide le cache si différent)';

COMMENT ON COLUMN public.collective_agreement_texts.synthesis_model IS
    'Modèle IA utilisé pour générer la synthèse';

COMMENT ON COLUMN public.collective_agreement_texts.synthesis_generated_at IS
    'Date de génération de la synthèse en cache';
