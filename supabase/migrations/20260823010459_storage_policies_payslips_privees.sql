-- Storage : retrait des policies {public} sur les bulletins (23/08/2026).
--
-- Nommées « Accès complet pour le backend » mais posées sur le rôle
-- {public} : elles ouvraient à l'anonyme le SELECT, l'UPDATE et le DELETE
-- des objets du bucket payslips (1384 bulletins nominatifs). Le backend
-- n'en a jamais eu besoin : il travaille en service_role, qui contourne
-- la RLS.
--
-- Idempotent : ré-exécutable sans erreur.
DROP POLICY IF EXISTS "Accès complet pour le backend mymt8r_0" ON storage.objects;
DROP POLICY IF EXISTS "Accès complet pour le backend mymt8r_1" ON storage.objects;
DROP POLICY IF EXISTS "Accès complet pour le backend mymt8r_2" ON storage.objects;
DROP POLICY IF EXISTS "Accès complet pour le backend mymt8r_3" ON storage.objects;
