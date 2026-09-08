-- MAJI : adresse du siège social = 10 rue des Rubis, 38280 Villette d'Anthon
-- (déclarante, 08/09/2026). La fiche portait une adresse de démonstration
-- (Place des 4 dauphins, 13100 Aix-en-Provence) qui partait sur les bulletins
-- et documents.
--
-- Ciblage par id (identique prod/test — base de test = copie de la prod).
-- Idempotente : le garde sur l'ancien code postal ne réécrit jamais une
-- valeur corrigée depuis.
UPDATE companies
SET adresse_rue = '10 rue des Rubis',
    adresse_code_postal = '38280',
    adresse_ville = 'Villette d''Anthon'
WHERE id = '113b2f33-82ec-4cec-8d3a-f16cda8f74f2'
  AND adresse_code_postal = '13100';
