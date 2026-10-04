-- Supprimer un bulletin ne supprime plus l'échéance de prêt qu'il avait réglée,
-- ni l'acompte sur prime rapproché sur lui.
--
-- Créées en ON DELETE SET NULL (20260610200000, 20260610220000), ces deux clés
-- sont passées en ON DELETE CASCADE avec toutes les clés vers `payslips` dans
-- 20260618200000_employee_delete_cascade : supprimer un bulletin effaçait la
-- ligne d'échéancier qu'il avait réglée (`employee_loan_installments`), et
-- l'avance elle-même si elle portait son identifiant (audit du 04/10/2026).
--
-- La suppression d'un salarié reste en cascade : échéances et avances partent
-- par `employee_loans.employee_id` et `salary_advances.employee_id`. Les lignes
-- de retenue (`employee_loan_repayments`, `salary_advance_repayments`,
-- `salary_seizure_deductions`) restent en cascade : elles appartiennent au
-- bulletin, que l'application défait avant de le supprimer.
--
-- Idempotente.

ALTER TABLE public.employee_loan_installments
    DROP CONSTRAINT IF EXISTS employee_loan_installments_payslip_id_fkey;
ALTER TABLE public.employee_loan_installments
    ADD CONSTRAINT employee_loan_installments_payslip_id_fkey
    FOREIGN KEY (payslip_id) REFERENCES public.payslips(id) ON DELETE SET NULL;

ALTER TABLE public.salary_advances
    DROP CONSTRAINT IF EXISTS salary_advances_prime_reconciled_payslip_id_fkey;
ALTER TABLE public.salary_advances
    ADD CONSTRAINT salary_advances_prime_reconciled_payslip_id_fkey
    FOREIGN KEY (prime_reconciled_payslip_id) REFERENCES public.payslips(id) ON DELETE SET NULL;
