-- Lecture directe des contrats passés et des profils BOETH réservée à la RH.
-- Avant : tout utilisateur ayant un accès à la société (rôles collaborateur et
-- custom compris) pouvait lire ces lignes par l'API Supabase. Le serveur lit
-- avec la clé de service : aucun écran ne change. Idempotente.

DROP POLICY IF EXISTS employee_contract_periods_select ON public.employee_contract_periods;
CREATE POLICY employee_contract_periods_select ON public.employee_contract_periods
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

DROP POLICY IF EXISTS employee_boeth_profiles_select ON public.employee_boeth_profiles;
CREATE POLICY employee_boeth_profiles_select ON public.employee_boeth_profiles
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

DROP POLICY IF EXISTS employee_boeth_status_history_select ON public.employee_boeth_status_history;
CREATE POLICY employee_boeth_status_history_select ON public.employee_boeth_status_history
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );
