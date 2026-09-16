# Colorplast, avril 2026 : EYWAI contre Quadra, ligne à ligne

Rejeu du 16/09/2026 (`backend/scripts/colorplast_rejeu_test.py --jusqu-a 4`),
comparé au PDF du cabinet `data/colorplast/bulletins/2026-04/`. Sept salariés :
Fuckar arrive le 07/04. Fenêtre des variables : **23/03 → 19/04**.
Convention : **écart = EYWAI − Quadra**.

Avril apporte trois choses neuves : un mois d'entrée avec **retenue d'entrée**
(Fuckar), un **jour férié non payé** faute d'ancienneté (Demory), et la part
patronale de mutuelle **réintégrée au net imposable** à partir de ce mois.

## État

| | Brut | Net à payer | Impôt | Net social | Compteurs | Plafond | Coût patronal | Déduction HS | Allègement |
|---|---|---|---|---|---|---|---|---|---|
| Bugny | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cotte | ✓ | ✓ | ✓ | ✓ | *écart assumé* | ✓ | ✓ | ✓ | −0,51 |
| Demory | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | −0,42 |
| Espinosa | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Fuckar | ✓ | ✓ | ✓ | ✓ | *écart assumé* | ✓ | ✓ | ✓ | *écart assumé* |
| Girerd | +0,01 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Gautheron | *en attente* | | | | | | | | |

Les sept bruts, les sept nets à payer, les sept prélèvements à la source, les
sept plafonds et les sept déductions patronales d'heures sup tombent au centime.

## Ce qui a été corrigé

### La retenue d'entrée gonflait l'allègement

Fuckar est embauché le 07/04 : le mois porte **30,50 h non travaillées** avant
son arrivée, retenues sur son salaire. Ces heures restaient comptées dans le
SMIC de référence qui sert de base à l'allègement de cotisations — le moteur
raisonnait sur l'horaire du contrat, pas sur ce qui avait été payé.

C'est le même défaut que celui corrigé en janvier pour les absences non payées,
sur un autre chemin : une heure non payée ne doit alimenter ni le compteur ni la
base de l'allègement. Corrigé et couvert par un test
(`test_retenue_entree_sortie_heures.py`).

### Un jour férié non payé se déduisait sur l'horaire planifié

Demory a moins de trois mois d'ancienneté : la loi (art. L3133-3) ne lui garantit
pas le paiement d'un jour férié chômé, et le cabinet ne le lui paie pas. Nous
non plus — mais nous retirions **l'horaire planifié du jour** (8,50 h) au lieu de
la **référence journalière légale**.

Le brut ne bougeait pas, mais le décompte, si. Le moteur retient désormais le
plus petit des deux, ce qui est la règle : on ne peut pas retirer plus qu'une
journée légale. Couvert par `test_ferie_non_paye_journee_legale.py`.

### Un chiffre faux dans le jeu de test, pas dans le moteur

Le jeu d'essai posait 7,00 h d'absence pour Demory là où il en fallait 7,80.
Le cabinet **imprime la part de base** d'une absence ; sur un contrat à 39 h le
moteur répartit chaque heure d'absence entre base (35/39) et heures sup
structurelles (4/39). Une journée complète vaut donc 7,80 h à poser, dont 7,00
de base.

J'avais d'abord mis cet écart sur le compte d'une incohérence du moteur. C'était
faux : le moteur était juste, le jeu de test ne l'était pas.

## Ce que nous ne reproduisons pas, et pourquoi

Ces écarts sont inscrits nommément dans le rejeu (`ecarts_documentes`) : le
contrôle les retire puis vérifie le reste au centime, plutôt que d'élargir une
tolérance qui masquerait aussi une régression.

### Le mois d'entrée de Fuckar : 42,38 € d'allègement

Son bulletin Quadra porte « **14,28 H.sup exo / 3,05 H n.exo** » : le cabinet
garde ses 17,33 h structurelles **entières** au compteur (22,33 avec ses heures
sup) tout en n'en exonérant que 14,28. Les 3,05 h non exonérées sont exactement
la part structurelle des 30,50 h qu'il n'a pas travaillées avant son embauche.

Autrement dit, le cabinet sait que ces heures ne sont pas dues — il refuse de les
exonérer — mais il les laisse au compteur et dans sa base d'allègement. Nous les
sortons des deux. Sur les 42,38 € d'écart, environ 34 viennent de là et 8 du
décalage habituel entre les heures que le cabinet imprime et celles sur
lesquelles il calcule.

### Cotte traîne son congé pour événement familial de mars

23,40 h au compteur et 2,40 h au compteur d'heures sup, que le cabinet avait
retirées en mars et que nous gardons. Le raisonnement est dans
`docs/colorplast-mars-2026-ligne-a-ligne.md` : une absence payée ne réduit pas
le compteur, et le cabinet n'est pas cohérent avec lui-même là-dessus.

### Deux petits restes d'allègement : 0,51 € et 0,42 €

Cotte et Demory, même famille que les écarts de janvier et de mars : dès qu'il y
a une absence, le cabinet compte une fraction d'heure de plus ou de moins, sans
règle reproductible. C'est la **question 1** posée à Gaëlle — sur quelles heures
Cegid calcule-t-il exactement.

## Ce qui reste ouvert

### Gautheron : en arrêt tout le mois

Arrêt du 29/03 au 28/04. Son bulletin Quadra est **négatif** : 20,20 € de brut,
−114,82 € à payer, et un allègement qui se retourne en remboursement (+35,34).
Le cabinet ne lui verse aucun maintien de salaire.

Nous ne pouvons pas la comparer tant que la question du maintien n'est pas
tranchée : avec plus de quatre ans d'ancienneté, l'article L1226-1 lui garantit
90 % de son salaire pendant 30 jours, et notre moteur refuse délibérément de
descendre sous ce plancher. Elle est imprimée au rejeu sans le faire échouer.

**Question 4** à Gaëlle : chez Colorplast, qui verse le complément de salaire au
delà du 3ᵉ jour d'arrêt ?

### Girerd : 0,01 € sur le brut

Un centime, stable depuis janvier, sur un brut de 3 799,06. Sans conséquence sur
le net, l'impôt ni les cotisations. Arrondi de ligne chez l'un ou chez l'autre.
