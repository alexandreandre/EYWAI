-- Saisie sur salaire : montant total de la dette.
--
-- Demande d'Elsa (Zone 404, 24/11/2026) : la saisie ne connaissait que la
-- mensualité (`amount`). Avec le montant total, Martine calcule le reste dû
-- (montant total moins les retenues déjà faites, `salary_seizure_deductions`),
-- plafonne la retenue du mois au reste dû, et termine la saisie (statut
-- « closed ») quand il atteint zéro. La quotité saisissable reste le plafond
-- légal : le reste dû s'y ajoute.
--
-- Colonne vide : la saisie court sans fin, comme avant. Aucune donnée n'est
-- modifiée. Idempotente. À appliquer avec le code qui la lit (la liste des
-- saisies et le rappel des retenues reprises la lisent).

ALTER TABLE public.salary_seizures
    ADD COLUMN IF NOT EXISTS montant_total numeric;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'salary_seizures_montant_total_positif'
    ) THEN
        ALTER TABLE public.salary_seizures
            ADD CONSTRAINT salary_seizures_montant_total_positif
            CHECK (montant_total IS NULL OR montant_total >= 0);
    END IF;
END $$;

COMMENT ON COLUMN public.salary_seizures.montant_total IS
    'Montant total de la dette : la retenue est plafonnée au reste dû (total moins les retenues déjà faites) et la saisie se termine à zéro. Vide : la saisie court sans fin.';
