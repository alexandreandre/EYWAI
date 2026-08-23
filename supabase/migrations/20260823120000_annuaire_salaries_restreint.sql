-- Annuaire salariés : fin de la lecture intégrale par tout compte de la
-- société (23/08/2026, audit sécurité Axe A).
--
-- La policy SELECT était `company_id = get_user_company_id()`, SANS aucune
-- condition de rôle : n'importe quel salarié connecté lisait la fiche
-- COMPLÈTE de tous ses collègues — NIR, coordonnées bancaires, salaire de
-- base, adresse, date de naissance. Volumétrie prod : 292 NIR, 291 RIB,
-- 7 sociétés. Reproduit sur la base de test avec un compte collaborateur
-- (impersonation exacte du rôle authenticated).
--
-- Le vecteur est réel dès la vague 0 : la clé anon est publique (frontend)
-- et tout salarié disposant d'un compte obtient son propre JWT, donc peut
-- interroger PostgREST directement.
--
-- Le backend travaille en service_role (RLS contournée) et le frontend
-- n'interroge aucune table directement : restreindre ici ne change rien au
-- fonctionnement de l'application.
--
-- NOTE : is_company_manager() est volontairement absente de la condition —
-- la fonction référence une colonne `is_manager` qui n existe pas et lève
-- une erreur, ce qui ferait échouer toute la policy (constat de l audit ;
-- fonction morte à traiter séparément).
--
-- Idempotent : ré-exécutable sans erreur.

DROP POLICY IF EXISTS "Users can view employees from their company"
    ON public.employees;

CREATE POLICY "Salaries : RH toute la societe, salarie sa fiche"
    ON public.employees
    FOR SELECT
    TO authenticated
    USING (
        company_id = get_user_company_id()
        AND (
            has_rh_access()
            OR is_company_admin()
            OR user_id = auth.uid()
            OR id = get_user_employee_id()
        )
    );

-- anon n'a aucune raison de toucher l'annuaire : les seuls accès légitimes
-- passent par le backend (service_role) ou par un compte connecté.
REVOKE ALL ON public.employees FROM anon;
