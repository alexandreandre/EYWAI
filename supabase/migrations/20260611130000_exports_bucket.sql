-- Bucket Supabase pour les fichiers d'export (paie, compta, banque, RH, DSN).
--
-- Le backend opère avec la clé service_role (bypass RLS) pour l'upload et la
-- génération des URLs signées ; le bucket reste donc privé et tout
-- téléchargement passe par une URL signée générée côté serveur.
--
-- Idempotent : ne recrée pas le bucket s'il existe déjà (créé manuellement
-- historiquement sur l'instance partagée dev/prod).

INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES (
    'exports',
    'exports',
    false,
    52428800
)
ON CONFLICT (id) DO NOTHING;
