-- Lien d'activation partagé (28/08/2026) : plusieurs salariés, une seule URL.
-- Chacun s'identifie par son e-mail. Consommer un jeton ne tue pas les autres.
--
-- Idempotent : relancer ce fichier est sans effet.

ALTER TABLE public.employee_activation_tokens
    ADD COLUMN IF NOT EXISTS lien_partage text;

COMMENT ON COLUMN public.employee_activation_tokens.lien_partage IS
    'Identifiant brut du lien partagé (plusieurs salariés, même URL). '
    'NULL = invitation individuelle (jeton unique dans le lien).';

CREATE INDEX IF NOT EXISTS idx_employee_activation_tokens_lien_partage
    ON public.employee_activation_tokens (lien_partage)
    WHERE lien_partage IS NOT NULL
      AND used_at IS NULL
      AND invalidated_at IS NULL;
