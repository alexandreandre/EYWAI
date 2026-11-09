-- R-657 : retirer les quatre politiques « true » en écriture sur collective_agreement_texts.
--
-- Constat sur la base de test (lecture du 09/11/2026) : ALL, INSERT, UPDATE et DELETE
-- laissaient tout compte connecté écrire ce cache de textes de convention. La politique
-- de lecture reste ; tout le code écrit par la clé service_role, qui ignore la RLS.
-- Idempotente. Retour arrière : les quatre CREATE POLICY en commentaire en bas de fichier.

DROP POLICY IF EXISTS "Permettre tout pour authentifiés" ON public.collective_agreement_texts;
DROP POLICY IF EXISTS "Permettre l'insertion pour les utilisateurs authentifiés" ON public.collective_agreement_texts;
DROP POLICY IF EXISTS "Permettre la mise à jour pour les utilisateurs authentifiés" ON public.collective_agreement_texts;
DROP POLICY IF EXISTS "Permettre la suppression pour les utilisateurs authentifiés" ON public.collective_agreement_texts;

-- Retour arrière :
-- CREATE POLICY "Permettre tout pour authentifiés" ON public.collective_agreement_texts FOR ALL TO authenticated USING (true) WITH CHECK (true);
-- CREATE POLICY "Permettre l'insertion pour les utilisateurs authentifiés" ON public.collective_agreement_texts FOR INSERT TO authenticated WITH CHECK (true);
-- CREATE POLICY "Permettre la mise à jour pour les utilisateurs authentifiés" ON public.collective_agreement_texts FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
-- CREATE POLICY "Permettre la suppression pour les utilisateurs authentifiés" ON public.collective_agreement_texts FOR DELETE TO authenticated USING (true);
