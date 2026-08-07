-- Le NIR identifie une personne, pas un contrat.
--
-- employees.nir portait une unicité globale : un même NIR ne pouvait apparaître
-- qu'une fois, toutes sociétés confondues. Or le groupe compte sept sociétés et
-- une même personne peut y tenir deux contrats — CHAMBERT Lucas est salarié de
-- Comitech et a fait un CDD chez Mont Blanc, BARBERET Théo est passé de MAJI à
-- Zone 404, DA SILVA CARDOSO de Colorplast à Comitech. La contrainte interdisait
-- leur seconde fiche.
--
-- Elle a été contournée en amputant le NIR de sa clé de contrôle : cinq fiches
-- portaient treize chiffres au lieu de quinze. Un NIR incomplet est refusé en
-- DSN, ce qui deviendra bloquant dès qu'EYWAI produira les déclarations. La
-- troncature n'était donc pas une négligence de saisie mais la trace du
-- contournement, et c'est la contrainte qu'il faut corriger.
--
-- Unicité visée : une personne au plus une fois par société. Vérifié avant
-- écriture, aucun couple (company_id, nir) n'est en double aujourd'hui.

ALTER TABLE public.employees DROP CONSTRAINT IF EXISTS employees_nir_key;

-- Les NIR se complètent avant la nouvelle unicité : trois d'entre eux
-- retrouvent la même valeur que leur fiche jumelle, dans une autre société.
-- La clé de contrôle est déterministe (97 moins le NIR modulo 97) ; le calcul a
-- été validé sur les trois cas où la fiche jumelle porte déjà le NIR complet.
UPDATE public.employees
SET nir = nir || lpad((97 - (nir::bigint % 97))::text, 2, '0')
WHERE nir ~ '^[0-9]{13}$';

-- Index partiel plutôt que contrainte : les fiches sans NIR connu ne doivent pas
-- se gêner entre elles, et une chaîne vide n'est pas une identité.
CREATE UNIQUE INDEX IF NOT EXISTS employees_nir_unique_par_societe
    ON public.employees (company_id, nir)
    WHERE nir IS NOT NULL AND nir <> '';

COMMENT ON INDEX public.employees_nir_unique_par_societe IS
    'Une personne au plus une fois par société. L''unicité globale d''origine interdisait les contrats multiples au sein du groupe.';
