# Import de pointages en masse : une semaine par fichier

Demande d'Alexandre du 19/09/2026 : importer plusieurs feuilles de pointage à la
fois, et donner à chaque fichier sa semaine (S27, S28, S29…) pour importer tout
un mois d'un coup. « C'est juste ce qu'il y a déjà, pour chaque fichier. »

## L'existant

Le dialogue `PointageImportDialog` accepte déjà plusieurs fichiers. Il porte un
sélecteur « Semaine (optionnel) » — les semaines ISO du mois
(`monthIsoWeekOptions`), « Non précisée » par défaut — mais **un seul pour tous
les fichiers**. Quand tous les fichiers sont des documents, il appelle le job
serveur groupé `POST /timesheet-import/extract-timesheet/start-batch`, qui
extrait chaque fichier indépendamment puis fusionne par salarié et par jour
(`_merge_proposals`, le dernier fichier gagne sur un même jour) — et qui
**ignore la semaine**. Sinon il enchaîne fichier par fichier avec la même
semaine pour tous. Le parseur (`parse_with_llm_fallback`) accepte pourtant
`week_anchor_date` ; il ne la reçoit simplement pas. La persistance sait ranger
dans le mois voisin les jours d'une semaine à cheval sur deux mois.

## Conception

**Front.** Le sélecteur « Semaine (optionnel) » quitte l'en-tête et se répète
sur chaque ligne de la liste des fichiers déposés, à l'identique (mêmes options,
« Non précisée » par défaut, aucun pré-remplissage). La règle de validation ne
change pas : en « Hebdomadaire », chaque fichier doit avoir sa semaine avant de
lancer. Les deux chemins passent la semaine de chaque fichier : le job groupé
reçoit la liste alignée sur les fichiers ; le chemin fichier par fichier passe
celle du fichier en cours.

**API.** `start-batch` reçoit `week_anchor_dates` (JSON, une entrée par
fichier dans le même ordre, date ISO du lundi ou `null`). Longueur différente
du nombre de fichiers → 400. `request_json.files` mémorise
`[{filename, week_anchor_date}]`.

**Job groupé.** `run_multi_timesheet_extraction_job` passe à chaque fichier sa
`week_anchor_date` ; la progression nomme la semaine (« S28 · fichier.pdf »).
La fusion ne change pas ; quand deux fichiers portent la même semaine, un
avertissement le dit dans la proposition (aujourd'hui le second écrase le
premier en silence).

**Ce qui ne change pas.** Pas de nouvel écran, de nouveau job ni de nouvelle
table ; la revue (`AssistedFillReview`) et la persistance sont inchangées.

## Tests

- back : liste de semaines mal alignée → 400 ; chaque extraction reçoit la
  semaine de son fichier (parseur doublé) ; deux fichiers sur la même semaine
  → avertissement ; libellé de progression ;
- front : une ligne par fichier avec son sélecteur ; validation « Hebdomadaire »
  fichier par fichier ; les semaines partent alignées avec les fichiers.
