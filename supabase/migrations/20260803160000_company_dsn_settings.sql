-- Paramétrage DSN par société : tout ce qui ne se déduit d'aucun bulletin.
-- Émetteur, contacts, NAF déclaré, IDCC. Repris de la dernière DSN du cabinet
-- puis corrigeable ; chaque ligne garde la trace de sa provenance.

CREATE TABLE IF NOT EXISTS public.company_dsn_settings (
    company_id uuid PRIMARY KEY REFERENCES public.companies(id) ON DELETE CASCADE,

    emetteur_siren text NOT NULL DEFAULT '',
    emetteur_nic text NOT NULL DEFAULT '',
    emetteur_raison_sociale text NOT NULL DEFAULT '',
    emetteur_rue text NOT NULL DEFAULT '',
    emetteur_code_postal text NOT NULL DEFAULT '',
    emetteur_ville text NOT NULL DEFAULT '',

    contact_emetteur_type text NOT NULL DEFAULT '02',
    contact_emetteur_nom text NOT NULL DEFAULT '',
    contact_emetteur_email text NOT NULL DEFAULT '',
    contact_emetteur_telephone text NOT NULL DEFAULT '',

    contacts_declaration jsonb NOT NULL DEFAULT '[]'::jsonb,

    naf text NOT NULL DEFAULT '',
    idcc text NOT NULL DEFAULT '',
    complement_adresse text NOT NULL DEFAULT '',
    commune_implantation text NOT NULL DEFAULT '',

    source text NOT NULL DEFAULT 'saisie',
    source_fichier text NOT NULL DEFAULT '',
    source_date timestamptz,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,

    CONSTRAINT company_dsn_settings_source_check
        CHECK (source IN ('saisie', 'reprise_dsn'))
);

COMMENT ON TABLE public.company_dsn_settings IS
    'Paramétrage DSN société : émetteur, contacts, NAF et IDCC déclarés.';

COMMENT ON COLUMN public.company_dsn_settings.contacts_declaration IS
    'Contacts du bloc S20.G00.07, un par organisme destinataire : [{nom, telephone, email, code_destinataire}].';

COMMENT ON COLUMN public.company_dsn_settings.source IS
    'reprise_dsn = repris d''une DSN du cabinet ; saisie = renseigné à la main.';

COMMENT ON COLUMN public.company_dsn_settings.naf IS
    'Code NAF tel que déclaré en DSN, sans séparateur (2229A, pas 22.29A).';

ALTER TABLE public.company_dsn_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_dsn_settings_select ON public.company_dsn_settings;
CREATE POLICY company_dsn_settings_select ON public.company_dsn_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

-- Écriture réservée au backend (service_role) : pas de policy INSERT/UPDATE client.
