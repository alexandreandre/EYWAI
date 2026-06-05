-- Autoriser le statut en_onboarding (embauche via recrutement)

ALTER TABLE public.employees
    DROP CONSTRAINT IF EXISTS employees_employment_status_check;

ALTER TABLE public.employees
    ADD CONSTRAINT employees_employment_status_check
    CHECK (
        employment_status IS NULL
        OR employment_status IN (
            'actif',
            'active',
            'en_sortie',
            'en_onboarding',
            'inactif'
        )
    );
