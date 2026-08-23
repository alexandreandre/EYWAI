-- Alertes de changement de RIB : lecture restreinte (23/08/2026, audit Axe A).
--
-- Même défaut que l'annuaire salariés : la policy SELECT était
-- `company_id = get_user_company_id()` SANS condition de rôle, donc tout
-- salarié connecté lisait les 294 alertes nominatives de sa société
-- (employee_id, message, détails d'un changement de coordonnées bancaires).
-- Vérifié après application : un salarié ne voit plus que la sienne.
--
-- Idempotent : ré-exécutable sans erreur.

DROP POLICY IF EXISTS "Users view company rib alerts" ON public.rib_alerts;
DROP POLICY IF EXISTS "Alertes RIB : RH, ou le salarie concerne"
    ON public.rib_alerts;

CREATE POLICY "Alertes RIB : RH, ou le salarie concerne"
    ON public.rib_alerts
    FOR SELECT
    TO authenticated
    USING (
        company_id = get_user_company_id()
        AND (
            has_rh_access()
            OR is_company_admin()
            OR employee_id = get_user_employee_id()
        )
    );

REVOKE ALL ON public.rib_alerts FROM anon;
