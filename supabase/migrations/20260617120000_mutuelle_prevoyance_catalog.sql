-- Catalogue mutuelle entreprise + colonnes pack / catégorie (versionnement du schéma existant).

CREATE TABLE IF NOT EXISTS public.company_mutuelle_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    libelle text NOT NULL,
    montant_salarial numeric NOT NULL DEFAULT 0 CHECK (montant_salarial >= 0),
    montant_patronal numeric NOT NULL DEFAULT 0 CHECK (montant_patronal >= 0),
    part_patronale_soumise_a_csg boolean NOT NULL DEFAULT true,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES auth.users(id)
);

CREATE TABLE IF NOT EXISTS public.employee_mutuelle_types (
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    mutuelle_type_id uuid NOT NULL REFERENCES public.company_mutuelle_types(id) ON DELETE CASCADE,
    created_by uuid REFERENCES auth.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (employee_id, mutuelle_type_id)
);

ALTER TABLE public.company_mutuelle_types
    ADD COLUMN IF NOT EXISTS pack_couverture text
        CHECK (pack_couverture IS NULL OR pack_couverture IN ('isole', 'famille', 'duo', 'autre'));

ALTER TABLE public.company_mutuelle_types
    ADD COLUMN IF NOT EXISTS statut_categoriel text NOT NULL DEFAULT 'tous'
        CHECK (statut_categoriel IN ('cadre', 'non_cadre', 'tous'));

ALTER TABLE public.company_mutuelle_types
    ADD COLUMN IF NOT EXISTS code_option_dsn text;

ALTER TABLE public.company_mutuelle_types
    ADD COLUMN IF NOT EXISTS code_organisme_dsn text;

ALTER TABLE public.company_mutuelle_types
    ADD COLUMN IF NOT EXISTS reference_contrat_dsn text;

ALTER TABLE public.company_mutuelle_types
    ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'dsn_import'));

COMMENT ON COLUMN public.company_mutuelle_types.pack_couverture IS
    'Type de couverture mutuelle : isole (salarié seul), famille, duo (couple), autre.';
COMMENT ON COLUMN public.company_mutuelle_types.statut_categoriel IS
    'Catégorie salariale visée : cadre, non_cadre, ou tous.';
COMMENT ON COLUMN public.company_mutuelle_types.code_option_dsn IS
    'Code option DSN S21.G00.70.004 (ex. ISO, FAM) — défini par l''organisme.';

CREATE INDEX IF NOT EXISTS idx_company_mutuelle_types_company
    ON public.company_mutuelle_types (company_id);

CREATE INDEX IF NOT EXISTS idx_employee_mutuelle_types_employee
    ON public.employee_mutuelle_types (employee_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_company_mutuelle_types_dsn_key
    ON public.company_mutuelle_types (
        company_id,
        COALESCE(reference_contrat_dsn, ''),
        COALESCE(code_organisme_dsn, ''),
        COALESCE(code_option_dsn, ''),
        statut_categoriel,
        COALESCE(pack_couverture, ''),
        montant_salarial,
        montant_patronal
    )
    WHERE source = 'dsn_import';

ALTER TABLE public.company_mutuelle_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_mutuelle_types ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_mutuelle_types_select ON public.company_mutuelle_types;
CREATE POLICY company_mutuelle_types_select ON public.company_mutuelle_types
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_mutuelle_types_write ON public.company_mutuelle_types;
CREATE POLICY company_mutuelle_types_write ON public.company_mutuelle_types
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

DROP POLICY IF EXISTS employee_mutuelle_types_select ON public.employee_mutuelle_types;
CREATE POLICY employee_mutuelle_types_select ON public.employee_mutuelle_types
    FOR SELECT TO authenticated
    USING (
        employee_id IN (
            SELECT e.id FROM public.employees e
            JOIN public.user_company_accesses uca ON uca.company_id = e.company_id
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_mutuelle_types_write ON public.employee_mutuelle_types;
CREATE POLICY employee_mutuelle_types_write ON public.employee_mutuelle_types
    FOR ALL TO authenticated
    USING (
        employee_id IN (
            SELECT e.id FROM public.employees e
            JOIN public.user_company_accesses uca ON uca.company_id = e.company_id
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    )
    WITH CHECK (
        employee_id IN (
            SELECT e.id FROM public.employees e
            JOIN public.user_company_accesses uca ON uca.company_id = e.company_id
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );
