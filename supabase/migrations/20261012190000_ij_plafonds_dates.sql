-- Plafonds d'IJ datés : le barème `ij_plafonds` porte ses paliers.
--
-- Le barème (montant maximal de l'indemnité journalière par jour) n'avait
-- qu'une valeur, sans date. Le décret n° 2026-909 du 30/09/2026 abaisse le
-- plafond des IJ d'accident du travail et de maladie professionnelle pour les
-- arrêts qui surviennent à compter du 01/11/2026 : salaire journalier de base
-- retenu dans la limite de 0,226 % du PASS au lieu de 0,834 %.
-- https://www.service-public.gouv.fr/particuliers/actualites/A19080
-- (publiée le 08/10/2026, ouverte le 12/10/2026).
--
-- PASS 2026 = 48 060 € :
--   avant le 01/11/2026 : 0,834 % = 400,82 €, soit 240,49 € (60 %) puis 320,66 € (80 %, dès le 29e jour) ;
--   dès le 01/11/2026  : 0,226 % = 108,62 €, soit  65,17 € (60 %) puis  86,89 € (80 %).
-- Maladie (42,97 €) et maternité-paternité (104,02 €) : montants actuels du
-- barème, inchangés par le décret.
--
-- Le moteur lit le palier en vigueur à la date de l'accident quand elle est
-- saisie, sinon au début de l'arrêt (celui de l'arrêt prolongé) : un arrêt
-- d'octobre garde 240,49 €, même si le relevé automatique passe le barème à
-- 65,17 €. Le relevé garde les paliers. Sans eux, le barème se lit tel quel.
--
-- Écrit le 12/10/2026, NON appliqué. Idempotente : n'écrit que si la clé
-- `historique` est absente. Les valeurs courantes du barème ne changent pas.

UPDATE payroll_config
SET config_data = config_data || jsonb_build_object(
      'historique', jsonb_build_array(
        jsonb_build_object(
          'date_debut', '2026-01-01',
          'maladie', 42.97,
          'maternite_paternite', 104.02,
          'at_mp', 240.49,
          'at_mp_majoree', 320.66
        ),
        jsonb_build_object(
          'date_debut', '2026-11-01',
          'maladie', 42.97,
          'maternite_paternite', 104.02,
          'at_mp', 65.17,
          'at_mp_majoree', 86.89
        )
      )
    )
WHERE config_key = 'ij_plafonds'
  AND is_active
  AND NOT (config_data ? 'historique');
