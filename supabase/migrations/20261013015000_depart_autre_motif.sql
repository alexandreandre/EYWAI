-- Type de départ « Autre motif » : un motif de rupture DSN sans équivalent
-- (066, 085, 098, 099…) ne retombe plus sur « démission » à l'import. Le code
-- d'origine reste dans exit_reason (« Import DSN (0xx) »), que la DSN réémet.
-- Non appliquée : à passer sur la base de test d'abord.
ALTER TABLE public.employee_exits
  DROP CONSTRAINT IF EXISTS employee_exits_exit_type_check;
ALTER TABLE public.employee_exits
  ADD CONSTRAINT employee_exits_exit_type_check CHECK (
    (exit_type)::text = ANY (
      (ARRAY[
        'demission'::character varying,
        'rupture_conventionnelle'::character varying,
        'licenciement'::character varying,
        'depart_retraite'::character varying,
        'fin_periode_essai'::character varying,
        'fin_cdd'::character varying,
        'transfert'::character varying,
        'autre_motif'::character varying
      ])::text[]
    )
  );
