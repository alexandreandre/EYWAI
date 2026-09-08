-- Zone 404 Mars : statut JEI activé (demande Elsa 07/09/2026 — « le lab »).
-- Date de création de l'établissement : 05/11/2025 (répertoire Sirene,
-- SIRET 99434502300018) — éligibilité JEI 8 ans, exonération pleine.
--
-- Idempotente : ON CONFLICT ne ré-écrase pas une date posée depuis.
INSERT INTO company_jei_settings (company_id, jei_enabled, date_creation_etablissement, taux_exoneration)
VALUES ('03fb17a5-134b-4c6e-9927-2083370c44d4', true, '2025-11-05', 1.0)
ON CONFLICT (company_id) DO UPDATE
SET jei_enabled = true,
    date_creation_etablissement = COALESCE(
      company_jei_settings.date_creation_etablissement,
      EXCLUDED.date_creation_etablissement
    );
