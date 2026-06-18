-- Colonnes audit étendues pour diagnostic OCR / import pointages
ALTER TABLE schedule_import_runs
  ADD COLUMN IF NOT EXISTS extraction_method text,
  ADD COLUMN IF NOT EXISTS raw_ocr_excerpt text,
  ADD COLUMN IF NOT EXISTS file_hash text,
  ADD COLUMN IF NOT EXISTS parse_confidence numeric,
  ADD COLUMN IF NOT EXISTS coverage_avg numeric;

COMMENT ON COLUMN schedule_import_runs.extraction_method IS
  'Méthode extraction document (PDF natif, OCR PDF, OCR image).';
COMMENT ON COLUMN schedule_import_runs.raw_ocr_excerpt IS
  'Extrait OCR brut (max ~20k chars) pour diagnostic import.';
COMMENT ON COLUMN schedule_import_runs.file_hash IS
  'Hash SHA-256 du fichier importé.';
COMMENT ON COLUMN schedule_import_runs.parse_confidence IS
  'Confiance parseur Cegid (0-1) si applicable.';
COMMENT ON COLUMN schedule_import_runs.coverage_avg IS
  'Couverture moyenne jours lus / attendus par salarié.';
