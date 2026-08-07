-- Une seule référence pour « qui a le droit d'agir sur quelle société » :
-- user_company_accesses.
--
-- EYWAI est passé d'un compte rattaché à une société unique (profiles.company_id)
-- à un compte pouvant couvrir plusieurs sociétés (user_company_accesses). La
-- bascule n'a été faite qu'à moitié : get_user_company_id() a suivi, mais le
-- trigger de cohérence et plusieurs politiques RLS sont restés sur l'ancien
-- modèle. Cette migration termine la bascule.
--
-- Rien de tout ceci n'était versionné : ces objets n'existaient que dans la base,
-- invisibles en revue et perdus à toute reconstruction. Les redéfinir ici les
-- fait entrer dans le dépôt.

-- ---------------------------------------------------------------------------
-- 1. Le trigger de cohérence fiche / compte
-- ---------------------------------------------------------------------------
-- Il comparait la société de la fiche à profiles.company_id, c'est-à-dire à UNE
-- société. Un salarié dont le compte couvre plusieurs sociétés était donc refusé
-- alors qu'il avait bien accès à la sienne : plus aucune modification de sa fiche
-- n'était possible, ni par les RH ni par l'application. Deux salariés étaient
-- dans ce cas (une personne multi-sociétés, et une fiche rattachée à un compte
-- dont la société principale avait dérivé).
--
-- Un compte sans aucun accès déclaré n'est pas « d'une autre société » : c'est un
-- compte que l'application n'a pas encore approvisionné. Le bloquer ferait échouer
-- la création de fiche selon l'ordre des opérations, sans rien protéger. On ne
-- refuse donc que ce que la règle vise vraiment : un compte qui appartient à
-- d'autres sociétés, et à aucune de celle de la fiche.

CREATE OR REPLACE FUNCTION public.validate_employee_company_match()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.user_id IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM public.user_company_accesses a
           WHERE a.user_id = NEW.user_id
       )
       AND NOT EXISTS (
           SELECT 1 FROM public.user_company_accesses a
           WHERE a.user_id = NEW.user_id
             AND a.company_id = NEW.company_id
       )
    THEN
        RAISE EXCEPTION
            'SÉCURITÉ: le compte lié à cette fiche n''a accès à aucune société correspondant à celle de l''employé';
    END IF;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.validate_employee_company_match() IS
    'Empêche de rattacher une fiche salarié au compte d''une société étrangère. S''appuie sur user_company_accesses, seule référence des droits par société.';

DROP TRIGGER IF EXISTS trg_validate_employee_company ON public.employees;
CREATE TRIGGER trg_validate_employee_company
    BEFORE INSERT OR UPDATE ON public.employees
    FOR EACH ROW EXECUTE FUNCTION public.validate_employee_company_match();

-- ---------------------------------------------------------------------------
-- 2. Les politiques RLS héritées du modèle mono-société
-- ---------------------------------------------------------------------------
-- Ces politiques n'ont aucune condition de société : elles autorisent sur le seul
-- rôle « rh ». Étant permissives, elles s'ajoutent aux politiques cloisonnées au
-- lieu de les préciser — elles annulent donc le cloisonnement. Un compte marqué
-- « rh » pouvait lire, modifier et supprimer les salariés, les plannings et les
-- saisies de paie de TOUTES les sociétés.
--
-- Chaque table conserve après suppression une politique équivalente cloisonnée
-- (« Users can view employees from their company », « RH manage schedules »,
-- « RH manage monthly inputs »…), y compris l'accès du salarié à ses propres
-- lignes. Aucun écran n'est concerné : le front ne parle jamais directement à la
-- base, il passe par l'API.

DROP POLICY IF EXISTS "Accès aux dossiers employés" ON public.employees;
DROP POLICY IF EXISTS "Les RH peuvent modifier des employés" ON public.employees;
DROP POLICY IF EXISTS "Les RH peuvent supprimer des employés" ON public.employees;
DROP POLICY IF EXISTS "Accès aux plannings" ON public.employee_schedules;
DROP POLICY IF EXISTS "Accès aux saisies du mois" ON public.monthly_inputs;

-- ---------------------------------------------------------------------------
-- 3. profiles.company_id n'est plus une autorisation
-- ---------------------------------------------------------------------------
-- Le champ survit comme société d'affichage par défaut. Il dérive : treize profils
-- ne correspondaient plus à leur accès principal, dont sept pointaient vers une
-- société où le compte n'avait aucun accès. On les réaligne sur l'accès marqué
-- principal, seule source de vérité désormais. Les comptes sans aucun accès
-- (comptes de test) sont laissés tels quels, il n'y a rien sur quoi les aligner.

UPDATE public.profiles p
SET company_id = a.company_id
FROM public.user_company_accesses a
WHERE a.user_id = p.id
  AND a.is_primary
  AND p.company_id IS DISTINCT FROM a.company_id;

COMMENT ON COLUMN public.profiles.company_id IS
    'Société affichée par défaut à la connexion. N''accorde aucun droit : les droits par société vivent dans user_company_accesses (is_primary y tient le rôle de société principale).';
