# Maintien de salaire : barème de la métallurgie (IDCC 3248)

Date : 03/11/2026. Branche : feat/dsn-octobre. Audit du 02/11, n° 12 (Cartol et LEWIS seraient payés selon la loi, au lieu de 100 % dès le premier jour). Même mécanique que le barème de la plasturgie (conception du 24/10), avec quatre différences écrites dans le texte.

## Le texte

Convention du 7 février 2022 (KALICONT000046993250), lue sur Légifrance le 02/11 et le 03/11 (`data/_sources/maintien/legifrance-metallurgie-3248-art-91-1-lu-2026-11-02.txt`) :

- **art. 91.1.1, conditions** : un an d'ancienneté ; « en cas d'absence pour accident du travail ou maladie professionnelle survenu ou contractée dans l'entreprise », trois mois. L'ancienneté s'apprécie au premier jour de l'absence. Si elle est acquise pendant l'absence, l'article s'applique « sans déduction de la période n'ouvrant pas droit à indemnisation ». En cas de changement de tranche pendant l'absence, le salarié « bénéficie immédiatement du crédit d'indemnisation afférent ».
- **art. 91.1.2.1, groupes A à E (non-cadres)**, « à compter du 1er jour entièrement non-travaillé » : 100 % pendant 90 jours (1 à 5 ans), 120 jours (5 à 10 ans), 150 jours (10 à 15 ans), 180 jours (plus de 15 ans). Accident du travail et maladie professionnelle : « à partir du 1er jour d'absence ».
- **art. 91.1.2.2, groupes F à I (cadres)** : les mêmes durées à 100 %, puis autant à 50 %.
- **art. 91.1.3, versement** :
  - « la rémunération brute que le salarié aurait perçue s'il avait continué à travailler » ;
  - sous déduction des IJSS, « retenues pour leur montant avant précompte » de la CSG et de la CRDS ;
  - plafond : le salarié ne peut percevoir « une indemnisation plus importante que la rémunération nette qu'il aurait perçue » ;
  - durée totale sur l'année civile, plusieurs absences comprises ;
  - arrêt à cheval sur deux années : le changement d'année n'allonge pas l'arrêt. Si le salarié a déjà été arrêté pendant l'année N, le crédit de l'arrêt est réévalué au 1er janvier N + 1 : crédit total moins ce que l'arrêt a déjà reçu. Un nouvel arrêt après lui prend le crédit total moins ce qui a été indemnisé depuis le 1er janvier.

## Ce que Martine fait

Le barème « Métallurgie (IDCC 3248) » s'ajoute au choix de la carte « Maintien de salaire ». Il passe par le même rejeu des arrêts (`paliers_convention.plan_conventionnel`) et la même valorisation des jours (`BaseDesJours`) que la plasturgie. Quatre réglages du barème, éteints pour la plasturgie :

1. **Pas de carence**, pour personne.
2. **Conditions d'ancienneté par nature** : maladie et accident de trajet, 12 mois ; accident du travail et maladie professionnelle, 3 mois. Le trajet n'est pas un accident du travail (L1226-7). Que l'accident soit survenu dans l'entreprise, Martine ne le sait pas : elle le suppose.
3. **Ancienneté lue chaque jour** : un jour d'arrêt n'est indemnisé que si l'ancienneté de ce jour ouvre le droit. Les jours d'avant ne consomment rien. La tranche, et donc la limite, est celle du jour.
4. **Paliers consommés sur l'année** : le rang d'un jour, qui fixe son taux (100 % puis 50 % pour un cadre), est le plus grand de deux compteurs, les jours déjà indemnisés pour cet arrêt et ceux déjà indemnisés dans l'année civile. Un jour est indemnisé si ce rang reste sous la limite. Cela donne les trois cas de l'arrêt à cheval :
   - le rang de l'arrêt continue après le 1er janvier ;
   - un arrêt bloqué par le compteur de l'année N reprend au 1er janvier, jusqu'à la limite moins ses propres jours ;
   - un arrêt suivant part du compteur de l'année N + 1.

   Pour la plasturgie, rien ne change : les paliers repartent à chaque arrêt, avec la même double limite.

**Le versé** : garanti brut (taux × valeur des jours), moins les IJSS brutes des jours maintenus (même réglage qu'aujourd'hui). Puis le **plafond au net** :

`versé ≤ valeur des jours maintenus − IJ × (1 − s) / (1 − t)`

Ici, `s` est la CSG et la CRDS des IJ (6,7 %), et `t` la part salariale d'un euro de salaire, mesurée par le moteur de cotisations (`garantie_nette.taux_salarial_marginal`, comme pour la plasturgie). Le plafond ne fait que baisser le versé : `min`. À 100 %, il mord dès que `t` dépasse `s`. À 50 % (un cadre), il ne mord presque jamais. Sans IJ déduites, il ne mord pas : verser le garanti en entier reste un choix de la société. Si la mesure échoue, le maintien n'est pas plafonné, ce qui est plus favorable au salarié, et une alerte le dit.

Chaque mois, Martine compare avec le maintien légal (sur le brut, inchangé) et verse le plus favorable.

## Ce qu'on montre

- Carte « Maintien de salaire » : le barème, ses tranches et ses règles (`description_lisible`), sans nouveau champ.
- Détail du maintien : une phrase sous les paliers quand le plafond mord, par exemple « Plafond au net : le maintien ne peut pas dépasser le net que le salarié aurait perçu. Les IJSS (X) sont comptées nettes de CSG et CRDS (6,7 %), puis ramenées au brut avec 21,84 % de cotisations salariales. Maintien réduit de Y. »
- Carence : « Métallurgie : pas de carence. » Droit fermé : « Métallurgie : 3 mois d'ancienneté requis pour un accident du travail ou une maladie professionnelle (N mois au début de l'arrêt). »

## Base

La contrainte de `company_maintenance_settings.bareme_convention` accepte `metallurgie_3248` (migration). Poser le barème chez Cartol et LEWIS est une écriture en base, avec un script simulé puis « lance ». Il faut d'abord vérifier, au bac à sable, qu'une ligne de réglages créée pour elles ne change rien d'autre.

## Plasturgie, en même temps

- **n° 11, Mont Blanc** : la société est en IDCC 0292, sans barème. Poser `plasturgie_0292`, avec un script simulé puis « lance ». Aucun code.
- **n° 13, accident du travail** : le barème de la plasturgie n'a déjà aucune condition d'ancienneté en accident du travail (`tranche_pour`). La condition de 3 mois vient des réglages manuels (`min_seniority_months_at_mp`), donc des sociétés sans barème : le n° 11 la ferme pour Mont Blanc. Un test le fixe.

## Fait le 03/11

Code et tests écrits (TDD), suite payroll au vert (2447 tests), plasturgie inchangée :
- barème `metallurgie_3248` dans `baremes_maintien.py` (deux champs nouveaux au défaut plasturgie : `anciennete_requise_at_mp_mois`, `trajet_requiert_anciennete`, `anciennete_et_paliers_par_annee` ; garantie `plafond_net`) ;
- rejeu par année dans `paliers_convention.py` (ancienneté lue chaque jour, rang = max des deux compteurs) ; les trois cas de l'arrêt à cheval testés ;
- plafond au net dans `maintien_salaire_service.py` (`_plafonner_au_net`, alerte si la mesure échoue), agrégé sur plusieurs arrêts ;
- affichage : carence « pas de carence », motif par nature, phrase du plafond (`paliers_affiches.py`, `paliersAffichage.ts`) ;
- schémas API, choix à l'écran (`baremeConvention.ts`), types (`absences.ts`, `maintenanceSettings.ts`), migration `20261103120000`.

**n° 13 fermé en code** : la plasturgie n'a aucune condition d'ancienneté en accident du travail (`tranche_pour`, testé). La condition de 3 mois que voyait A.D. venait des réglages manuels d'une société sans barème — donc de Mont Blanc, fermé par le n° 11 (poser le barème).

## Hors champ

- La prévoyance, qui entre dans le plafond (« après application des garanties […] d'un régime complémentaire de prévoyance ») : elle attend les décomptes, comme pour la plasturgie.
- Le salarié classé non-cadre en 2024 qui était cadre sous l'ancienne convention, et garde la durée des cadres (Code du travail numérique, art. 68) : rien dans la fiche ne le dit.
- La « contre-visite » et le délai de 48 heures.

## Tests (TDD)

- Barème : tranches, conditions par nature, libellés, sources.
- Rejeu :
  - pas de carence ;
  - accident du travail à 3 mois : droit ouvert ; à 2 mois : fermé ;
  - trajet à 11 mois : fermé ;
  - ancienneté acquise pendant l'arrêt : indemnisé à partir de l'anniversaire, crédit entier ;
  - changement de tranche pendant l'arrêt : 120 jours dès le 5e anniversaire ;
  - deux arrêts dans l'année : le second continue le rang (un cadre passe à 50 % au bon jour) ;
  - les trois cas de l'arrêt à cheval.
- Plasturgie : inchangée (les tests existants passent sans être modifiés).
- Plafond au net : `versé × (1 − t) + IJ × (1 − s) = valeur × (1 − t)` quand il mord ; sans IJ déduites, pas de plafond ; mesure en échec : alerte, pas de plafond.
- Filet avant/après sur les quatre sociétés : aucun écart (aucune n'a ce barème).
