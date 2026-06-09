-- Propositions de formation issues des conventions collectives (mutualisées par IDCC)

CREATE TABLE IF NOT EXISTS cc_training_recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idcc TEXT NOT NULL,
  agreement_id UUID,
  title TEXT NOT NULL,
  obligation_level TEXT NOT NULL DEFAULT 'recommandee'
    CHECK (obligation_level IN ('obligatoire', 'recommandee')),
  pedagogical_objective TEXT,
  legal_reference TEXT,
  target_roles JSONB NOT NULL DEFAULT '[]'::jsonb,
  periodicity TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,
  source TEXT NOT NULL DEFAULT 'ai' CHECK (source IN ('ai', 'manual')),
  confidence TEXT,
  extracted_at TIMESTAMPTZ,
  extraction_model TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
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
      AND table_name = 'cc_training_recommendations'
      AND constraint_name = 'cc_training_recommendations_agreement_id_fkey'
  ) THEN
    ALTER TABLE cc_training_recommendations
      ADD CONSTRAINT cc_training_recommendations_agreement_id_fkey
      FOREIGN KEY (agreement_id)
      REFERENCES collective_agreements_catalog(id)
      ON DELETE SET NULL;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cc_training_reco_idcc_title
  ON cc_training_recommendations (idcc, lower(title));

CREATE INDEX IF NOT EXISTS idx_cc_training_reco_idcc_active
  ON cc_training_recommendations (idcc)
  WHERE is_active = true;

COMMENT ON TABLE cc_training_recommendations IS
  'Propositions de formation extraites ou saisies manuellement par convention collective (IDCC).';

ALTER TABLE training_catalog
  ADD COLUMN IF NOT EXISTS source_cc_recommendation_id UUID;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'public'
      AND table_name = 'training_catalog'
      AND constraint_name = 'training_catalog_source_cc_recommendation_id_fkey'
  ) THEN
    ALTER TABLE training_catalog
      ADD CONSTRAINT training_catalog_source_cc_recommendation_id_fkey
      FOREIGN KEY (source_cc_recommendation_id)
      REFERENCES cc_training_recommendations(id)
      ON DELETE SET NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_training_catalog_source_cc_reco
  ON training_catalog (company_id, source_cc_recommendation_id)
  WHERE source_cc_recommendation_id IS NOT NULL;
