-- Plafond horaire de la Sécurité sociale 2026 : 30 € (valeur officielle).
--
-- Le plafond horaire est fixé par arrêté, il n'est pas le plafond mensuel divisé
-- par 151,67 h. 2026 : 30 € par heure, 220 € par jour, 4 005 € par mois,
-- 48 060 € par an.
-- Sources : Urssaf, « Accueillir un stagiaire étudiant » (« le plafond horaire de
-- la Sécurité sociale qui est de 30 € pour 2026 »)
-- https://www.urssaf.fr/accueil/employeur/embaucher-gerer-salaries/embaucher/stagiaire-etudiant.html
-- et Urssaf, page des plafonds de la Sécurité sociale
-- https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/plafonds-securite-sociale.html
--
-- Avant : `pss.horaire` valait 26 (calcul 4 005 / 151,67) et `stage` n'avait pas de
-- `plafond_horaire_ss`, donc pas de franchise de gratification de stage (4,50 € par heure =
-- 15 % de 30 €).
--
-- Ne touche que les lignes nationales actives `pss` et `stage`, par jsonb_set
-- ciblé (aucune autre clé réécrite), et seulement pour le barème 2026
-- (plafond annuel 48 060 ou mensuel 4 005). Idempotent.

UPDATE payroll_config
SET config_data = jsonb_set(config_data, '{horaire}', '30'::jsonb, true)
WHERE config_key = 'pss'
  AND is_active
  AND company_id IS NULL
  AND (
        (config_data->>'annuel')::numeric = 48060
        OR (config_data->>'mensuel')::numeric = 4005
      )
  AND (config_data->>'horaire') IS DISTINCT FROM '30';

UPDATE payroll_config s
SET config_data = jsonb_set(s.config_data, '{plafond_horaire_ss}', '30'::jsonb, true)
WHERE s.config_key = 'stage'
  AND s.is_active
  AND s.company_id IS NULL
  AND (s.config_data->>'plafond_horaire_ss') IS DISTINCT FROM '30'
  AND EXISTS (
        SELECT 1
        FROM payroll_config p
        WHERE p.config_key = 'pss'
          AND p.is_active
          AND p.company_id IS NULL
          AND (
                (p.config_data->>'annuel')::numeric = 48060
                OR (p.config_data->>'mensuel')::numeric = 4005
              )
      );
