-- Suivi des envois compta / banque par période

CREATE TABLE IF NOT EXISTS export_dispatches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('compta', 'banque')),
  period TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'generated'
    CHECK (status IN ('generated', 'transmitted', 'failed')),
  export_ids UUID[] NOT NULL DEFAULT '{}',
  parameters JSONB DEFAULT '{}',
  transmitted_at TIMESTAMPTZ,
  transmitted_by UUID,
  transmission_note TEXT,
  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (company_id, channel, period)
);

CREATE INDEX IF NOT EXISTS idx_export_dispatches_company_channel_period
  ON export_dispatches(company_id, channel, period);
