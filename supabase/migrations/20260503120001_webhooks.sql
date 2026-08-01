-- Webhooks sortants (config + logs) pour intégrations BI / SI tiers

CREATE TABLE IF NOT EXISTS webhook_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  secret TEXT,
  events TEXT[] NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  last_triggered_at TIMESTAMPTZ,
  last_status_code INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS webhook_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  webhook_id UUID REFERENCES webhook_configs(id)
    ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  payload JSONB,
  response_status INT,
  response_body TEXT,
  duration_ms INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_configs_company
  ON webhook_configs(company_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_webhook
  ON webhook_logs(webhook_id);
