-- Intégration Net-entreprises / Télétransmission DSN.
--
-- Ossature uniquement : tant qu'aucun identifiant/certificat n'est saisi, le mode
-- « manuel » reste actif (dépôt manuel sur net-entreprises.fr). Aucune donnée
-- sensible n'est exposée au frontend (le backend masque les secrets).
--
-- Deux tables :
--  1) company_net_entreprises_config : config de connexion par entreprise (1 ligne / entreprise).
--  2) dsn_transmissions : suivi de chaque dépôt DSN (statut, accusé, retours CRM).

-- 1) Configuration de connexion Net-entreprises (par entreprise)
CREATE TABLE IF NOT EXISTS public.company_net_entreprises_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
  enabled BOOLEAN NOT NULL DEFAULT false,
  mode TEXT NOT NULL DEFAULT 'manual'
    CHECK (mode IN ('manual', 'api_certificat', 'api_declarant')),
  siret_declarant TEXT,
  raison_sociale_declarant TEXT,
  identifiant TEXT,
  contact_email TEXT,
  certificat_label TEXT,
  certificat_expires_at DATE,
  -- Référence vers le secret (jamais renvoyée au frontend) ; aucun secret en clair attendu ici.
  secret_ref TEXT,
  last_test_at TIMESTAMPTZ,
  last_test_status TEXT
    CHECK (last_test_status IN ('success', 'failure', 'manual', 'not_configured')),
  last_test_message TEXT,
  created_by UUID,
  updated_by UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT company_net_entreprises_config_company_unique UNIQUE (company_id)
);

CREATE INDEX IF NOT EXISTS idx_company_net_entreprises_config_company
  ON public.company_net_entreprises_config (company_id);

-- 2) Suivi des télétransmissions DSN (1 ligne / dépôt)
CREATE TABLE IF NOT EXISTS public.dsn_transmissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
  export_id UUID,
  period TEXT NOT NULL,
  dsn_type TEXT NOT NULL DEFAULT 'dsn_mensuelle_normale',
  status TEXT NOT NULL DEFAULT 'generated'
    CHECK (status IN ('generated', 'manual', 'queued', 'sent', 'acknowledged', 'rejected')),
  mode TEXT NOT NULL DEFAULT 'manual'
    CHECK (mode IN ('manual', 'api_certificat', 'api_declarant')),
  net_entreprises_ref TEXT,
  submitted_at TIMESTAMPTZ,
  acknowledged_at TIMESTAMPTZ,
  crm_retour JSONB,
  error_message TEXT,
  created_by UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dsn_transmissions_company
  ON public.dsn_transmissions (company_id);
CREATE INDEX IF NOT EXISTS idx_dsn_transmissions_company_period
  ON public.dsn_transmissions (company_id, period);
CREATE INDEX IF NOT EXISTS idx_dsn_transmissions_export
  ON public.dsn_transmissions (export_id);

-- RLS : accès aux lignes dont l'entreprise est liée à l'utilisateur (user_company_accesses).
-- Le backend (service_role) reste maître des écritures sensibles ; les secrets ne sont
-- jamais renvoyés au frontend par l'API.

ALTER TABLE public.company_net_entreprises_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY company_net_entreprises_config_select
  ON public.company_net_entreprises_config
  FOR SELECT
  TO authenticated
  USING (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

CREATE POLICY company_net_entreprises_config_insert
  ON public.company_net_entreprises_config
  FOR INSERT
  TO authenticated
  WITH CHECK (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

CREATE POLICY company_net_entreprises_config_update
  ON public.company_net_entreprises_config
  FOR UPDATE
  TO authenticated
  USING (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  )
  WITH CHECK (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

ALTER TABLE public.dsn_transmissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY dsn_transmissions_select
  ON public.dsn_transmissions
  FOR SELECT
  TO authenticated
  USING (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

CREATE POLICY dsn_transmissions_insert
  ON public.dsn_transmissions
  FOR INSERT
  TO authenticated
  WITH CHECK (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );

CREATE POLICY dsn_transmissions_update
  ON public.dsn_transmissions
  FOR UPDATE
  TO authenticated
  USING (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  )
  WITH CHECK (
    company_id IN (
      SELECT uca.company_id
      FROM public.user_company_accesses uca
      WHERE uca.user_id = auth.uid()
    )
  );
