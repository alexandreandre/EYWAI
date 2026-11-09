-- Le congé supplémentaire de naissance (L1225-46-2, en vigueur depuis le 01/07/2026)
-- s'enregistre avec son type d'arrêt. Sans cette valeur, la contrainte refuse la
-- saisie (absence_requests_arret_type_check). Aucune ligne existante n'est réécrite :
-- on ajoute une valeur à la liste déjà admise.

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
      'adoption',
      'conge_supplementaire_naissance'
    ]::text[])
  );
