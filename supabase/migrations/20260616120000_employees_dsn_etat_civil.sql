-- Fiche salarié : champs d'état civil extraits de la DSN (import DSN).
-- Additif et idempotent. Le sexe (S21.G00.30.005) et le nom d'usage (S21.G00.30.003)
-- ne sont pas calculatoires en paie mais complètent la fiche collaborateur et
-- corrigent les requêtes d'aperçu entreprise qui sélectionnent déjà `sexe`.

ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS sexe text;

ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS nom_usage text;

COMMENT ON COLUMN public.employees.sexe IS
    'Sexe normalisé (M/F). Source DSN : S21.G00.30.005 (01 = masculin, 02 = féminin).';

COMMENT ON COLUMN public.employees.nom_usage IS
    'Nom d''usage du salarié. Source DSN : S21.G00.30.003.';
