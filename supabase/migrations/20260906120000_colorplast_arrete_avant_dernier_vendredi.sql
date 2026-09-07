-- Colorplast : arrêté des variables à l'avant-dernier vendredi.
--
-- Pratique du groupe (paies bouclées vers le 24) : les variables du bulletin
-- de M couvrent les semaines complètes du lundi qui suit l'arrêté de M-1 au
-- dimanche de la semaine de l'avant-dernier vendredi de M (ex. juillet 2026 :
-- 22/06 → 26/07, soit S26 → S30). Le moteur lit ce réglage dans
-- companies.paie_jour_de_fin (4 = vendredi) et companies.paie_occurrence
-- (-2 = avant-dernier) — voir
-- backend/app/modules/payroll/engine/period_forfait.py::definir_periode_de_paie.
--
-- L'import DSN avait posé (31, -1) = mois civil pour les 7 sociétés du
-- groupe ; seule Colorplast bascule (recette paie, demande RH du 03/09/2026).
-- Les autres restent au mois civil tant que leur pratique n'est pas confirmée.
--
-- Idempotente : rejouer l'UPDATE réécrit les mêmes valeurs.
UPDATE companies
SET paie_jour_de_fin = 4,
    paie_occurrence  = -2
WHERE siren = '802485169'; -- Colorplast
