-- Saisie sur salaire : montant total de la dette.
--
-- Demande d'Elsa (Zone 404, 24/11/2026) : la saisie ne connaissait que la
-- mensualité (`amount`). Avec le montant total, Martine calcule le reste dû
-- (montant total moins les retenues déjà faites, `salary_seizure_deductions`),
-- plafonne la retenue du mois au reste dû et ne retient plus rien quand il
-- atteint zéro (le statut n'est pas touché : un bulletin supprimé ou un total
-- relevé fait remonter le reste dû, et la retenue reprend). La quotité
-- saisissable reste le plafond légal : le reste dû s'y ajoute.
--
-- Colonne vide : la saisie court sans fin, comme avant. Aucune donnée n'est
-- modifiée. Idempotente. À appliquer avec le code qui l'écrit (création et
-- modification d'une saisie avec un montant total).

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
            CHECK (montant_total IS NULL OR montant_total > 0);
    END IF;
END $$;

COMMENT ON COLUMN public.salary_seizures.montant_total IS
    'Montant total de la dette : la retenue est plafonnée au reste dû (total moins les retenues déjà faites), plus rien n''est retenu à zéro. Vide : la saisie court sans fin.';
