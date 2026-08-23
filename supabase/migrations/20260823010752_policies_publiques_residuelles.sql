-- Fermeture des 6 policies « {public} USING(true) » résiduelles (23/08/2026).
--
-- AUDIT SÉCURITÉ AXE A. Ces policies étaient jusqu'ici considérées comme
-- inoffensives ; l'audit a prouvé le contraire, exploit exécuté sur la base
-- de test avec la seule clé anon (publique, présente dans le frontend) :
--
--   POST company_work_time_periods {...affects_payroll:true}      -> 201
--   POST employee_overtime_routing_decisions {total_hs_hours:99}  -> 201
--   PATCH ... {hours_to_pay:0, status:'validated'}                -> 200
--   DELETE ...                                                    -> 200
--
-- Autrement dit : un inconnu pouvait fabriquer ou neutraliser des heures
-- supplémentaires et des périodes de temps de travail — deux tables qui
-- pilotent la paie. `profiles` acceptait par ailleurs un INSERT libre, ce
-- qui permet de se fabriquer un profil (vecteur d'attribution de rôle).
--
-- PRINCIPE : le backend travaille en service_role (qui contourne la RLS) et
-- le frontend n'accède à AUCUNE table directement (0 occurrence de
-- `supabase.from(` dans le code) — anon n'a donc besoin d'aucun droit ici.
--
-- Idempotent : ré-exécutable sans erreur.

-- ---------------------------------------------------------------------------
-- 1. Tables qui pilotent la paie : CRUD anonyme supprimé
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS work_time_periods_select ON public.company_work_time_periods;
DROP POLICY IF EXISTS work_time_periods_write ON public.company_work_time_periods;
DROP POLICY IF EXISTS overtime_routing_decisions_select
    ON public.employee_overtime_routing_decisions;
DROP POLICY IF EXISTS overtime_routing_decisions_write
    ON public.employee_overtime_routing_decisions;

REVOKE ALL ON public.company_work_time_periods FROM anon, authenticated;
REVOKE ALL ON public.employee_overtime_routing_decisions FROM anon, authenticated;

-- ---------------------------------------------------------------------------
-- 2. profiles : plus d'INSERT libre — au mieux son PROPRE profil
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS "Allow profile creation" ON public.profiles;

CREATE POLICY "Profil : creation de son propre profil"
    ON public.profiles
    FOR INSERT
    TO authenticated
    WITH CHECK (id = auth.uid());

REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON public.profiles FROM anon;

-- ---------------------------------------------------------------------------
-- 3. convention_collective_rules : référentiel, lecture seulement pour les
--    comptes connectés (aucune raison d'être lisible par l'anonyme)
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS "Allow read convention_collective_rules"
    ON public.convention_collective_rules;

CREATE POLICY "Referentiel conventions : lecture authentifiee"
    ON public.convention_collective_rules
    FOR SELECT
    TO authenticated
    USING (true);

REVOKE ALL ON public.convention_collective_rules FROM anon;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON public.convention_collective_rules FROM authenticated;
