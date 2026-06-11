-- Comptes comptables PCG paie : mappings par rubrique (société + défaut global).

CREATE TABLE IF NOT EXISTS public.accounting_mappings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid REFERENCES public.companies(id) ON DELETE CASCADE,
    rubrique_code text NOT NULL,
    rubrique_libelle text NOT NULL,
    compte_comptable text NOT NULL,
    journal text NOT NULL DEFAULT 'OD',
    sens text NOT NULL DEFAULT 'debit' CHECK (sens IN ('debit', 'credit')),
    type_rubrique text NOT NULL DEFAULT 'salaire',
    analytique text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Run partiel possible : la table peut exister avec company_id NOT NULL.
-- Les defaults globaux (seed) nécessitent company_id nullable.
ALTER TABLE public.accounting_mappings
    ALTER COLUMN company_id DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'accounting_mappings_company_rubrique_key'
          AND conrelid = 'public.accounting_mappings'::regclass
    ) THEN
        ALTER TABLE public.accounting_mappings
            ADD CONSTRAINT accounting_mappings_company_rubrique_key
            UNIQUE NULLS NOT DISTINCT (company_id, rubrique_code);
    END IF;
END $$;

COMMENT ON TABLE public.accounting_mappings IS
    'Mapping rubriques paie → comptes PCG (override société ou défaut global si company_id IS NULL).';

CREATE INDEX IF NOT EXISTS idx_accounting_mappings_company
    ON public.accounting_mappings(company_id)
    WHERE is_active = true;

ALTER TABLE public.accounting_mappings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS accounting_mappings_select ON public.accounting_mappings;
CREATE POLICY accounting_mappings_select ON public.accounting_mappings
    FOR SELECT TO authenticated
    USING (
        company_id IS NULL
        OR company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS accounting_mappings_manage ON public.accounting_mappings;
CREATE POLICY accounting_mappings_manage ON public.accounting_mappings
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

-- Seed global (company_id NULL) — idempotent sans ON CONFLICT
INSERT INTO public.accounting_mappings
    (company_id, rubrique_code, rubrique_libelle, compte_comptable, journal, sens, type_rubrique)
SELECT seed.company_id, seed.rubrique_code, seed.rubrique_libelle, seed.compte_comptable, seed.journal, seed.sens, seed.type_rubrique
FROM (
    VALUES
        (NULL::uuid, 'salaire_brut', 'Salaire brut', '641000', 'OD', 'debit', 'salaire'),
        (NULL::uuid, 'net_a_payer', 'Net à payer', '425000', 'OD', 'credit', 'dette_salarie'),
        (NULL::uuid, 'cotisation_salariale', 'Cotisations salariales', '431000', 'OD', 'credit', 'dette_organisme'),
        (NULL::uuid, 'cotisation_patronale', 'Charges sociales patronales', '645000', 'OD', 'debit', 'charge_patronale'),
        (NULL::uuid, 'dette_organisme', 'Dettes organismes sociaux', '431000', 'OD', 'credit', 'dette_organisme'),
        (NULL::uuid, 'pas', 'Prélèvement à la source', '442000', 'OD', 'credit', 'pas'),
        (NULL::uuid, 'saisie_opposition', 'Oppositions sur salaires', '427000', 'OD', 'credit', 'dette_salarie'),
        (NULL::uuid, 'acompte_salaire', 'Acompte sur salaire', '425100', 'OD', 'credit', 'dette_salarie'),
        (NULL::uuid, 'avance_salaire', 'Avance sur salaire', '425200', 'OD', 'credit', 'dette_salarie'),
        (NULL::uuid, 'acompte_prime', 'Acompte sur prime', '425300', 'OD', 'credit', 'dette_salarie'),
        (NULL::uuid, 'pret_employeur', 'Prêt employeur', '274000', 'OD', 'credit', 'dette_salarie')
) AS seed(company_id, rubrique_code, rubrique_libelle, compte_comptable, journal, sens, type_rubrique)
WHERE NOT EXISTS (
    SELECT 1
    FROM public.accounting_mappings existing
    WHERE existing.company_id IS NOT DISTINCT FROM seed.company_id
      AND existing.rubrique_code = seed.rubrique_code
);

-- Étendre exports_history pour les nouveaux types
ALTER TABLE public.exports_history
    DROP CONSTRAINT IF EXISTS exports_history_export_type_check;

ALTER TABLE public.exports_history
    ADD CONSTRAINT exports_history_export_type_check
    CHECK (
        export_type IN (
            'journal_paie',
            'charges_sociales',
            'conges_absences',
            'notes_frais',
            'acomptes',
            'saisies',
            'prets_employeur',
            'paiement_organismes',
            'attestations_annexes',
            'fec',
            'od_salaires',
            'od_charges_sociales',
            'od_pas',
            'od_globale',
            'od_paie_unifiee',
            'export_cabinet_generique',
            'export_cabinet_quadra',
            'export_cabinet_sage',
            'dsn_mensuelle',
            'virement_salaires',
            'recapitulatif_montants'
        )
    );
