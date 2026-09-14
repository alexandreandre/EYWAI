# Fenêtre des variables et bilan hebdomadaire des absences

Retours de Gaëlle (Colorplast) du 14/09/2026, bulletins de juillet comparés
ligne à ligne à Quadra. Les bases, taux et la valorisation 35/39 d'une heure
d'absence sont identiques. Tout l'écart de brut vient de deux règles.

| Salarié | Quadra | EYWAI | Cause |
|---|---|---|---|
| Espinosa | 3 191,76 | 3 159,63 | absence du 31/07 comptée dans juillet (fenêtre) |
| Fuckar | 1 906,45 | 1 830,74 | 6 h d'absence en trop (bilan par semaine) + 29/07 (fenêtre) |
| Marion | 2 089,06 | 2 072,17 | 31/07 (fenêtre) + 15 min le 17/07 (donnée de feuille, hors sujet) |

Les heures de juillet des deux côtés viennent des mêmes feuilles de pointage
hebdomadaires, importées par Gaëlle le 01/09.

## Règle A — ce qui suit la fenêtre des variables

**Aujourd'hui.** La gestionnaire arrête ses variables à une date qu'elle
choisit (juillet : 22/06 au 26/07). Le moteur reçoit cette fenêtre et
l'imprime, mais seules les heures sup la suivent
(`calcul_brut.TYPES_RATTACHES_AUX_VARIABLES`). Les absences suivent le mois
civil : la semaine du 27 au 31 juillet est retenue sur juillet, puis reprise
sur août.

**Demain.** Les absences non rémunérées suivent la fenêtre, comme les heures
sup : `absence_injustifiee_base`, `absence_injustifiee_hs25`,
`absence_non_remuneree`. Congés payés, fériés, arrêts maladie et maintien
restent au mois civil : c'est le choix existant, cohérent avec les IJSS et la
DSN, et Gaëlle confirmera demain qu'un congé posé le 29/07 va bien sur juillet.

**Invariants qui rendent la règle sûre.**
- Une fenêtre est faite de semaines ISO entières et commence le lendemain de
  la fin de la précédente (`shared.domain.periode_variables.resoudre_fenetre`).
  Chaque jour appartient à une seule fenêtre : plus de double comptage.
- MAJI et Zone 404 ont une fenêtre égale au mois civil : rien ne bouge chez eux.
- Les heures rémunérées du mois (`heures_remunerees_mois_contrat`, base du
  compteur « cumul heures ») se calculent sur les événements retenus par la
  fenêtre, plus sur le calendrier étendu entier. Aujourd'hui elles retirent les
  absences du 22/06 au 31/07 d'un coup.

**Transition.** Le premier mois regénéré avec la règle reprend les absences
entre le début de sa fenêtre et la fin du mois civil précédent, que ce mois a
déjà pu retenir. Sur Colorplast, aucune absence entre le 22 et le 30 juin :
pas de correction à faire. À vérifier avant toute autre société.

## Règle B — bilan par semaine

**Aujourd'hui.** L'analyseur (`payroll.application.analyzer`) regroupe déjà
par semaine ISO. Les heures sup sont bien un cumul de semaine au-delà du
contrat. Les absences sont retenues jour par jour : une heure manquée est
retenue le jour même, sauf si les heures déjà faites plus tôt dans la semaine
atteignent le contrat. Les heures faites plus tard ne compensent rien. Une
semaine peut porter une absence et des heures sup.

**Demain.** Par semaine ISO, sur les jours de travail prévus qui ont un
pointage : `bilan = heures faites − heures prévues`. Les heures faites un jour
non prévu (repos, demi-journée de congé) n'entrent pas dans ce bilan : elles
comptent pour les heures sup comme aujourd'hui, sans effacer une absence. Si
le bilan est négatif, c'est de l'absence ; s'il est positif, ce sont les
heures sup d'aujourd'hui, inchangées. Jamais les deux dans la même semaine.

L'absence de la semaine se pose sur les jours manqués, dans l'ordre : le
surplus compense d'abord les premiers jours manqués, le reste porte sur les
derniers. Fuckar, semaine du 6 juillet (−1,5 mardi, −4 mercredi, +1 jeudi,
+2 vendredi) donne une seule ligne « Absence du 08/07 : 2,5 h ». Le typage
base / hs25 par position dans la semaine est conservé (il n'a plus d'effet sur
un contrat de plus de 35 h, la répartition 35/39 s'applique après).

**Conservé tel quel** : mois sans pointage (aucune absence), jour sans
pointage (neutre), repli planning (neutre), demi-journée de congé, durée de
semaine modulée, absences venant du planning (congés, absence non rémunérée
posée), heures assimilées pour le seuil d'heures sup.

## Attendus chiffrés

| Cas | Semaine | Prévu / fait | Attendu |
|---|---|---|---|
| Fuckar | 6–10/07 | 39 / 36,5 | absence 2,5 h le 08/07 |
| Fuckar | 13–17/07 | 30,5 / 23,5 (férié le 14) | absence 7 h le 15/07 |
| Fuckar | 20–24/07 | 39 / 30,5 | absence 8,5 h le 20/07 |
| Fuckar | 27–31/07 | 39 / 41 | 2 h HS, aucune absence ; hors fenêtre de juillet |
| Espinosa | 27–31/07 | 39 / 37 | absence 2 h, hors fenêtre de juillet |
| Marion | 13–17/07 | 22 / 21,75 | absence 0,25 h le 17/07 (donnée, attendu tel quel) |

Bulletins de juillet regénérés sur le test, fenêtre 22/06–26/07 :
Fuckar 1 906,45 et Espinosa 3 191,76 au centime ; Marion 2 085,64 (l'écart
restant de 3,42 est le 17/07). Bugny, Cotte, Girerd, Demory inchangés.

## Non-régression

- Suite unitaire backend complète.
- Rejeu MAJI et Zone 404 de janvier à juin, comparé au relevé du 11/09
  (81 bulletins) : tout écart nouveau est expliqué avant déploiement.
- Août de Colorplast, regénéré après, doit porter la semaine du 27 au 31
  juillet une seule fois.

## Hors périmètre, à traiter ensuite

- Reconstruction de la chaîne des cumuls (Girerd, net imposable, cumul heures).
- Compteurs CP N-1 (Bugny, Marion).
- Déclaration DSN d'une absence datée du mois précédent portée par la
  fenêtre : vérifier que le module DSN lit bien la date réelle de l'événement.
- Congés et arrêts dans la fenêtre : question à Gaëlle le 15/09.
