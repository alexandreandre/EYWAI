-- Jetons d'activation de compte salarié (22/08/2026) — composant 1 de
-- l'intégration par vagues.
--
-- Une RH invite un salarié depuis sa fiche : un jeton MAISON à usage unique
-- (expiration 7 jours) est envoyé par e-mail. Le jeton n'est JAMAIS stocké en
-- clair : seule son empreinte sha256 (hex) l'est. Le ré-envoi invalide les
-- jetons antérieurs (invalidated_at) ; la consommation pose used_at.
--
-- Accès : RLS activée sans policy et droits retirés à anon/authenticated,
-- comme les autres tables du schéma (cf. 20260806170000). Le backend tourne
-- avec service_role, qui contourne la RLS : les endpoints publics de
-- vérification passent par lui, jamais par le client.
--
-- Idempotent : ré-exécutable sans erreur.

CREATE TABLE IF NOT EXISTS public.employee_activation_tokens (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    company_id      uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    token_hash      text NOT NULL UNIQUE,
    email_envoye    text NOT NULL,
    expires_at      timestamptz NOT NULL,
    used_at         timestamptz,
    invalidated_at  timestamptz,
    created_by      uuid,
    created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.employee_activation_tokens IS
    'Jetons d''activation de compte salarié (usage unique, expiration 7 jours). '
    'token_hash = sha256 hex du jeton, jamais le jeton en clair.';
COMMENT ON COLUMN public.employee_activation_tokens.email_envoye IS
    'Adresse réelle à laquelle l''invitation a été adressée (jamais une adresse fabriquée).';
COMMENT ON COLUMN public.employee_activation_tokens.used_at IS
    'Posé à la consommation du jeton (choix du mot de passe). Un jeton consommé est mort.';
COMMENT ON COLUMN public.employee_activation_tokens.invalidated_at IS
    'Posé quand un ré-envoi remplace ce jeton. Un jeton invalidé est mort.';

-- token_hash est déjà indexé par sa contrainte UNIQUE.
CREATE INDEX IF NOT EXISTS idx_employee_activation_tokens_employee
    ON public.employee_activation_tokens (employee_id);

ALTER TABLE public.employee_activation_tokens ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.employee_activation_tokens FROM anon, authenticated;
