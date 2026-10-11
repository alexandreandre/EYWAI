-- Effectif retenu pour les seuils de paie (11, 20, 50 salariés) en 2026.
--
-- Le moteur lisait companies.effectif, que tient le déclencheur
-- profiles_update_company_effectif : le nombre de comptes de la société
-- (admins, RH et salariés partis compris). Colorplast y était à 19 pour
-- environ 5 salariés, Comitech à 25 pour 15 à 17, MAJI à 14 pour 5 à 9
-- (enquête du 10/10/2026). Le moteur lit désormais settings.effectif_seuils,
-- par année ; la colonne reste le nombre de comptes, pour l'affichage.
--
-- Valeurs de départ : effectif moyen de 2025 estimé depuis les DSN et les
-- fiches (CSS R130-1), dans le palier que confirment les taux des DSN Quadra
-- de 2026. À remplacer par le compte rendu n° 118 de l'Urssaf (effectif moyen
-- annuel) dès qu'il est reçu, depuis la carte « Paramètres de paie ».
-- Une valeur déjà saisie pour 2026 n'est jamais écrasée.

update public.companies as c
set settings = coalesce(c.settings, '{}'::jsonb)
  || jsonb_build_object(
    'effectif_seuils',
    jsonb_build_object('2026', v.effectif) || coalesce(c.settings -> 'effectif_seuils', '{}'::jsonb)
  )
from (
  values
    ('dbe2b9f5-44dd-41bc-a625-36ed33d160f7'::uuid, 5),   -- Colorplast : moins de 11
    ('12cd8c71-da13-43f9-9151-475c4d5e8812'::uuid, 16),  -- Comitech Composite : de 11 à 19
    ('113b2f33-82ec-4cec-8d3a-f16cda8f74f2'::uuid, 7),   -- MAJI : moins de 11
    ('03fb17a5-134b-4c6e-9927-2083370c44d4'::uuid, 2),   -- Zone 404 Mars : créée en 2026
    ('b3c747e4-5094-4252-b0e6-5b711a5b4e81'::uuid, 30),  -- LEWIS : de 20 à 49
    ('b541df31-e964-485e-ac36-cf580633fd1d'::uuid, 70),  -- Mont Blanc Composite : 50 et plus
    ('18de8de4-eb52-4a7c-a9f4-4c7321e6f11f'::uuid, 70)   -- Cartol Industrie : 50 et plus
) as v(id, effectif)
where c.id = v.id;
