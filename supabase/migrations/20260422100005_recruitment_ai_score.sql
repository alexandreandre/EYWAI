-- Colonnes scoring IA des candidatures (recrutement)
ALTER TABLE recruitment_candidates
  ADD COLUMN IF NOT EXISTS ai_score integer,
  ADD COLUMN IF NOT EXISTS ai_score_detail jsonb,
  ADD COLUMN IF NOT EXISTS ai_scored_at timestamptz;
