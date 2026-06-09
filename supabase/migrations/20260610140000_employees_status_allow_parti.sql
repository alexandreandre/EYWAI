-- Autoriser le statut 'parti' (archivage d'une procédure de sortie).
-- Le code marque l'employé 'parti' à l'archivage de la sortie
-- (employee_exits/application/commands.py), mais la contrainte
-- précédente (20260605220000) ne l'autorisait pas → échec d'archivage.

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
            'parti',
            'inactif'
        )
    );
