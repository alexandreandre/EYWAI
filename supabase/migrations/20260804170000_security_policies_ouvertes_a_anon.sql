-- ============================================================================
-- Sécurité — policies « ouvertes » laissant passer l'anonyme (04/08/2026)
--
-- Suite de 20260804160000 : un balayage de TOUTES les tables du schéma public
-- sous le rôle `anon` (prod) a montré que 6 tables restaient lisibles malgré
-- une RLS active — leurs policies ciblent le rôle `public` (qui inclut anon)
-- avec USING (true). Trois d'entre elles étaient aussi INSCRIPTIBLES par un
-- anonyme :
--
--   notifications                     132 lignes  ALL/public/true  (mal nommée
--                                     « Service role full access ») — messages
--                                     RH nominatifs + employee_id + company_id
--   company_schedule_plans             22 lignes  ALL/public/true
--   recruitment_interview_participants  1 ligne   ALL/public/true
--
-- Correctif : ces policies deviennent réservées à service_role (le backend),
-- et les GRANT anon/authenticated sont retirés.
--
-- Laissées volontairement en lecture publique (référentiels sans donnée
-- personnelle, policies « _select_public » explicitement voulues) :
--   shift_types, collective_agreements, convention_collective_rules.
--
-- Idempotent.
-- ============================================================================

-- notifications : la policy annonçait service_role mais visait `public`.
DROP POLICY IF EXISTS "Service role full access" ON public.notifications;
CREATE POLICY "Service role full access"
    ON public.notifications
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
REVOKE ALL ON public.notifications FROM anon, authenticated;

-- company_schedule_plans : lecture + écriture ouvertes à tous.
DROP POLICY IF EXISTS schedule_plans_select ON public.company_schedule_plans;
DROP POLICY IF EXISTS schedule_plans_write  ON public.company_schedule_plans;
CREATE POLICY schedule_plans_service_role
    ON public.company_schedule_plans
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
REVOKE ALL ON public.company_schedule_plans FROM anon, authenticated;

-- recruitment_interview_participants : « allow_all » au sens littéral.
DROP POLICY IF EXISTS recruitment_participants_allow_all ON public.recruitment_interview_participants;
CREATE POLICY recruitment_participants_service_role
    ON public.recruitment_interview_participants
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
REVOKE ALL ON public.recruitment_interview_participants FROM anon, authenticated;
