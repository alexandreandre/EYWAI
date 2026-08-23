-- Bucket 'expense_receipts' repassé en privé (23/08/2026, audit sécurité).
--
-- Les justificatifs de notes de frais (achats, adresses, identités) étaient
-- servis par /storage/v1/object/public/... sans authentification — vérifié
-- en réel (HTTP 200, image de 1 Mo). La fermeture attendait son préalable,
-- désormais en production : le frontend demande une URL signée à
-- GET /api/expenses/receipt-url (réservée RH) au lieu de fabriquer l'URL.
--
-- Les policies storage nommées « Accès complet pour le backend » visaient en
-- fait le rôle {public} : elles ouvraient aussi UPDATE et DELETE. Le backend
-- travaille en service_role, qui contourne la RLS — elles sont inutiles.
--
-- Après application, seul le bucket 'logos' reste public (logos d'entreprise,
-- légitime). Vérifié hors cache CDN : 400 en anonyme.
--
-- Idempotent : ré-exécutable sans erreur.

UPDATE storage.buckets SET public = false WHERE id = 'expense_receipts';

DROP POLICY IF EXISTS "Accès complet pour le backend uwccaq_0" ON storage.objects;
DROP POLICY IF EXISTS "Accès complet pour le backend uwccaq_1" ON storage.objects;
DROP POLICY IF EXISTS "Accès complet pour le backend uwccaq_2" ON storage.objects;
DROP POLICY IF EXISTS "Accès complet pour le backend uwccaq_3" ON storage.objects;
