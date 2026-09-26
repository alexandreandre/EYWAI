# Colorplast, février 2026 : EYWAI contre Quadra, ligne à ligne

Rejeu du 15/09/2026 (`backend/scripts/colorplast_rejeu_test.py`), comparé au
PDF du cabinet `data/colorplast/bulletins/2026-02/02-2026-colorplast.pdf` et à
la DSN `data/colorplast/dsn/2026-02.dsn`. Cinq salariés : Bugny, Cotte,
Espinosa, Gautheron, Girerd.

Convention : **écart = EYWAI − Quadra**.

## Résultat

| | Brut | Net à payer avant impôt | Impôt | Net social | Compteurs d'heures | Autres contrib. patronales | Déduction HS | Allègement |
|---|---|---|---|---|---|---|---|---|
| Bugny | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Cotte | 0,00 | +0,01 | 0,00 | +0,01 | 0,00 | 0,00 | 0,00 | +0,02 |
| Espinosa | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Gautheron | 0,00 | +0,02 | 0,00 | +0,02 | 0,00 | 0,00 | 0,00 | −0,26 |
| Girerd | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 | −0,01 |

Février tombe donc au centime, à un reste de 0,26 près chez Gautheron —
la traîne de l'écart de janvier, expliqué plus bas.

## Ce que février a appris

### L'allègement se calcule en cumulé depuis janvier

Le cabinet ne recalcule pas un allègement du mois isolé : il calcule
l'allègement dû sur **janvier + février réunis** et retranche celui déjà pris en
janvier. Vérifiable à la main sur Bugny — cumul brut 5 658,30 et cumul heures
358,50 (les deux figurent sur son bulletin), ce qui donne 1 099,4x, moins les
569,91 de janvier : 529,5x, exactement ce que Quadra imprime.

Conséquence pratique : **février ne peut être juste que si janvier l'est
d'abord**. Le cumul voyage de mois en mois dans `employee_schedules.cumuls`. Le
rejeu de février repose donc janvier avant de générer février, et contrôle brut
et compteurs de janvier comme porte d'entrée.

C'est aussi ce qui rattrape en partie l'écart de janvier : Cotte était à +1,41
en janvier et retombe à +0,02 en février.

### La fenêtre des variables de février : 26/01 → 22/02, vérifiée sur les faits

En comptant sur les feuilles de pointage les heures au-delà de 39 h, semaine par
semaine :

| Semaine | Gautheron | Espinosa | Bugny |
|---|---|---|---|
| 26–30 janvier | 0 | +3 | +6,5 |
| 2–6 février | +1 | +4 | +10 |
| 9–13 février | +1,5 | +6 | +13 |
| 16–20 février | +1 | +6 | +8,5 |
| **Total** | **3,5 h** | **19 h** | **38 h** |

Quadra a payé **exactement 3,5 h** à Gautheron et **19 h** (15 à 25 % + 4 à
50 %) à Espinosa. Deux salariés indépendants, au quart d'heure près : la fenêtre
26/01 → 22/02 est confirmée par les faits, pas seulement par la règle société.

### Bugny : 38 h relevées, aucune payée

Michel Bugny a fait 45,5 h, 49 h, 52 h et 47,5 h sur ces quatre semaines. Aucune
heure supplémentaire conjoncturelle ne lui a été payée en février. En janvier,
Quadra lui avait payé ses 20,5 h au centime près (12 à 25 % + 8,5 à 50 %), et en
mars il en touche 26. **Question posée à Gaëlle** — c'est de l'argent pour le
salarié, et le seul salarié concerné.

### Les congés payés de Cotte, décomposés comme le cabinet

Deux jours les jeudi 19 et vendredi 20 février. Quadra retire 15,60 h (14 h de
base + 1,60 h structurelles, soit 2 jours × 7 h et 2 × 0,80 h) puis remet
207,19 € d'indemnité — exactement la somme retirée, salaire maintenu, brut
inchangé. Nos trois lignes sont identiques aux siennes, quantités comprises.

À noter : la retenue se fait sur le **jour ouvré théorique** (7,80 h), pas sur
l'horaire réel du jour posé (le jeudi vaut 8,5 h et le vendredi 5 h chez Cotte).

## Ce qui a été corrigé pour y arriver

### Déduction forfaitaire sur les heures sup : l'arrondi du demi-centime

Sous 20 salariés, l'employeur déduit 1,50 € par heure supplémentaire. À 39 h,
17,33 h structurelles donnent 25,995. Quadra imprime **26,00**, nous imprimions
**25,99** — sur les cinq bulletins de février, et sur ceux de janvier que la
tolérance laissait passer.

Deux causes cumulées : `round` de Python retient le pair le plus proche, et
17,33 × 1,50 vaut de toute façon 25,994999999999997 en binaire. Le produit se
fait désormais en décimal, la moitié s'éloignant de zéro. Corrigé le 15/09, avec
`backend/tests/unit/payroll/test_deduction_hs_arrondi.py`.

Effet de bord : l'écart de Cotte en janvier passe de 0,04 à 0,03.

### Un jour de congé manquait au paramétrage

Le bulletin Quadra de Cotte porte « Congés payés : 190226-200226 », deux jours,
et son compteur CP N-1 pris passe de 23,00 en janvier à 25,00 en février. Le
setup du backtest n'avait que le 19.

## Ce qui reste

### Gautheron, −0,26 sur l'allègement

La traîne de janvier. Quadra ne retranche qu'environ 60 % de la part « heures
sup » d'une absence, et n'est pas cohérent avec lui-même (16,97 h imprimé /
16,99 pour la déduction / 17,11 pour l'allègement). Sur janvier l'écart était de
4,50 ; comme février repart de notre propre janvier, il en reste 0,26 sur le
mois et 4,24 sur le cumul des deux. Question Q3 à Gaëlle, non reproductible.

### Cotte et Gautheron, +0,01 et +0,02 sur le net

Résidu d'arrondi de la base des heures sup, sans conséquence.

## Défauts de données relevés dans la base de test

Ces deux points ne viennent pas du moteur mais fausseraient de vrais bulletins.

### Les absences importées de la DSN sont datées en fin de mois

| | Bulletin Quadra | Chargeur DSN |
|---|---|---|
| Cotte | 3,5 h le **21 janvier** | 3,5 h le **30 janvier** |
| Gautheron | 2,5 h le 13 et 8,5 h le **14 janvier** | 2,5 h le 29 et 8,5 h le **30 janvier** |

La fenêtre de janvier s'arrêtant au 25, ces copies mal datées ne pèsent pas sur
janvier — elles tombent dans la fenêtre de **février** et y créent des absences
qui n'ont jamais eu lieu (−46,49 de brut chez Cotte, −89,44 chez Gautheron). Le
chargeur date en revanche correctement les arrêts maladie, qui portent leurs
dates dans la DSN (Gautheron, 16 au 27 mars).

### Les heures sup existent en double

Pour février, chaque heure sup est présente deux fois dans `monthly_inputs` :
une posée par le setup du backtest, une chargée depuis la DSN. Le moteur
additionne au lieu de choisir : Espinosa en paie 30 et 8 au lieu de 15 et 4.

Le rejeu écarte les deux avant de générer. À traiter à la source avant tout
usage réel.
