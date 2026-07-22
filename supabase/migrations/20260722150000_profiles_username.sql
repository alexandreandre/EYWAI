-- Identifiant de connexion prenom.nom pour comptes sans fiche salarié (RH techniques).
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS username text;

CREATE UNIQUE INDEX IF NOT EXISTS profiles_username_unique
    ON public.profiles (lower(username))
    WHERE username IS NOT NULL;

COMMENT ON COLUMN public.profiles.username IS
    'Identifiant de connexion prenom.nom (résolu au login si pas de employees.username).';
