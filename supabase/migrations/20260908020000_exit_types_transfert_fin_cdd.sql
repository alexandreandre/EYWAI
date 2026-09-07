-- Types de sortie manquants + correction du dossier BARBERET (MAJI).
--
-- L'historique réel (déclarante, 08/09/2026) : CDI MAJI 23/01→28/02/2026,
-- TRANSFERT intra-groupe vers ZONE 404 sans solde de tout compte (solde CP
-- et ancienneté conservés), puis CDI ZONE 404 01/03→21/06 (STC payé sur
-- 06/2026), puis CDD MAJI 29→30/06. Le dossier enregistré disait « fin de
-- période d'essai au 31/03 » : type et date faux.
--
-- 1) Le CHECK exit_type gagne 'transfert' (mutation intra-groupe, jamais de
--    STC) et 'fin_cdd' (prérequis du chantier STC fin de CDD : indemnité de
--    précarité + ICCP).
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
        'transfert'::character varying
      ])::text[]
    )
  );

-- 2) Correction du dossier BARBERET (id identique prod/test — copie).
--    exit_notes est un JOURNAL jsonb : la correction s'y appose comme une
--    entrée d'audit, au format des entrées existantes (exit_type_change).
UPDATE employee_exits
SET exit_type = 'transfert',
    last_working_day = '2026-02-28',
    exit_notes = COALESCE(exit_notes, '{}'::jsonb) || jsonb_build_object(
      'correction_transfert_20260908', jsonb_build_object(
        'timestamp', now(),
        'previous_exit_type', 'fin_periode_essai',
        'previous_last_working_day', '2026-03-31',
        'note', 'Transfert intra-groupe vers ZONE 404 au 28/02/2026, sans STC '
                || '(solde CP et anciennete conserves) — la fiche portait a tort '
                || 'fin de periode d''essai au 31/03. Source : declarante, 08/09/2026.'
      )
    )
WHERE id = 'e58aea3e-8260-4a37-a42a-c568948fc4a4'
  AND exit_type = 'fin_periode_essai';
