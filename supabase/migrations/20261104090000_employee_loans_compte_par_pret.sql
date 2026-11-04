-- Un compte par prêt dans l'OD de paie (04/11/2026).
-- La comptable du groupe ouvre un compte de tiers par prêt (« on crée un 425 à
-- chaque fois qu'un nouveau salarié nous demande un prêt ») : le versement du
-- prêt est passé sur ce compte, et chaque remboursement retenu sur le bulletin
-- doit le solder. Vide : le prêt suit le compte « prêt » de la société.
-- Colonne facultative, sans valeur par défaut : rien ne change pour les prêts
-- existants.

ALTER TABLE public.employee_loans
    ADD COLUMN IF NOT EXISTS accounting_account text;

COMMENT ON COLUMN public.employee_loans.accounting_account IS
    'Compte comptable propre au prêt (ex. 42511000), crédité de chaque remboursement dans l''OD de paie ; vide : compte « prêt » de la société.';
