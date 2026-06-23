-- Bucket privé pour documents CSE / BDES (PV carence, BDES, etc.).

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'cse-documents',
    'cse-documents',
    false,
    52428800,
    ARRAY[
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]::text[]
)
ON CONFLICT (id) DO NOTHING;
