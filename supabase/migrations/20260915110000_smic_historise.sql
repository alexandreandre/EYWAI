-- Historique du SMIC horaire : le bulletin d'un mois passé doit porter le SMIC
-- de ce mois-là, pas celui d'aujourd'hui.
--
-- Le barème `smic` n'avait qu'une valeur active, sans date. Un bulletin de
-- janvier 2026 refabriqué affichait donc 12,31 €, le SMIC de septembre. Le
-- cabinet imprime bien celui de la période : sur les bulletins Colorplast de
-- 2026, 12,02 € de janvier à mai et 12,31 € à partir de juin.
--
-- Ce n'est pas qu'une question d'affichage. Le SMIC plafonne l'exonération de
-- cotisations des apprentis : une valeur trop haute sur un mois passé relève
-- leur plafond et change leurs cotisations. Colorplast n'a pas d'apprenti,
-- Mont Blanc Composite et Lewis si.
--
-- La réduction générale n'est pas concernée : elle lit sa propre valeur gelée,
-- `reduction_generale.smic_reference_horaire`, déjà juste.
--
-- Les paliers antérieurs à 2026 ne sont pas renseignés, faute de bulletin de
-- cabinet pour les confirmer : une période plus ancienne retombe sur la valeur
-- courante, comme avant.
--
-- Idempotent : n'écrit que si la clé `historique` est absente.

UPDATE payroll_config
SET config_data = config_data || jsonb_build_object(
      'historique', jsonb_build_array(
        jsonb_build_object('date_debut', '2026-01-01', 'cas_general', 12.02),
        jsonb_build_object('date_debut', '2026-06-01', 'cas_general', 12.31)
      )
    )
WHERE config_key = 'smic'
  AND is_active
  AND NOT (config_data ? 'historique');
