-- Règles CC structurées pour le moteur de paie + journal d'extraction IA
-- Compatible table legacy convention_collective_rules (souvent : idcc + rules uniquement)

CREATE TABLE IF NOT EXISTS convention_collective_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idcc TEXT NOT NULL UNIQUE,
  rules JSONB NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE convention_collective_rules
  ADD COLUMN IF NOT EXISTS id UUID DEFAULT gen_random_uuid(),
  ADD COLUMN IF NOT EXISTS agreement_id UUID,
  ADD COLUMN IF NOT EXISTS schema_version INT DEFAULT 1,
  ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS extraction_model TEXT,
  ADD COLUMN IF NOT EXISTS source_text_hash TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

UPDATE convention_collective_rules
SET schema_version = 1
WHERE schema_version IS NULL;

ALTER TABLE convention_collective_rules
  ALTER COLUMN schema_version SET DEFAULT 1,
  ALTER COLUMN schema_version SET NOT NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = 'collective_agreements_catalog'
  )
  AND NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'public'
      AND table_name = 'convention_collective_rules'
      AND constraint_name = 'convention_collective_rules_agreement_id_fkey'
  ) THEN
    ALTER TABLE convention_collective_rules
      ADD CONSTRAINT convention_collective_rules_agreement_id_fkey
      FOREIGN KEY (agreement_id)
      REFERENCES collective_agreements_catalog(id)
      ON DELETE SET NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_cc_rules_idcc ON convention_collective_rules(idcc);
CREATE INDEX IF NOT EXISTS idx_cc_rules_agreement_id ON convention_collective_rules(agreement_id);

CREATE TABLE IF NOT EXISTS cc_rules_extraction_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idcc TEXT NOT NULL,
  agreement_id UUID,
  status TEXT NOT NULL CHECK (status IN ('success', 'rejected_validation', 'error')),
  rules_proposed JSONB,
  rules_previous JSONB,
  error_message TEXT,
  model TEXT,
  tokens_used INT,
  created_at TIMESTAMPTZ DEFAULT now()
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = 'collective_agreements_catalog'
  )
  AND NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'public'
      AND table_name = 'cc_rules_extraction_log'
      AND constraint_name = 'cc_rules_extraction_log_agreement_id_fkey'
  ) THEN
    ALTER TABLE cc_rules_extraction_log
      ADD CONSTRAINT cc_rules_extraction_log_agreement_id_fkey
      FOREIGN KEY (agreement_id)
      REFERENCES collective_agreements_catalog(id)
      ON DELETE SET NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_cc_rules_log_idcc ON cc_rules_extraction_log(idcc);
CREATE INDEX IF NOT EXISTS idx_cc_rules_log_agreement_id ON cc_rules_extraction_log(agreement_id);
CREATE INDEX IF NOT EXISTS idx_cc_rules_log_created_at ON cc_rules_extraction_log(created_at DESC);
