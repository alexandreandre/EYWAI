-- Maintien de salaire : table de configuration par entreprise + paramètres de
-- prévoyance (relais / garantie cadre).
--
-- La table company_maintenance_settings n'avait jusqu'ici aucune migration de
-- création dans le dépôt (créée manuellement en prod). On la (re)crée de façon
-- idempotente pour fiabiliser les environnements neufs, puis on garantit la
-- présence des colonnes de prévoyance (relais, taux garanti, périmètre cadre).

CREATE TABLE IF NOT EXISTS public.company_maintenance_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL UNIQUE REFERENCES public.companies(id) ON DELETE CASCADE,
    apply_legal_maintenance boolean NOT NULL DEFAULT true,
    min_seniority_months integer NOT NULL DEFAULT 12,
    employer_waiting_days integer NOT NULL DEFAULT 7,
    seniority_extension_enabled boolean NOT NULL DEFAULT false,
    remove_employer_waiting boolean NOT NULL DEFAULT false,
    annual_unique_waiting boolean NOT NULL DEFAULT false,
    maintain_100_percent boolean NOT NULL DEFAULT false,
    differentiated_at_illness boolean NOT NULL DEFAULT false,
    maintain_by_category boolean NOT NULL DEFAULT false,
    no_seniority_condition boolean NOT NULL DEFAULT false,
    custom_duration_days integer,
    subrogation_mode text NOT NULL DEFAULT 'automatic'
        CHECK (subrogation_mode IN ('automatic', 'at_mp_only', 'per_case')),
    provident_relay_days integer,
    provident_maintenance_rate numeric(5, 4),
    provident_cadre_only boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Mise à niveau des bases existantes (table déjà présente, colonnes manquantes).
ALTER TABLE public.company_maintenance_settings
    ADD COLUMN IF NOT EXISTS provident_relay_days integer,
    ADD COLUMN IF NOT EXISTS provident_maintenance_rate numeric(5, 4),
    ADD COLUMN IF NOT EXISTS provident_cadre_only boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN public.company_maintenance_settings.provident_maintenance_rate IS
    'Taux net de remplacement garanti par la prévoyance (0..1, ex. 0.80 = 80 % du brut). NULL = pas de garantie paramétrée.';

COMMENT ON COLUMN public.company_maintenance_settings.provident_cadre_only IS
    'Si true, la garantie prévoyance ne s''applique qu''aux salariés cadres / assimilés cadres.';

ALTER TABLE public.company_maintenance_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_maintenance_settings_select ON public.company_maintenance_settings;
CREATE POLICY company_maintenance_settings_select ON public.company_maintenance_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_maintenance_settings_write ON public.company_maintenance_settings;
CREATE POLICY company_maintenance_settings_write ON public.company_maintenance_settings
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
