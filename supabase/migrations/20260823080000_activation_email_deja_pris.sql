-- Détection de collision d'adresse à l'invitation (23/08/2026).
--
-- Cas réel : un compte auth « orphelin » porte déjà l'adresse de la fiche
-- d'un salarié → la bascule d'e-mail à l'activation échouerait chez GoTrue
-- en « unexpected_failure » (indistinguable d'une panne). Cette fonction
-- permet au backend de signaler la collision à la RH AU MOMENT D'INVITER.
--
-- SECURITY DEFINER : lit auth.users, schéma non exposé par PostgREST.
-- EXECUTE réservé à service_role : jamais d'énumération côté client.
--
-- Idempotent : ré-exécutable sans erreur.

CREATE OR REPLACE FUNCTION public.activation_email_deja_pris(
    p_email text,
    p_user_id uuid DEFAULT NULL
)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1 FROM auth.users u
        WHERE lower(u.email) = lower(trim(p_email))
          AND (p_user_id IS NULL OR u.id <> p_user_id)
    );
$$;

COMMENT ON FUNCTION public.activation_email_deja_pris(text, uuid) IS
    'True si l''adresse est portée par un compte auth AUTRE que p_user_id. '
    'Réservée au backend (service_role) — détection de collision à l''invitation.';

REVOKE ALL ON FUNCTION public.activation_email_deja_pris(text, uuid)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.activation_email_deja_pris(text, uuid)
    TO service_role;
