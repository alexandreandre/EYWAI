-- Préavis : trois cas, une valeur chacun ([H1], Code du travail L1234-5).
--
-- « executed » : préavis exécuté, payé avec le salaire du mois (nouvelle
--   valeur, défaut de l'écran et de l'API) ;
-- « paid » : dispense à l'initiative de l'employeur, indemnité compensatrice
--   (sens inchangé : c'est ce que le calcul et les documents lisaient déjà) ;
-- « waived » : dispense à la demande du salarié, acceptée, rien n'est dû ;
-- « not_applicable » : pas de préavis.
--
-- Aucune donnée ne change : au 11/10/2026, aucun départ n'a de jours de
-- préavis, et aucun ne porte « waived ».
--
-- À appliquer AVANT de déployer le code qui écrit « executed » : sans elle,
-- la création d'une démission ou d'un licenciement avec préavis serait refusée.
ALTER TABLE public.employee_exits
  DROP CONSTRAINT IF EXISTS employee_exits_notice_indemnity_type_check;
ALTER TABLE public.employee_exits
  ADD CONSTRAINT employee_exits_notice_indemnity_type_check CHECK (
    (notice_indemnity_type)::text = ANY (
      (ARRAY[
        'executed'::character varying,
        'paid'::character varying,
        'waived'::character varying,
        'not_applicable'::character varying
      ])::text[]
    )
  );
