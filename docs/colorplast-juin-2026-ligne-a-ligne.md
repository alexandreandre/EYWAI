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

### La règle est tranchée : le gel, par décret

Vérifié le 16/09/2026. Le **décret n° 2026-509 du 12 juin 2026** (JO du 14
juin, en vigueur le 15), annoncé par le BOSS le 5 juin, remplace dans les
articles D. 241-7 et suivants la référence au « SMIC en vigueur » par « le
salaire minimum applicable au 1er janvier 2026 » : la réduction générale de
toute l'année 2026 se calcule sur **12,02 €**, pas sur les 12,31 € du 1er juin.
Seule tolérance : les contrats qui prennent fin entre le 1er et le 30 juin
2026, dont aucun ici.

Notre moteur applique donc la règle, et Bugny le confirme chez le cabinet
aussi (0,43 € près). Les quatre autres allègements du cabinet dépassent les
nôtres de 18 à 44 €. Ce que le SMIC revalorisé explique, d'après le tableau
ci-dessus : exactement pour Girerd et Espinosa, à 4,50 € près pour Cotte, pas
du tout pour Demory. Le rejeu de juillet montre l'écart s'étendre à tous,
Bugny compris (−14 à −42 €). La direction et l'ordre de grandeur désignent le
SMIC de juin, la démonstration n'est faite que pour deux bulletins sur quatre.
Un allègement de trop se rembourse en cas de contrôle. Les écarts restent
inscrits tels quels dans le rejeu, et la question 7 devient : sur quel SMIC
juin et juillet sont-ils calculés, et seront-ils régularisés ?

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

### Le détail des heures sup du cabinet s'arrête à la semaine 24

Le classeur `detail-heures-sup-06-2026-colorplast.xlsx` donne 10 h à 25 % et
3,5 h à 50 % pour Bugny quand son bulletin en paie 14 et 7. Ce n'est pas une
contradiction : ses colonnes S25 sont vides. Prolongé à la semaine 25 par sa
propre méthode, il retombe exactement sur les trois bulletins — voir la section
suivante.

## Juin rejoué depuis les feuilles de pointage

De février à juillet, le rejeu prend la quantité d'heures sup sur le bulletin du
cabinet, en saisie mensuelle. Seul janvier fait tourner la chaîne complète,
feuilles de pointage → calendrier réel → heures sup. Le 16/09/2026, juin a été
rejoué de la même façon, à part, par
`backend/scripts/colorplast_feuilles_juin_test.py` (données dans
`backend/scripts/backtest/colorplast_feuilles_juin.py`) : les quatre feuilles
de la fenêtre, `data/colorplast/pointages/2026-06/semaine-22.pdf` à
`semaine-25.pdf`, posées au calendrier réel (25 au 29/05 dans mai, 1ᵉʳ au 19/06
dans juin), les saisies d'heures sup effacées, les sept bulletins générés, puis
la base remise en état. Règle de lecture, celle de Gaëlle : heures = fin −
début − 0,5 h de pause au-delà de 6 h.

### Ce que disent les feuilles, semaine par semaine

| | S22 (25→29/05) | S23 | S24 | S25 | Règle hebdo, 25 % / 50 % | Payé par le cabinet |
|---|---|---|---|---|---|---|
| Bugny | 39,00 | 43,00 | 46,50 | 46,50 | **12,00 / 7,00** | 14,00 / 7,00 |
| Espinosa | 34,50 | 44,00 | 45,08 | 47,00 | **12,00 / 7,08** | 16,00 / 7,00 |
| Fuckar | 32,00 | 46,00 | 40,00 | 43,00 | **9,00 / 3,00** | 4,00 / 3,00 |
| Cotte | 37,50 | 41,50 | 41,50 | 42,50 | **8,50 / 0** | 0 / 0 |
| Gautheron | 31,50 | 39,50 | 31,00 | 39,00 | **0,50 / 0** | 0 / 0 |
| Demory | arrêt | blanc | 8,50 (mardi seul) | 39,00 | **0 / 0** | 0 / 0 |
| Girerd | sans feuille | | | | **0 / 0** | 0 / 0 |

Règle hebdomadaire sur un contrat de 39 h : la 40ᵉ à la 43ᵉ heure de la semaine
à 25 %, au-delà à 50 %. Rien n'est assimilé à du travail dans ces quatre
semaines : le congé et le férié du 25/05 sont à 0 h prévue au calendrier, et une
absence non payée ne l'est jamais.

### Ce que le moteur retrouve

**Exactement la règle hebdomadaire, pour les sept, au centième d'heure** —
jusqu'aux 7,08 h à 50 % d'Espinosa (mercredi 10/06, 6h45–17h20). La fenêtre
imprimée est bien 25/05 → 21/06. Sur les semaines 23, 24 et 25, le moteur et
le cabinet tombent d'accord **jour pour jour** : Bugny 4, 4 + 3,5, 4 + 3,5 ;
Espinosa 4 + 1, 4 + 2, 4 + 4 ; Fuckar 4 + 3, 1, 4. Tout l'écart avec les
bulletins tient à la semaine 22 et aux compensations propres au cabinet.

| | Moteur, depuis les feuilles | Cabinet | Écart de brut (EYWAI − Quadra) |
|---|---|---|---|
| Bugny | 12 / 7 | 14 / 7 | −35,70 |
| Espinosa | 12 / 7,08 | 16 / 7 | −76,40 |
| Fuckar | 9 / 3 | 4 / 3 | +76,94 |
| Cotte | 8,5 / 0 | 0 / 0 | +140,34 |
| Gautheron | 0,5 / 0 | 0 / 0 | +8,21 |
| Demory, Girerd | 0 | 0 | 0,00 |

### Le classeur du cabinet, prolongé à S25, reproduit les bulletins

Sa méthode, lisible dans ses formules : pour chaque jour, l'écart avec l'horaire
du jour (positif ou négatif) ; par semaine, `Majo 25 % = MIN(total + 4 ; 8) −
4`, le reste à 50 % ; puis la somme des semaines, **semaines négatives
comprises**. Ses journées de S22 à S24 sont les nôtres, à deux lectures près
(Fuckar mardi 26/05 compté 1 h au lieu de 0,5 ; Cotte ses vendredis 7h–15h
comptés 7 h au lieu de 7,5). Ses colonnes S25 sont vides. Remplies depuis la
feuille :

- Bugny, S25 : +1, +1, +1, +1, +3,5 = 7,5 → 4 à 25 %, 3,5 à 50 %. Total 2 + 4 +
  4 + 4 = **14** et 0 + 0 + 3,5 + 3,5 = **7**. Le bulletin.
- Espinosa, S25 : +1,5, +1,5, +2,5, +2, +0,5 = 8 → 4 et 4. Total **16** et
  **7**. Le bulletin.
- Fuckar, S25 : −1, +1,5, +0,5, −0,5, +3,5 = 4 → 4 et 0. Total à 25 % : −5 +
  4 + 1 + 4 = **4** ; à 50 % : **3**. Le bulletin.

Trois bulletins retrouvés à l'heure près par une troisième source : la fenêtre
25/05 → 21/06 est confirmée, et la lecture des feuilles avec elle.

### La semaine 22 : là où tout se joue

Le lundi 25 mai est le lundi de Pentecôte, férié, et la **journée de
solidarité** de Colorplast (`settings.jour_solidarite`). Bugny et Cotte l'ont
travaillée, 7 h chacun. Espinosa, Gautheron et Girerd ont posé un congé.
Fuckar ni l'un ni l'autre : sa feuille est blanche. Demory est en accident du
travail jusqu'au 29.

**Bugny** — 39 h pointées, dont 7 de solidarité. Le cabinet compte +2 (mercredi
+1, jeudi +1 ; le lundi vaut sa journée de solidarité, le mardi 7h–15h30 est lu
comme une journée pleine). Le moteur compte 0 : 39 h, c'est le contrat. La loi
(art. L3133-8) dit que les heures de la journée de solidarité, dans la limite
de 7, ne sont pas des heures supplémentaires : 32 h de travail effectif, aucune
majoration due. Les 2 h du cabinet ne le sont pas.

**Espinosa** — 34,5 h et un congé posé. Le cabinet compte 4 h (34,5 pour 30,5
prévues). Le moteur 0 : le congé est à 0 h prévue, rien n'est assimilé, et
34,5 h restent sous 39. Or depuis Cass. soc. 10 septembre 2025 (confirmé le 7
janvier 2026), **un congé payé compte dans le seuil de déclenchement des heures
sup**. Le cabinet a raison sur cette semaine, et c'est le moteur qui manque
4 h — par la donnée, pas par la règle : voir ci-dessous.

**Gautheron** — 31,5 h et un congé posé : 1 h par la même logique, que le
cabinet compte aussi. Il compte ensuite **−8** pour son absence du 10/06, déjà
retenue sur le bulletin (7,80 h), et son total tombe à −6,5 : il ne paie rien.
Une absence non payée réduit la semaine où elle tombe ; elle n'efface pas les
heures sup d'une autre semaine. Dû, sans compensation : 1 h (S22) + 0,5 h
(S23).

**Fuckar** — 32 h, journée de solidarité ni travaillée ni couverte par un
congé. Le cabinet compte **−7** pour la journée due, +1, +1, soit −5, qu'il
retranche des heures sup des semaines suivantes : 4 h payées à 25 % au lieu
de 9. Une journée de solidarité non travaillée se retient sur le salaire (7 h
au taux normal) ; elle ne se convertit pas en heures sup négatives à 125 %. Le
moteur ne peut pas la voir : le 25/05 est un férié à 0 h sans pointage, et un
trou n'est pas une absence. Ses 9 h à 25 % et 3 h à 50 % des semaines 23 à 25
sont dues ; les 7 h de solidarité restent à retenir, ce que personne n'a saisi.

**Cotte** — 37,5 h dont 7 de solidarité : 0, partout. Puis 41,5, 41,5 et
42,5 h : 8,5 h à 25 % (7,5 dans la lecture du cabinet). **Rien n'est payé en
juin** ; son bulletin de juillet porte 8 h. Le classeur porte la consigne « ne
pas payer les heures sup quand compteur récup en négatif » : les heures sont
reportées ou compensées par un compteur que nous ne connaissons pas. Les heures
supplémentaires se décomptent par semaine civile et se paient avec le mois ; un
report suppose un repos compensateur de remplacement, qui n'existe pas ici.

**Demory** — rien à trouver, rien trouvé.

### Ce que cela dit du moteur

**La chaîne pointage → heures sup est juste.** Sur 4 semaines × 7 salariés, le
moteur donne ce que la règle hebdomadaire donne, et ce que le cabinet lui-même
compte dès qu'il n'y a ni férié, ni congé, ni compensation.

**Deux manques latents, tous deux dans la semaine 22, tous deux sans effet sur
les chiffres de juin :**

1. **Un congé ou un férié à 0 h prévue n'est pas assimilé.** L'analyseur
   (`analyzer.py`, `heures_assimilees`) compte les congés payés et les fériés
   à leurs `heures_prevues`. Le setup du backtest pose un congé avec les heures
   du jour (Gautheron 22/01 : 8,5 h) ; l'interface le pose à 0 h (Bugny, ses
   congés d'août) ; tous les fériés sont à 0 h. Le même congé compte ou ne
   compte pas selon la porte par laquelle il est entré. Pour les congés payés
   c'est désormais la règle légale qui est manquée (Cass. soc. 10/09/2025).
   Pour les fériés chômés, la Cour de cassation les exclut (1ᵉʳ déc. 2004,
   4 avril 2012) et l'administration les assimile ; le moteur a été écrit pour
   les assimiler et ne le fait jamais. Proposition : à 0 h prévue, replier sur
   l'horaire contractuel du jour de semaine — le repli qui existe déjà pour les
   retenues (`TYPES_SIGNIFICATIFS_A_ZERO_HEURE`).
2. **La journée de solidarité n'existe pas pour le compteur hebdomadaire.** Ses
   heures travaillées (7 h chez Bugny et Cotte) entrent dans la semaine comme
   des heures ordinaires ; `calcul_brut` ne connaît la date que pour ne pas
   déduire le férié. Neutre à 39 h et 37,5 h ; à 41 h, le moteur aurait payé
   2 h que la loi ne majore pas.

Les deux manques se compensent chez Bugny en juin (0 h dans les deux sens) ;
ils ne se compenseraient pas ailleurs. À corriger ensemble, avec la question
du férié à trancher (Cour de cassation ou administration), puis rejouer
janvier et juin depuis les feuilles.

**Ce qu'on ne reproduira pas :** les compensations du cabinet entre semaines
(Fuckar −5, Gautheron −6,5, Cotte reporté à juillet). Si juin passait sur les
feuilles dans le rejeu, ce seraient ses écarts documentés : Bugny −2 h, Espinosa
−4 h, Fuckar +5 h, Cotte +8,5 h, Gautheron +0,5 h, avec les montants du tableau
plus haut. Le rejeu reste sur les saisies du cabinet ; le script des feuilles
tourne à part.

### À demander à Gaëlle

- Cotte : 8,5 h au-delà de 39 h sur les semaines 23 à 25, rien de payé en
  juin, 8 h en juillet. Quel compteur, et que compense-t-il ?
- Fuckar : les 7 h de solidarité non travaillées retirées de ses heures sup à
  25 % plutôt que de son salaire — voulu ?
- Bugny, mardi 26/05 : 7h–15h30 sur la feuille (8 h), comptée pleine.
