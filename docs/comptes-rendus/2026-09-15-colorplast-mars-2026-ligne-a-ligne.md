# Colorplast, mars 2026 : EYWAI contre Quadra, ligne à ligne

Rejeu du 15/09/2026 (`backend/scripts/colorplast_rejeu_test.py`), comparé au PDF
du cabinet `data/colorplast/bulletins/2026-03/`. Six salariés : Demory arrive le
23/03. Convention : **écart = EYWAI − Quadra**.

Mars apporte trois mécanismes que ni janvier ni février ne contenaient : un
congé pour événement familial, un arrêt maladie avec maintien partiel, et un
mois d'entrée.

## État

| | Brut | Net à payer | Impôt | Net social | Compteurs | Coût patronal | Déduction HS | Allègement |
|---|---|---|---|---|---|---|---|---|
| Bugny | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cotte | ✓ | +0,01 | ✓ | +0,01 | *écart assumé* | ✓ | ✓ | −5,71 |
| Demory | ✓ | −0,01 | ✓ | −0,01 | ✓ | ✓ | ✓ | −29,70 |
| Espinosa | ✓ | −0,01 | ✓ | −0,01 | ✓ | ✓ | ✓ | ✓ |
| Girerd | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | −0,01 |
| Gautheron | *en attente* | | | | | | | |

## Ce qui a été corrigé

### Le mois d'entrée comptait un mois plein d'heures

Demory est embauché le 23/03. Son bulletin Quadra porte 47,50 h de base et
3,00 h structurelles, soit 50,50 h de période. Nous comptions **154,67 h** — les
151,67 h d'un mois plein plus ses 3 h — parce que le compteur partait de la durée
contractuelle mensuelle sans regarder ce qui avait été payé.

Le compteur alimentant le SMIC de référence, l'allègement suivait : −248,91 au
lieu des −201,39 du cabinet. Le calcul du brut expose désormais les heures de
base réellement payées ; un mois plein est inchangé.

### Le congé pour événement familial était invisible

Le jour était écrit sous le type `conge`, que le moteur ne lit nulle part : ni
travaillé ni en congé, il ne figurait pas au bulletin et **minorait les heures
supplémentaires de sa semaine**. 371 jours étaient dans ce cas sur le groupe au
26/08/2026.

Tranché sur le bulletin de mars de Cotte (congé du 25 au 27 février) : absence
déduite sur la référence journalière légale, quote-part d'heures sup
structurelles retirée, puis maintien du total — brut inchangé. Chez Quadra :
271,93 + 38,85 retirés, 310,78 remis.

Le repos compensateur souffre du même aveuglement mais n'a aucun bulletin de
référence : laissé tel quel volontairement.

### Il était aussi rattaché au mauvais mois

Les heures sup et les absences non payées suivent la période de paie ; tout le
reste était rattaché au mois civil. Le congé du 25 au 27 février tombait donc
entre deux bulletins : hors de la fenêtre de février (arrêtée au 22), et
invisible en mars. Le cabinet, lui, le paie en mars.

L'arrêt maladie reste au mois civil : Quadra déduit l'intégralité de celui de
Gautheron (16 au 28/03) sur mars, alors que la semaine du 23 appartient à la
fenêtre d'avril — il porte ses propres dates, pour les indemnités journalières
comme pour la DSN.

### Un mois d'entrée sans compteur de départ

La base de test portait des bulletins fantômes de janvier et février pour
Demory, embauché le 23/03 : 492,67 h et 1 056,21 € de cumul, dont le moteur
repartait. Le rejeu vide le maillon du mois précédent pour qui débute.

## Le maintien de salaire de Gautheron : question ouverte

Arrêt du 16 au 28 mars, prolongé jusqu'au 28 avril. Le cabinet lui verse
**310,78 €** de maintien, « du 16 au 18-03-2026 », puis plus rien : sur le
bulletin d'avril, arrêt complet du 29/03 au 28/04, elle est à **20,20 € de
brut**. Aucune indemnité journalière n'apparaît sur ses bulletins — la caisse
la paie directement.

### Ce que le bulletin nous a appris, et qui est acquis

310,78 = 3 × **103,59**, et 103,59 est la valeur exacte d'une de ses journées
complètes : 7 h de base à 12,9492 (90,64) **plus** sa quote-part d'heure
supplémentaire structurelle, 0,80 h à 16,1865 (12,95). C'est le même montant
que son indemnité de congé payé du 23 février.

Notre maintien en jours ouvrés ne restituait que la base. L'absence, elle,
retire les deux : un salarié à 39 h perdait ses heures structurelles sur un
jour pourtant maintenu. **Corrigé** — sans effet sur les contrats à 35 h, où
la part structurelle est nulle.

### Pourquoi nous ne descendons pas à 310,78 €

Marion a plus de quatre ans d'ancienneté. L'article L1226-1 lui garantit 90 %
de son salaire pendant 30 jours. Trois journées à 100 % valent moins que ce
plancher : notre moteur le calcule, signale `conflit_convention` et **retient
le légal**. C'est une protection délibérée, pas un défaut.

Le seul montage qui rendrait le bulletin du cabinet régulier est une prise en
charge par la **prévoyance GAN**, versée directement à la salariée et donc
absente du bulletin. C'est un montage courant, mais nous n'en avons aucune
trace.

Forcer le moteur à 310,78 € graverait une sous-paie possible dans les sept
sociétés. Tant que la question n'est pas tranchée, Gautheron est imprimée au
rejeu mais ne le fait pas échouer, et le paramétrage de Colorplast reste celui
d'avant l'essai.

**Question à Gaëlle** : chez Colorplast, qui verse le complément de salaire au
delà du 3ᵉ jour d'arrêt ? La réponse décide d'un paramètre, pas d'une ligne de
code — le moteur sait déjà exprimer un relais prévoyance.

### Un défaut du chargeur DSN, corrigé au passage

Les jours d'arrêt importés étaient posés sans leur nature ni leurs bornes.
Sans elles, le moteur les ignore pour le maintien : **aucun arrêt importé
d'une DSN ne produisait le moindre maintien de salaire**. Le chargeur les écrit
désormais, et le rejeu complète ceux déjà posés.

## Ce que nous ne reproduisons pas, et pourquoi

Ces écarts sont inscrits nommément dans le rejeu (`ecarts_documentes`) : le
contrôle les retire puis vérifie le reste au centime, plutôt que d'élargir une
tolérance qui masquerait aussi une régression.

### Le plafond Sécu proratisé d'une absence payée

Quadra ramène le plafond de Cotte à 3 575,89 au lieu de 4 005 pour ses 3 jours
d'événement familial. Le plafond ne se réduit que pour une absence **non
payée** ; Cotte est payé en plein. Et l'écart n'a **aucune conséquence
financière** : son brut (2 398,38) est sous le plafond dans les deux cas.

### Les heures d'une absence payée sorties du compteur

Quadra retire les 23,40 h de l'événement familial du compteur (480,10 au lieu de
503,50) et 2,40 h du compteur d'heures sup — alors qu'il **garde** les 15,60 h du
congé payé de Cotte en février (169,00 h de période). Deux absences payées, deux
traitements. Nous restons cohérents.

À noter : Quadra garde bien ces heures dans le SMIC de référence de son
allègement. Vérifié en inversant la formule — avec 480,10 h elle donnerait −398,
or il imprime −617,14, ce qui correspond à environ 503 h. Compteur imprimé et
base de l'allègement sont donc deux quantités différentes chez lui.

## Ce qui reste ouvert

### L'allègement du mois d'entrée de Demory : 29,70 €

Notre formule tourne sur les bonnes heures — 50,50, comme le cabinet — et donne
−231,09 là où il imprime −201,39. En inversant sa formule, ses heures implicites
valent environ 47,87, ce qui ne correspond ni aux 47,50 h de base seules, ni aux
50,50 h de période, ni à un prorata calendaire. Règle non identifiée.

### L'allègement de Cotte : 5,71 €

Même famille que l'écart de janvier : le cabinet compte une fraction d'heure de
plus ou de moins quand il y a une absence, sans règle reproductible. Question Q3
à Gaëlle.

### Le plafond Sécu de Marion : 2 957,61

Aucune règle simple ne le reproduit — ni les jours calendaires du mois, ni ceux
de la période de paie, ni le prorata des heures payées.
