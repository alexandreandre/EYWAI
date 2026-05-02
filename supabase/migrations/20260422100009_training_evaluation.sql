-- Évaluation post-formation + certificat sur inscription (Pack Talent Bloc 2)

ALTER TABLE training_enrollments
    ADD COLUMN IF NOT EXISTS rating integer CHECK (rating >= 1 AND rating <= 5),
    ADD COLUMN IF NOT EXISTS evaluation_comment text,
    ADD COLUMN IF NOT EXISTS evaluated_at timestamptz,
    ADD COLUMN IF NOT EXISTS certificate_url text,
    ADD COLUMN IF NOT EXISTS certificate_uploaded_at timestamptz;
