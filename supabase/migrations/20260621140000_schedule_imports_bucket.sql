-- Bucket Supabase pour les PDF relevés de pointages (import temporaire).
--
-- Le backend utilise la clé service_role pour upload/téléchargement ;
-- le bucket reste privé, accès via le backend uniquement.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'schedule-imports',
    'schedule-imports',
    false,
    52428800,
    ARRAY['application/pdf', 'image/png', 'image/jpeg', 'image/webp']
)
ON CONFLICT (id) DO NOTHING;
