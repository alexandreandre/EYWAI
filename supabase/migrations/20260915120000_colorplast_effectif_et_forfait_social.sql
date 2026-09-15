-- Colorplast : effectif corrigé et forfait social sur la prévoyance.
--
-- EFFECTIF. La société était enregistrée à 17 salariés alors qu'elle n'a que 9
-- fiches — 6 actifs et 3 partis, ces derniers tous embauchés en 2026. Sur les
-- six autres sociétés du groupe, l'effectif déclaré colle au nombre de fiches à
-- un près, deux sont même exactement égaux : Colorplast était la seule à
-- s'écarter, et de huit. Le champ étant saisi à la main, c'est une erreur de
-- saisie, vraisemblablement faite à la création de la société en novembre 2025,
-- avant l'import des salariés.
--
-- La correction fait passer la contribution formation de 1 % à 0,55 %, le taux
-- des employeurs de moins de 11 salariés. C'est bien ce que le cabinet déclare
-- à l'URSSAF : DSN de janvier 2026, cotisation individuelle code 128, base
-- 3 023,40, montant 16,63, taux 0,550 pour Bugny.
--
-- Seul le seuil de 11 est franchi : 17 comme 9 sont déjà sous 20 (déduction
-- forfaitaire heures sup) et sous 50 (aide au logement, réduction générale).
-- Le taux de formation est donc la seule chose qui bouge.
--
-- FORFAIT SOCIAL. Le cabinet facture 8 % sur les contributions patronales de
-- prévoyance et de mutuelle (DSN code 071, taux 8,000, base 43,29 = 14,06 +
-- 29,23 pour Bugny). Nous ne le produisions pas : les quatre non-cadres
-- passaient par le barème global, sans ligne de prévoyance sur leur fiche.
--
-- RÉSERVE. Les employeurs de moins de onze salariés sont en principe dispensés
-- de ce forfait social. La déclaration du cabinet porte donc deux mentions qui
-- se contredisent : un taux de formation réservé aux moins de 11 et un forfait
-- social dont ces mêmes employeurs sont dispensés. On reproduit le cabinet --
-- sous-déclarer serait plus risqué que sur-déclarer, et c'est ce que Colorplast
-- paie déjà -- et la question est posée à Gaëlle pour vérification par Cegid.
-- Si elle confirme, retirer `forfait_social` de ces lignes suffit.
--
-- Idempotent.

UPDATE companies SET effectif = 9
WHERE company_name = 'Colorplast' AND effectif <> 9;

UPDATE employees e
SET specificites_paie = jsonb_set(
      e.specificites_paie, '{prevoyance,lignes_specifiques}',
      jsonb_build_array(jsonb_build_object(
        'id','prevoyance_colorplast',
        'libelle','Prévoyance Non-Cadre Tranche 1',
        'base','brut_plafonne',
        'salarial',0.00465,
        'patronal',0.00465,
        'forfait_social',0.08))
    ), updated_at = now()
FROM companies c
WHERE c.id = e.company_id AND c.company_name = 'Colorplast'
  AND e.statut = 'Non-Cadre'
  AND coalesce(jsonb_array_length(e.specificites_paie->'prevoyance'->'lignes_specifiques'), 0) = 0;

UPDATE employees e
SET specificites_paie = jsonb_set(
      e.specificites_paie, '{prevoyance,lignes_specifiques}',
      (SELECT jsonb_agg(CASE WHEN l ? 'forfait_social' THEN l
                             ELSE l || jsonb_build_object('forfait_social', 0.08) END)
       FROM jsonb_array_elements(e.specificites_paie->'prevoyance'->'lignes_specifiques') l)
    ), updated_at = now()
FROM companies c
WHERE c.id = e.company_id AND c.company_name = 'Colorplast'
  AND e.statut = 'Cadre'
  AND coalesce(jsonb_array_length(e.specificites_paie->'prevoyance'->'lignes_specifiques'), 0) > 0
  AND NOT (e.specificites_paie->'prevoyance'->'lignes_specifiques'->0 ? 'forfait_social');
