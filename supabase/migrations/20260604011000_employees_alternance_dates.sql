-- Dates de contrat nécessaires au régime des alternants (apprentis).
-- date_debut_execution = 1er jour d'exécution (fait générateur du régime apprenti).
-- date_conclusion_contrat = date de signature (option de maintien de l'ancien régime).
-- L'option de maintien elle-même est stockée dans employees.specificites_paie
-- (clé "maintien_regime_apprenti"), pas besoin de colonne dédiée.

ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS date_conclusion_contrat date,
    ADD COLUMN IF NOT EXISTS date_debut_execution date;

COMMENT ON COLUMN public.employees.date_conclusion_contrat IS
    'Date de conclusion (signature) du contrat — sert à l''option de maintien du régime apprenti.';
COMMENT ON COLUMN public.employees.date_debut_execution IS
    'Premier jour d''exécution du contrat — fait générateur du régime d''exonération apprenti.';
