# Compensation des heures entre semaines — conception

Date : 21 septembre 2026. Décision d'Alexandre : offrir une option société qui
fait la paie des heures comme Gaëlle la fait chez Colorplast, en connaissance
de cause — la règle légale reste hebdomadaire, l'option est un choix explicite
de l'entreprise, nommé pour ce qu'il est.

## La règle de Gaëlle, lue dans son classeur

`data/colorplast/variables/2026-06/detail-heures-sup-06-2026-colorplast.xlsx`,
onglet « DETAIL HEURES SUP » : « les 8 premières heures = 25 %, les suivantes
= 50 % ».

- **Par jour** : l'écart entre les heures faites et l'horaire du jour, positif
  ou négatif (`B7:G7`).
- **Par semaine** : `TOTAL = SUM(écarts)` ; `H sup mens. = 4` (les heures
  structurelles 35 → 39, déjà payées chaque mois) ; `J = TOTAL + 4` ;
  `Majo 25 % = IF(J < 8, J, 8) − 4` — soit **min(TOTAL, 4)**, négatif compris ;
  `Majo 50 % = TOTAL − Majo 25 %` — soit **max(TOTAL − 4, 0)**.
- **Par mois de paie** (sa fenêtre de variables) : la somme des semaines,
  **semaines négatives comprises**, pour chaque taux.

Vérifié sur juin 2026 (le classeur prolongé à S25 redonne les bulletins) :
Bugny semaines +2, +4, +7,5, +7,5 → 14 h à 25 % et 7 h à 50 % ; Fuckar −5, +7,
+1, +4 → 4 h à 25 % et 3 h à 50 %. Une semaine négative ne retire jamais de
salaire : elle mange des heures sup.

Généralisation à un autre contrat : les heures à 25 % sont celles entre le
contrat et 43 h, soit `seuil25 = 43 − durée hebdo` (4 h à 39 h, 8 h à 35 h) ;
`majo25 = min(TOTAL, seuil25)`, `majo50 = max(TOTAL − seuil25, 0)`.

## Ce que l'option fait

`companies.settings.compensation_heures_entre_semaines = true` (défaut : faux,
rien ne change pour les autres sociétés).

Sur la **fenêtre des variables** du bulletin (celle du moteur, 22/06 → 26/07
pour juillet Colorplast), après l'analyse hebdomadaire habituelle :

1. **Bilan par semaine** : écart journalier = heures faites − heures prévues,
   sur les jours de travail prévus qui ont un pointage. Comme dans l'analyseur,
   un jour prévu sans pointage est neutre, un mois sans aucun pointage aussi ;
   un jour non prévu compte pour ses heures faites (écart = faites).
2. **Majorations de la semaine** : `majo25 = min(TOTAL, seuil25)`,
   `majo50 = max(TOTAL − seuil25, 0)`.
3. **Compensation** : `net25 = Σ majo25`, `net50 = Σ majo50`. Si `net25 < 0`,
   le manque mange d'abord `net50` ; ce qui reste de négatif n'est **ni retenu
   ni reporté** (le compteur de récupération multi-mois de Gaëlle est hors
   périmètre, voir plus bas) — il est seulement dit.
4. **Application** : dans le calendrier de paie, les événements `travail_hs25`,
   `travail_hs50` et `absence_injustifiee_*` datés dans la fenêtre sont
   retirés, remplacés par un `travail_hs25` de `net25` heures et un
   `travail_hs50` de `net50` heures datés du dernier jour de la fenêtre. Les
   autres événements (congés, fériés, arrêts, régularisations antérieures)
   ne bougent pas.

Conséquences voulues : aucune retenue pour semaine courte ; les heures sup
d'une semaine haute sont réduites par les semaines basses ; le compteur
d'heures et la base de l'allègement suivent (rien de retenu = tout rémunéré).

## Traçabilité

- Le bulletin porte une mention, sous la ligne des heures sup, du même
  mécanisme que l'arbitrage des congés : « Heures compensées entre semaines
  (option société) : S26 +0,0 · S27 +1,5 · S28 +0,0 · S29 +0,0 · S30 −1,0 →
  0,5 h à 25 %, 0 h à 50 % ; solde non payé 0 h. »
- `payslip_data.compensation_semaines` garde le détail (semaines, écarts,
  majorations, nets, solde négatif) pour l'audit et le rapprochement.
- Les heures sup **saisies à la main** (variables mensuelles « Heures
  supplémentaires conjoncturelles ») priment sur le calendrier dans le moteur,
  option ou pas : quand elles diffèrent des nets compensés, le résumé les porte
  (`heures_saisies`) et la mention le dit — « Heures supplémentaires saisies à
  la main retenues sur le bulletin : 8 h à 25 %, 0 h à 50 %. » Le bulletin
  reste vrai ; l'option ne retire donc que les retenues d'absence, et laisse
  la saisie faire les heures sup.
- Une régularisation d'un mois antérieur (`is_regularisation_anterieure`)
  datée dans la fenêtre n'est jamais remplacée : elle appartient au bulletin,
  pas à une semaine.
- La revue pré-paie et la modale de lancement rappellent que l'option est
  active pour la société.

## Où ça vit

- Domaine pur : `app/modules/payroll/application/compensation_semaines.py`
  (bilan par semaine, majorations, compensation, application au calendrier).
- Générateur (`payslip_generator`) : lit l'option dans `company_data.settings`,
  applique après résolution de la fenêtre aux événements de M et M-1 avant de
  les écrire, dépose le résumé dans `saisies/MM.json`.
- Moteur (`payslip_run_heures` → `engine/bulletin`) : lit le résumé, écrit la
  mention et `payslip_data.compensation_semaines`.
- Réglage : `CompanySettingsUpdate.compensation_heures_entre_semaines`
  (PATCH `/api/company/settings`), carte dédiée dans l'onglet Paie de la
  société, sur le modèle des cartes existantes, avec le texte d'avertissement.

## Hors périmètre, dit explicitement

- Le **compteur de récupération** entre mois (« ne pas payer les heures sup
  quand compteur récup en négatif », report d'un solde négatif ou d'heures non
  payées au mois suivant) : une deuxième étape si Alexandre la veut.
- Les journées « en récup » et la journée de solidarité que Gaëlle saisit à la
  main en négatif dans son classeur : elles restent des saisies.
- La règle légale ne change pas pour les sociétés sans l'option ; la
  tolérance de retenue séparée n'a pas lieu d'être pour une société qui
  compense.

## Tests

Purs, sur des semaines et des jours :
- majorations : 7,5 → (4 ; 3,5) ; 2 → (2 ; 0) ; −5 → (−5 ; 0) ; à 35 h,
  10 → (8 ; 2) ;
- compensation juin 2026 : Bugny [+2, +4, +7,5, +7,5] → (14 ; 7) ; Fuckar
  [−5, +7, +1, +4] → (4 ; 3) ; Espinosa [+4, +4, +8, +8] → (16 ; 7)* ;
  un net25 négatif mange le net50 : [−6, +10] → (0 ; 4, solde 0) ; [−8, +2] →
  (0 ; 0, solde −6) ;
- écarts journaliers : Fuckar S28 (−1,5, −4, +1, +2) → −2,5 ; un jour sans
  pointage neutre ; un mois sans pointage neutre ; un jour non prévu compte ;
- application au calendrier : les HS et absences de la fenêtre disparaissent,
  les nets apparaissent au dernier jour de la fenêtre, un congé de la fenêtre
  et une HS hors fenêtre restent ; option désactivée → calendrier identique ;
- réglage : le PATCH accepte le booléen et le rend au GET.

\* semaines d'Espinosa reconstruites depuis le total 16/7 du classeur ; la
recette qui compte est Bugny et Fuckar, dont les semaines sont écrites.
