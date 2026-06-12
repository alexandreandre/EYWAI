-- Téléphone personnel du salarié (fiche employé / onboarding).

ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS phone_number text;

COMMENT ON COLUMN public.employees.phone_number IS
    'Numéro de téléphone personnel du salarié (format libre, ex. +33612345678).';
