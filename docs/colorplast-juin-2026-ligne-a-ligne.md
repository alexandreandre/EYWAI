# Colorplast, juin 2026 : EYWAI contre Quadra, ligne à ligne

Rejeu du 16/09/2026 (`backend/scripts/colorplast_rejeu_test.py`), comparé au PDF
du cabinet `data/colorplast/bulletins/2026-06/`. Sept salariés.
Convention : **écart = EYWAI − Quadra**.

Juin apporte deux choses : la **revalorisation du SMIC** (12,02 → 12,31 au 1er
juin) et l'augmentation de Demory et Fuckar, qui passent à 1 867,06 €.

C'est le premier mois qui n'a demandé **aucune correction du moteur**. Du
premier passage, les sept bruts, nets à payer, prélèvements à la source, nets
sociaux, nets des heures sup exonérées, compteurs d'heures, plafonds,
contributions patronales et déductions forfaitaires tombent au centime.

## État

| | Brut | Net à payer | Impôt | Net social | Compteurs | Plafond | Coût patronal | Déduction HS | Allègement |
|---|---|---|---|---|---|---|---|---|---|
| Bugny | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cotte | ✓ | ✓ | ✓ | ✓ | *écart assumé* | ✓ | ✓ | ✓ | **+38,33** |
| Demory | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **+43,66** |
| Espinosa | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **+35,51** |
| Fuckar | ✓ | ✓ | ✓ | ✓ | *écart assumé* | ✓ | ✓ | ✓ | −1,90 |
| Girerd | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **+18,32** |
| Gautheron | *en attente* | | | | | | | | |

## Comment les cibles ont été établies

Le relevé du PDF se contrôle par deux chemins indépendants, et les deux tombent
au centime pour les sept.

**Contrôle interne du bulletin** : net à payer avant impôt − prélèvement à la
source = net versé au salarié.

**Contrôle des heures** : la variation du compteur cumulé doit valoir le mois
plein (169 h sur un contrat de 39 h) plus les heures sup, moins l'absence.

| | Cumul juin − mai | Attendu |
|---|---|---|
| Bugny | 190,00 | 169 + 14 + 7 |
| Espinosa | 192,00 | 169 + 16 + 7 |
| Fuckar | 176,00 | 169 + 4 + 3 |
| Cotte, Girerd | 169,00 | mois plein |
| Demory | 160,50 | 169 − **8,50** |
| Gautheron | 161,20 | 169 − **7,80** |

## Ce qui a été corrigé dans les données

### Le SMIC imprimé change en cours d'année

12,02 € jusqu'en mai, **12,31 € au 1er juin**. Le moteur savait déjà le faire —
le barème porte les deux valeurs datées et retient la plus récente qui précède
la fin de la période. Seule la constante du rejeu était figée ; elle est
désormais mensuelle.

À ne pas confondre avec le **SMIC de référence de l'allègement**, gelé à 12,02 €
pour toute l'année. C'est tout le sujet de la section suivante.

### Deux absences posées à la part de base au lieu du total

Demory est absent le 08/06 et Gautheron le 10/06. Le cabinet imprime chaque
absence sur **deux lignes** — la retenue de base et la réduction des heures sup
structurelles — alors que le jeu de test attend le total, que le moteur
répartit ensuite 35/39.

| Salarié | Base déduite | HS structurelles | Total à poser |
|---|---|---|---|
| Demory, 08/06 | 7,63 | 0,87 | **8,50** |
| Gautheron, 10/06 | 7,00 | 0,80 | **7,80** |

C'est la troisième fois que cette confusion se produit (avril, mai, juin). La
règle est simple et vaut d'être retenue : **le nombre posé dans `abs` est
toujours le total de la journée**, jamais la quantité imprimée par le cabinet.

### La base de test portait les heures sup de juillet sur juin

Bugny y avait 19,00 h à 25 % et 6,50 à 50 %, saisies le 14/09 et libellées
« corrigées au bulletin ». Ce sont exactement les heures de **juillet** : son
bulletin de juin en paie 14,00 et 7,00. Le nettoyage du rejeu les efface avant
de reposer celles du bulletin.

Quatrième fois de la série que la base de test contient déjà — mal — ce qu'on
s'apprêtait à écrire.

## Le seul vrai écart : l'allègement, 18 à 44 €

Jusqu'ici les écarts d'allègement se comptaient en centimes ou en euros. En
juin ils atteignent 44 €, sur cinq salariés sur sept. La cause est identifiée,
elle n'est pas tranchée.

### La question

La réduction générale se calcule sur un **SMIC de référence**. Notre moteur le
garde **gelé à 12,02 €** pour toute l'année (LFSS 2025), valeur inscrite dans
`payroll_config.reduction_generale.smic_reference_horaire`. Ce gel a reproduit
janvier à mai exactement — mais ces mois ne prouvent rien, puisque le SMIC y
valait 12,02 de toute façon. **Juin est le premier mois qui pouvait départager
le gel de la revalorisation.**

### Ce que dit le bulletin du cabinet

En remontant sa formule à l'envers sur le **cumul** de janvier à juin — le
coefficient RGDU, puis le SMIC de référence qu'il implique :

| | Cumul reproduit par | Écart résiduel |
|---|---|---|
| **Bugny** | SMIC **gelé** à 12,02 | 0,43 € |
| **Girerd** | SMIC **revalorisé** à 12,31 sur les heures de juin | 0,25 € |
| **Espinosa** | revalorisé | 0,74 € |
| Cotte, Fuckar | revalorisé | ≈ 4,50 € |
| Demory | ni l'un ni l'autre | — |

Deux salariés du même bulletin, produits par la même paie, le même jour, avec
deux références différentes. Les bruts cumulés utilisés pour ce calcul sont
ceux **imprimés par le cabinet lui-même** dans l'encadré « Bruts » — vérifiés
identiques à la somme de nos six mois, donc l'écart ne vient pas de là.

### Pourquoi nous ne changeons rien

Suivre la revalorisation sur la foi d'une observation qui se contredit d'un
bulletin à l'autre reviendrait à graver un allègement possiblement excessif
dans les sept sociétés — et un allègement de trop est un redressement en cas de
contrôle. Le gel reste appliqué, l'écart est inscrit, et la question est posée.

C'est la **question 1** sous une forme enfin chiffrée : sur quelle base le
cabinet calcule-t-il réellement ?

## Ce que nous ne reproduisons pas, et pourquoi

### Les traînes de mars et d'avril

Cotte porte toujours les 23,40 h de son congé pour événement familial de mars
(2,40 h au compteur d'heures sup), et Fuckar les −3,05 h structurelles
rattachées à la période précédant son embauche d'avril. Sans conséquence
financière.

### Deux journées d'absence, deux traitements

Demory et Gautheron s'absentent chacun une journée. La feuille d'heures du
cabinet porte **8,50 h pour les deux**. Il en déduit 8,50 à l'un et 7,80 à
l'autre. Nous posons ce qu'il a payé.

## Ce qui reste ouvert

### Gautheron : ses cumuls dépendent toujours d'avril

Son brut de juin tombe au centime, mais ses compteurs héritent de son arrêt
d'avril, toujours suspendu à la question du maintien.

Sur ce point, **le classeur de juin du cabinet apporte un élément neuf et
décisif**. Son onglet « Règles de maintien » porte leurs propres barèmes :

> Ouvriers et collaborateurs, de 1 à 4 ans d'ancienneté : **100 % pendant 45
> jours, puis 75 % pendant 60 jours** — 105 jours de maintien au total. À partir
> de 5 ans : 100 % pendant 60 jours, puis 75 % pendant 75.

Marion a plus de quatre ans d'ancienneté. Selon **leur propre table**, elle
avait droit à 100 % de son salaire pendant au moins 45 jours. Le cabinet lui a
versé trois jours, soit 310,78 €.

Cela ne change rien à notre moteur, qui refusait déjà de descendre sous le
plancher légal de 90 % — mais cela déplace la question. Elle n'est plus « qui
verse le complément ? » mais « pourquoi le barème conventionnel n'a-t-il pas
été appliqué ? ».

### Le détail des heures sup ne reproduit pas ce qui a été payé

Le classeur `detail-heures-sup-06-2026-colorplast.xlsx` calcule, semaine par
semaine, les heures au-delà de 39 h et leur majoration. Ses totaux pour Bugny :
**10 h à 25 % et 3,5 h à 50 %**. Son bulletin en paie **14 et 7**. Pour
Espinosa, 12 et 3 contre 16 et 7 payées.

Ce ne sont pas non plus les heures de juillet (19 et 6,5 pour Bugny). La
fenêtre des variables de juin n'est donc pas confirmée par cette source ; celle
retenue, 25/05 → 21/06, est la suite logique de mai en semaines entières.

Même famille que les 48,5 h non payées de Michel entre janvier et mars — sauf
qu'ici le cabinet paie **plus** que ce que son propre décompte justifie.
