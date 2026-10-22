-- Un congé de maternité, de paternité ou d'adoption s'enregistre avec son type.
-- La contrainte ne connaissait que les types de maladie et d'accident : la saisie
-- « Maternité » échouait (absence_requests_arret_type_check). Aucune ligne existante
-- n'est réécrite : on ajoute trois valeurs à la liste déjà admise.

alter table public.absence_requests
  drop constraint if exists absence_requests_arret_type_check;

alter table public.absence_requests
  add constraint absence_requests_arret_type_check
  check (
    arret_type is null
    or arret_type = any (array[
      'maladie_simple',
      'accident_travail',
      'maladie_professionnelle',
      'accident_trajet',
      'mi_temps_therapeutique',
      'ald',
      'rechute_at',
      'arret_exceptionnel',
      'maternite',
      'paternite',
      'adoption'
    ]::text[])
  );
