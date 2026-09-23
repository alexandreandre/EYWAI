# Compensation entre semaines : le solde négatif redevient une retenue

Décidé le 22/09/2026 avec Alexandre, après mesure. Corrige la spec
`2026-09-21-compensation-heures-entre-semaines-design.md`, dont le point 3
(« ce qui reste de négatif n'est ni retenu ni reporté ») est remplacé.

## Pourquoi

L'option « compensation des heures entre semaines » a été activée le 21/09
pour reproduire la méthode de Gaëlle. Les six mois de Colorplast rejoués à la
régulière le 22/09, avec et sans l'option, tout le reste égal :

| | Bulletins au centime | Écart absolu cumulé |
|---|---|---|
| Sans l'option | 16 / 37 | 3 028,81 € |
| Avec l'option | 13 / 37 | 3 677,40 € |

L'option éloigne de 648,59 € et coûte trois bulletins exacts. La cause tient
en une ligne : `_TYPES_REMPLACES` contient `absence_injustifiee`, si bien que
la compensation **efface les retenues d'absence de la fenêtre sans rien
remettre** quand le solde est négatif. Or Quadra retient. Janvier rejoué sans
l'option le prouve, toutes choses égales par ailleurs :

| Janvier | Quadra | avec l'option | sans l'option |
|---|---|---|---|
| Cotte | 2 351,89 | 2 398,38 (+46,49) | 2 351,89 (0,00) |
| Gautheron | 2 252,28 | 2 398,38 (+146,10) | 2 252,28 (0,00) |

Sans l'option, le moteur produit déjà les lignes de Quadra au centime et à la
date : « Absence injustifiée du 21/01/26 (base) », 3,14 h × 12,9492 = 40,66 €,
face à « Abs. Abs aut nonpayé 210126 » de même base, même taux, même montant.
Il n'y a donc rien à inventer : il faut cesser de détruire ce qui est juste.

## Ce qu'on change

Les heures supplémentaires de la fenêtre **absorbent** les absences
injustifiées dans l'ordre des jours ; ce qui reste est **retenu sur les
derniers jours manqués, à leur vraie date**.

C'est la convention que `_absences_injustifiees_de_la_semaine` applique déjà à
l'intérieur d'une semaine (« le surplus compense les manques dans l'ordre des
jours ; ce qui reste est retenu sur les derniers jours manqués »). On l'étend
à la fenêtre, on ne l'invente pas.

`compenser` produit déjà la quantité voulue : `Compensation.solde_negatif`
est, au signe près, le nombre d'heures à retenir.

- `solde_negatif == 0` : toutes les absences de la fenêtre sont absorbées.
  C'est le comportement actuel, celui qui rapproche de Quadra (Bugny mai
  −196,35 → +35,70 ; Espinosa juin −76,40 → +1,88 ; Demory avril −68,81 → 0).
- `solde_negatif < 0` : on conserve `−solde_negatif` heures d'absence, prises
  sur les jours les plus tardifs ; les plus anciennes sont absorbées.

Vérification arithmétique sur les deux bords :

| Semaines | net25 | net50 | solde | Absences du bilan | Retenu |
|---|---|---|---|---|---|
| +1, −5 | −4 → 0 | 0 | −4 | 5 h | 4 h (1 h absorbée) |
| −6, +10 | −6 → 0 | 10 → 4 | 0 | 6 h | 0 h (tout absorbé) |

## Ce qu'on ne change pas

- La formule des majorations (`min(TOTAL, 43 − durée)` et le reste à 50 %),
  semaines négatives comprises : c'est le classeur de Gaëlle, il tient.
- Les heures sup **saisies à la main** continuent de primer sur le calendrier.
- Les régularisations antérieures (`is_regularisation_anterieure`) ne sont
  jamais remplacées.
- Le compteur de récupération entre mois de Gaëlle reste **hors périmètre**.
  C'est un manque connu et assumé : il explique l'essentiel de l'écart qui
  subsistera (Espinosa mai, +281,80 €, à qui Gaëlle retire 12 h de journées
  « en récup » les 15 et 25/05). Ce chantier-ci ne le traite pas.

## Architecture

Trois unités, chacune testable seule.

**1. `absences_a_conserver(absences, solde_negatif)` — nouvelle, pure.**
Reçoit les absences injustifiées de la fenêtre (tous mois confondus) et le
solde. Rend la liste de celles à garder, quantités éventuellement réduites.

- Trie par date croissante.
- Parcourt **de la fin vers le début**, en gardant des heures jusqu'à
  concurrence de `−solde_negatif`.
- Une absence partiellement gardée voit ses `heures` réduites ; les autres
  sont écartées.
- Si les absences disponibles ne couvrent pas le solde, garde tout et
  signale le reliquat (voir « Garde-fou »).

**2. `appliquer_aux_mois` — modifiée.**
Aujourd'hui elle appelle `appliquer` mois par mois, sans vue d'ensemble. Or la
fenêtre est à cheval sur deux mois : la décision doit être prise **une fois**.
Elle collecte donc les absences de la fenêtre à travers tous les mois, appelle
`absences_a_conserver`, et passe le résultat à chaque appel de `appliquer`.

**3. `appliquer` — modifiée.**
Ne supprime plus les `absence_injustifiee_*` en bloc. Elle reçoit en plus les
absences à conserver et garde celles qui y figurent, avec leur quantité
retenue. Les heures sup de la fenêtre restent remplacées comme aujourd'hui.

Identification d'une absence : le triplet `(annee, mois, jour)` plus le `type`
(`absence_injustifiee_base` ou `absence_injustifiee_hs25`). Deux événements du
même type le même jour sont additionnés avant répartition.

## Flux

```
ecarts_par_semaine  ──►  compenser  ──►  Compensation(net25, net50, solde_negatif)
                                              │
       évènements de tous les mois ───────────┤
                                              ▼
                              absences_a_conserver(absences, solde)
                                              │
                                              ▼
                      appliquer(mois) : HS remplacées, absences filtrées
```

## Traçabilité

La mention du bulletin change d'un mot : « Solde non payé : −3,5 h » devient
**« Solde retenu : −3,5 h »**. `payslip_data.compensation_semaines` gagne un
champ `solde_retenu` (heures effectivement retenues) à côté de
`solde_negatif`, pour que l'audit distingue le calcul de son application.

## Garde-fou

Si `−solde_negatif` dépasse le total des absences injustifiées disponibles, on
retient tout ce qui existe et le résumé porte `reliquat_sans_jour` (heures non
imputables). La mention l'ajoute : « dont X h sans jour identifié ». On
n'invente jamais une retenue à une date où le salarié était présent.

Ce cas ne devrait pas se produire — `ecarts_par_semaine` et l'analyseur
ignorent les mêmes jours (trou, mois sans pointage) — mais il ne doit pas
passer en silence s'il arrive.

## Tests

**Unitaires, `absences_a_conserver`** (module pur, aucune base) :

1. Solde nul et absences présentes → liste vide, tout est absorbé (le cas
   d'une semaine négative couverte par les heures sup d'une autre : c'est
   Bugny en mai, le comportement que l'option gagne et qu'on préserve).
2. Aucune absence et solde négatif → liste vide et `reliquat_sans_jour`
   égal au solde (voir « Garde-fou »).
3. Solde de −4 h, absences de 5 h en un jour → 4 h gardées ce jour-là.
4. Solde de −4 h, absences de 2 h le 10 et 3 h le 20 → 3 h le 20 et 1 h le 10
   (on garde les plus tardives).
5. Solde de −10 h, absences de 5 h → 5 h gardées et `reliquat_sans_jour` de 5.
6. Deux absences du même type le même jour → additionnées avant répartition.

**Unitaires, `appliquer` / `appliquer_aux_mois`** :

7. Fenêtre à cheval sur deux mois : une absence dans chaque mois, solde qui
   n'en couvre qu'une → la bonne est gardée, dans le bon mois.
8. Une régularisation antérieure datée dans la fenêtre n'est pas touchée.

**De bout en bout, contre Quadra** (bac à sable, données réelles de la base de
test) :

9. Cotte, janvier 2026 : solde de −3,5 h, une ligne retenue le 21/01,
   3,14 h × 12,9492 = 40,66 € en base et 0,36 h × 16,1865 = 5,83 € en
   réduction de HS structurelles ; brut 2 351,89 €.
10. Gautheron, janvier 2026 : deux lignes, 2,24 h le 13/01 (29,01 €) et
    7,63 h le 14/01 (98,80 €) ; brut 2 252,28 €.
11. Bugny, mai 2026 : solde positif, aucune retenue, brut inchangé à
    2 988,04 € — la correction ne doit pas défaire ce que l'option gagne.

## Critère de réussite

Les six mois rejoués à la régulière avec l'option corrigée :

- Cotte janvier, Gautheron janvier et Demory juin reviennent au centime ;
- aucun bulletin aujourd'hui exact ne se dégrade ;
- l'écart absolu cumulé descend d'environ 300 €.

La décision de **garder ou non l'option pour août** est prise sur ce rejeu,
pas avant. Si l'option corrigée reste moins bonne que son absence
(3 028,81 € sans elle), elle est éteinte le temps de traiter le compteur de
récupération.
