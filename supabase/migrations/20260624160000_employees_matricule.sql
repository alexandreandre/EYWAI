-- Matricule interne salarié (DSN S21.G00.30.019 / S21.G00.40.009).

ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS matricule text;

COMMENT ON COLUMN public.employees.matricule IS
    'Matricule interne entreprise. Source DSN : S21.G00.30.019 ou S21.G00.40.009.';
