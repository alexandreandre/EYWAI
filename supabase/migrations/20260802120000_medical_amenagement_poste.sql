-- Case « aménagement de poste » saisie à l'enregistrement d'une visite médicale réalisée.
-- Voir docs/superpowers/specs/2026-08-02-case-amenagement-suivi-medical-design.md
ALTER TABLE medical_follow_up_obligations
  ADD COLUMN IF NOT EXISTS amenagement_poste BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN medical_follow_up_obligations.amenagement_poste IS
  'True si la visite réalisée a débouché sur un aménagement de poste. Saisi par la RH, jamais calculé.';
