-- Bucket Supabase pour les contrats PDF de prêts employeur.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'employee_loan_contracts',
    'employee_loan_contracts',
    false,
    10485760,
    ARRAY['application/pdf']::text[]
)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS employee_loan_contracts_select ON storage.objects;
CREATE POLICY employee_loan_contracts_select ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id = 'employee_loan_contracts'
        AND (storage.foldername(name))[1] IN (
            SELECT uca.company_id::text
            FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_loan_contracts_insert ON storage.objects;
CREATE POLICY employee_loan_contracts_insert ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'employee_loan_contracts'
        AND (storage.foldername(name))[1] IN (
            SELECT uca.company_id::text
            FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

DROP POLICY IF EXISTS employee_loan_contracts_update ON storage.objects;
CREATE POLICY employee_loan_contracts_update ON storage.objects
    FOR UPDATE TO authenticated
    USING (
        bucket_id = 'employee_loan_contracts'
        AND (storage.foldername(name))[1] IN (
            SELECT uca.company_id::text
            FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

DROP POLICY IF EXISTS employee_loan_contracts_delete ON storage.objects;
CREATE POLICY employee_loan_contracts_delete ON storage.objects
    FOR DELETE TO authenticated
    USING (
        bucket_id = 'employee_loan_contracts'
        AND (storage.foldername(name))[1] IN (
            SELECT uca.company_id::text
            FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );
