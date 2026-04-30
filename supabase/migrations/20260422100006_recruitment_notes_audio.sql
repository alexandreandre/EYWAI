-- Audio optionnel sur les notes de recrutement
ALTER TABLE recruitment_notes
ADD COLUMN IF NOT EXISTS audio_url text;
