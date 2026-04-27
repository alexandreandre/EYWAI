-- Habilitations / certifications (Pack Talent)
-- Après déploiement : créer le bucket Storage privé « certifications » (service_role / policies adaptées).

CREATE TABLE IF NOT EXISTS certification_referential (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  name text NOT NULL,
  code text,
  category text NOT NULL,
  validity_months integer,
  alert_days integer NOT NULL DEFAULT 60,
  certifying_body text,
  description text,
  legal_link text,
  status text NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_certification_referential_company
  ON certification_referential (company_id);

CREATE TABLE IF NOT EXISTS employee_certifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  employee_id uuid NOT NULL,
  certification_id uuid NOT NULL REFERENCES certification_referential (id) ON DELETE RESTRICT,
  obtained_date date NOT NULL,
  expiry_date date,
  certifying_body text,
  certificate_number text,
  certificate_url text,
  notes text,
  is_archived boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_employee_certifications_company
  ON employee_certifications (company_id);

CREATE INDEX IF NOT EXISTS idx_employee_certifications_employee
  ON employee_certifications (employee_id);

CREATE INDEX IF NOT EXISTS idx_employee_certifications_cert
  ON employee_certifications (certification_id);

CREATE INDEX IF NOT EXISTS idx_employee_certifications_active_ref
  ON employee_certifications (certification_id, company_id)
  WHERE is_archived = false;
