-- Configuration SMTP / expéditeur de la plateforme (singleton).
-- Accès backend uniquement via service_role ; l'API super-admin lit/écrit via le client admin.

CREATE TABLE IF NOT EXISTS public.platform_email_settings (
  id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  smtp_host TEXT,
  smtp_port INTEGER NOT NULL DEFAULT 587,
  smtp_user TEXT,
  smtp_password TEXT,
  smtp_security TEXT NOT NULL DEFAULT 'starttls'
    CHECK (smtp_security IN ('starttls', 'ssl', 'none')),
  from_email TEXT,
  from_name TEXT NOT NULL DEFAULT 'EYWAI',
  reply_to TEXT,
  support_recipients TEXT[] NOT NULL DEFAULT ARRAY['contact@eywai.fr']::TEXT[],
  is_active BOOLEAN NOT NULL DEFAULT false,
  updated_by UUID,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.platform_email_settings IS
  'Paramètres SMTP globaux (une seule ligne). Si is_active=false, repli sur variables d''environnement.';

ALTER TABLE public.platform_email_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY platform_email_settings_service_all
  ON public.platform_email_settings
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
