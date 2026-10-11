-- Notes de frais du module dans le montant net social : réglage de Colorplast.
--
-- Depuis le 11/10/2026, une note de frais validée (module « Notes de frais ») est
-- versée au net à payer mais n'entre plus dans le montant net social (BOSS,
-- Montant net social, II, A, 1 : « Les remboursements de frais professionnels
-- (au réel ou forfaitaires) dans la limite de chacun de leurs plafonds
-- d'exonération » ne sont pas pris en compte).
--
-- Colorplast fait autrement, dans Quadra : ses notes de frais restent dans le
-- montant net social (spécificité S27, constatée au rapprochement ; juillet 2026,
-- 499,15 € ; septembre 2026, 627,30 €, bulletin Quadra égal au bulletin Martine).
-- Une pratique de la gestionnaire ne se corrige pas sans son accord : ce réglage
-- la garde. Le retirer applique la règle du BOSS à Colorplast aussi.
-- Le réglage n'entre pas dans l'empreinte des bulletins : le poser ne les
-- périme pas.

update public.companies
set settings = coalesce(settings, '{}'::jsonb) || jsonb_build_object('notes_de_frais_dans_mns', true)
where id = 'dbe2b9f5-44dd-41bc-a625-36ed33d160f7'::uuid;  -- Colorplast
