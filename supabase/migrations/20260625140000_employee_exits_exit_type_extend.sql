-- Étend les types de sortie autorisés (aligné sur employee_exits/domain/enums.py).
-- Requis pour l'import DSN (motifs 037/038 → fin_periode_essai, départ retraite).

ALTER TABLE public.employee_exits
    DROP CONSTRAINT IF EXISTS employee_exits_exit_type_check;

ALTER TABLE public.employee_exits
    ADD CONSTRAINT employee_exits_exit_type_check
    CHECK (exit_type IN (
        'demission',
        'rupture_conventionnelle',
        'licenciement',
        'depart_retraite',
        'fin_periode_essai'
    ));
