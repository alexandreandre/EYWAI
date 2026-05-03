-- Exports planifiés (fréquence + prochaine exécution ; envoi différé / worker hors scope)

CREATE TABLE IF NOT EXISTS scheduled_exports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL,
  name TEXT NOT NULL,
  export_type TEXT NOT NULL,
  frequency TEXT NOT NULL
    CHECK (frequency IN ('daily', 'weekly', 'monthly')),
  day_of_week INT,
  day_of_month INT,
  hour_utc INT NOT NULL DEFAULT 6,
  recipients TEXT[],
  is_active BOOLEAN DEFAULT TRUE,
  last_run_at TIMESTAMPTZ,
  next_run_at TIMESTAMPTZ,
  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_exports_company
  ON scheduled_exports(company_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_exports_next_run
  ON scheduled_exports(next_run_at)
  WHERE is_active = TRUE;
