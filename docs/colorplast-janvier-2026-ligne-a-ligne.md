# Colorplast, janvier 2026 : EYWAI contre Quadra, ligne à ligne

Rejeu du 14/09/2026 au soir (`backend/scripts/colorplast_janvier_feuilles_test.py`),
comparé au PDF du cabinet `data/colorplast/bulletins/2026-01/01-2026-colorplast.pdf`.
Cinq salariés : Bugny, Cotte, Espinosa, Gautheron, Girerd.

Convention : **écart = EYWAI − Quadra**.

## Ce qui est identique au centime

Sur les cinq bulletins, toutes ces lignes tombent exactement :

- salaire de base, heures sup structurelles 25 %, sous-total contractuel ;
- heures sup conjoncturelles 25 % et 50 % ;
- prime d'ancienneté, prime exceptionnelle ;
- retenue d'absence congés payés, indemnité de CP (part base et part HS) ;
- absences non rémunérées (Cotte 40,66 ; Gautheron 29,01 + 98,80) et la
  réduction d'heures sup structurelles qui les accompagne (5,83 ; 18,29) ;
- **salaire brut** (Girerd +0,01 d'arrondi) ;
- toutes les cotisations salariales et patronales nommées : maladie, AT/MP,
  vieillesse plafonnée et déplafonnée, AGIRC-ARRCO T1 + CEG, famille, chômage,
  AGS, APEC, prévoyance, retraite supplémentaire cadre, mutuelle isolé,
  CSG déductible, CSG/CRDS non déductible, réduction salariale HS ;
- **réduction générale** pour les trois salariés sans absence ;
- acompte, indemnité de transport, remboursement de notes de frais ;
- **net imposable**, **net à payer avant impôt**, **PAS**, **net à payer**
  (sauf Cotte −0,03 et Gautheron −0,10) ;
- cumul bruts, cumul net imposable, cumul PAS ;
- mention « dont évolution de la rémunération… » ;
- plafond Sécu pour les salariés sans absence.

## Ce qui diffère

### 1. Réduction générale quand il y a des absences non rémunérées — le seul écart d'argent important

**Corrigé le 15/09 (f79f3bb3).** État avant / après :

| | EYWAI avant | EYWAI après | Quadra | reste |
|---|---|---|---|---|
| Cotte | −643,01 | −608,20 | −609,61 | +1,41 |
| Gautheron | −689,65 | −577,71 | −582,21 | +4,50 |
| Bugny / Espinosa / Girerd | −569,91 / −524,94 / −252,64 | inchangés | identiques | 0,00 |

Cause exacte, vérifiée en inversant la formule RGDU (décret 2025-887,
Tmin 0,02 / Tdelta 0,3781 / P 1,75 / SMIC de référence gelé 12,02) : le
nombre d'heures du SMIC de référence.

| | heures utilisées par notre coefficient | heures implicites chez Quadra |
|---|---|---|
| Bugny | 189,51 | 189,51 |
| Espinosa | 184,99 | 184,99 |
| Girerd | 168,97 | 168,97 |
| Cotte | **169,00** | **165,64** |
| Gautheron | **169,00** | **158,46** |

Notre SMIC de référence partait des heures contractuelles (169 h) augmentées
des heures sup conjoncturelles, **sans retrancher les heures d'absence non
rémunérée**. Quadra part des heures réellement payées.

Le calcul du brut expose désormais `heures_absence_non_payees` — les heures
dont la paie a effectivement été retirée par une absence injustifiée, une
absence non rémunérée ou un férié chômé non payé, part base et part heures sup
structurelles comprises — et les deux pipelines (bulletin et simulation) les
retranchent du SMIC de référence.

L'arrêt maladie reste hors périmètre : la rémunération y est maintenue en tout
ou partie et le SMIC de référence suit alors la part restée à la charge de
l'employeur. Règle distincte, sans référence cabinet à ce jour, à traiter à
part.

#### Le reste de 1,41 € et 4,50 €

En inversant la réduction cumulée de Quadra mois par mois sur les sept
bulletins, on retrouve ses heures de SMIC de référence. La méthode est validée
sur les deux salariés sans absence non rémunérée : chez Bugny et Girerd, les
heures implicites collent au « cumul heures » imprimé à ± 0,05 h près sur sept
mois.

En janvier, Quadra utilise **165,6355 h** pour Cotte et **158,4595 h** pour
Gautheron (mesure à ± 0,001 h), là où les heures payées valent 165,50 et
158,00. Quadra ne retranche donc pas la totalité de l'absence : il en garde
0,135 h et 0,460 h, soit environ 4 %.

Aucune règle simple ne reproduit les deux valeurs :

| règle testée | Cotte | Gautheron |
|---|---|---|
| Quadra (mesuré) | 165,6355 | 158,4595 |
| heures payées (ce que nous faisons) | 165,500 | 158,000 |
| prorata de la rémunération entière | 165,724 | 158,705 |
| prorata hors prime d'ancienneté | 165,649 | 158,469 |
| fraction constante des heures d'absence | 96,1 % | 95,8 % |
| taux horaire constant sur la retenue | 13,82 €/h | 13,86 €/h |

Les deux dernières lignes montrent qu'il ne s'agit ni d'une fraction constante
ni d'un taux constant. Les deux salariés ayant exactement la même structure de
paie, deux observations ne suffisent pas à identifier la convention. Le reste
vaut 0,2 % de la réduction et joue en notre défaveur : nous réclamons un peu
moins que le cabinet. À demander à Gaëlle plutôt qu'à deviner.

#### Ce que le recoupement a révélé en plus : l'arrêt maladie

Le même calcul, appliqué aux sept mois de Marion, montre un décalage stable :

| | janv. | mars | avril | mai | juin | juil. |
|---|---|---|---|---|---|---|
| heures implicites − heures imprimées | +0,46 | +24,02 | +23,87 | +23,91 | +28,14 | +24,77 |

Le saut apparaît en mars, au mois exact de son arrêt maladie (16→28/03 puis
29/03→28/04), et ne se résorbe plus. **Quadra ne retire pas les heures d'arrêt
maladie du SMIC de référence**, conformément à la règle BOSS : en cas de
suspension avec maintien de rémunération, le SMIC ne baisse qu'à proportion de
la part restée à la charge de l'employeur. Notre moteur ne les retire pas non
plus depuis la correction du 15/09 : les deux sont alignés sur ce point.

Deux anomalies d'un mois restent inexpliquées, sans lien avec les absences :
Girerd en juin (+3,96 h alors qu'il n'a aucune absence) et Bugny en juillet
(−3,90 h). Ce sont probablement les régularisations Quadra du « rythme » de
juin.

### 2. Autres contributions employeur : deux taux de paramétrage

Quadra regroupe tout sous « Autres contrib. dues par empl. » avec plusieurs bases.

| | EYWAI | Quadra | écart |
|---|---|---|---|
| Bugny | 63,36 | 53,22 | +10,14 |
| Cotte | 49,31 | 39,61 | +9,70 |
| Espinosa | 63,87 | 53,63 | +10,24 |
| Gautheron | 47,21 | 40,26 | +6,95 |
| Girerd | 79,63 | 89,41 | −9,78 |

Deux causes, additives :

- **Formation professionnelle**. Le taux global de Quadra sur le brut est
  1,6458 % ; nos rubriques hors formation (CSA 0,30 + FNAL 0,10 + dialogue
  social 0,016 + taxe d'apprentissage 0,59 + solde 0,09) font 1,096 %. Le
  reste est 0,55 %, le taux des entreprises de moins de 11 salariés. Nous
  appliquons 1 %. Écart : 0,45 % du brut.
- **Forfait social absent chez nous.** Quadra ajoute une ligne à 8 % sur la
  prévoyance et la mutuelle patronales (Bugny 3,46 sur 43,29 ; Espinosa 3,47
  sur 43,40 ; Gautheron 3,18 sur 39,70 ; Cotte 0,88 sur 10,94 ; Girerd 7,88
  sur 98,56) et, pour Girerd seul, **20 % sur la retraite supplémentaire
  cadre** (19,00 sur 94,98).

Conséquence directe sur le **coût total employeur** : Bugny +10,15,
Espinosa +10,25, Girerd −9,75, Cotte −24,19, Gautheron −102,10 (ces deux
derniers cumulant l'effet de la réduction générale).

### 3. Mutuelle famille : bon montant, mauvaise place

Espinosa, Gautheron et Girerd paient 98,13 € de sur-cotisation « GAN mutuelle
famille ». Quadra la place **après le net imposable**, en retenue nette
(SMU2 −98,13). Nous la portons comme une cotisation du bloc principal.

Le net imposable, le net à payer avant impôt et le net à payer sont justes
(le moteur l'exclut du net imposable), mais :

- notre **total des retenues salariales** est supérieur de 98,13 ;
- notre **montant net social** est inférieur de 98,13 (Espinosa 2 440,05 au
  lieu de 2 538,18 ; Girerd 3 051,51 au lieu de 3 149,64 ; Gautheron 1 670,86
  au lieu de 1 769,08).

Le montant net social est une donnée réglementaire transmise aux organismes :
c'est le seul écart de cette liste qui sorte de l'entreprise.

### 4. Montant net des heures supplémentaires exonérées

| | EYWAI | Quadra | écart |
|---|---|---|---|
| Bugny | 625,85 | 645,56 | −19,71 |
| Cotte | 248,50 | 256,64 | −8,14 |
| Espinosa | 592,42 | 611,08 | −18,66 |
| Gautheron | 237,23 | 245,46 | −8,23 |
| Girerd | 400,70 | 413,31 | −12,61 |

Formules, exactes sur les cinq :

- Quadra : brut HS − **6,8 %** (CSG déductible) sur la base abattue ;
- EYWAI : brut HS − **9,7 %** (CSG + CRDS non déductibles) sur la même base.

Cette ligne est un montant *imposable* (elle alimente le revenu fiscal de
référence). La CSG non déductible et la CRDS ne se retranchent pas d'un net
imposable : Quadra a raison, nous retirons 2,9 % de trop.

### 5. Compteur d'heures de l'encadré

| | EYWAI « cumul heures » | Quadra « heures période / cumul heures » |
|---|---|---|
| Bugny | 169,00 | 189,50 |
| Espinosa | 169,00 | 185,00 |
| Cotte | 165,50 | 165,50 |
| Gautheron | 158,00 | 158,00 |
| Girerd | 169,00 | 169,00 |

Quadra ajoute les heures sup conjoncturelles au compteur, nous non. C'est le
« cumul heures faux » signalé par Gaëlle. Attention : notre calcul de la
réduction générale, lui, *les compte déjà* (§ 1) — c'est le champ stocké et
imprimé qui ne les porte pas.

Cumul heures sup : identique sauf chez les deux salariés absents, où Quadra
retranche les heures sup perdues par l'absence et nous non (Cotte 17,33 contre
16,97 ; Gautheron 17,33 contre 16,20). Même cause pour la base de la déduction
forfaitaire patronale (Cotte −0,50 ; Gautheron −1,61).

### 6. Plafond Sécu imprimé

Nous imprimons toujours 4 005,00. Quadra le proratise en jours calendaires
d'absence : Cotte 3 875,81 (30/31), Gautheron 3 746,61 (29/31).

Notre plafond interne suit Quadra pour Gautheron (3 746,61) mais pas pour
Cotte (4 005,00 au lieu de 3 875,81) : deux absences non rémunérées, deux
traitements différents. À corriger et à faire remonter jusqu'à l'impression.

### 7. SMIC horaire imprimé

Nous imprimons 12,31, Quadra 12,02. Le barème `smic` n'est pas historisé : il
n'a qu'une version active, celle d'aujourd'hui, et un bulletin de janvier
affiche donc le SMIC de septembre. Le calcul, lui, est juste : la réduction
générale lit `reduction_generale.smic_reference_horaire` = 12,02.

### 8. Compteurs de congés payés

Écarts sur les cinq. Le solde N est bon à 0,02 près (16,66 contre 16,64) mais
les **congés pris ne sont jamais décomptés** et le solde N-1 est faux :

| | N-1 acquis / pris / solde EYWAI | Quadra | N pris EYWAI | Quadra |
|---|---|---|---|---|
| Bugny | 25 / 0 / **50** | 28 / 13 / 15 | 0 | 0 |
| Cotte | 25 / 0 / 25 | 25 / 23 / 2 | 0 | 0 |
| Espinosa | 25 / 0 / 27 | 27 / 22 / 5 | 0 | 0 |
| Gautheron | 25 / 0 / 17,5 | 25 / 25 / 0 | 0 | 7 |
| Girerd | 25 / 0 / 27 | 27 / 24 / 3 | 0 | 0 |

Le cas de Bugny est incohérent en interne : solde 50 pour 25 acquis et 0 pris.

Repos compensateur : nous affichons un solde (Bugny 34,07 ; Espinosa 29,06),
Quadra laisse la case vide.

## Écarts de présentation, sans conséquence de montant

- Quadra scinde la maladie en deux lignes (7 % + 6 %), nous une seule à 13 % ;
  total identique.
- Quadra fusionne AGIRC-ARRCO T1 et CEG en une ligne à 4,01 %, nous deux
  lignes ; total identique.
- Prime d'ancienneté : Quadra affiche base 1 941,33 × 3 %, nous 2 426,65 ×
  2,4 % ; même montant.
- Congés payés : Quadra imprime une rubrique « BQCP arbitrage des congés
  payés » ; nous rendons l'arbitrage maintien / dixième en phrase sous le
  bloc, sans rubrique.
- Retenue d'absence : Quadra la quantifie en jours (1,00), nous en heures
  (7,80).

## Récapitulatif chiffré

| | Bugny | Cotte | Espinosa | Gautheron | Girerd |
|---|---|---|---|---|---|
| Brut | = | = | = | = | +0,01 |
| Net imposable | = | +0,37 | = | +1,16 | = |
| Net à payer | = | −0,03 | = | −0,10 | = |
| Montant net social | = | −0,02 | **−98,13** | **−98,22** | **−98,13** |
| Réduction générale | = | +1,41 | = | +4,50 | = | (corrigé, était −33,40 / −107,44)
| Autres contributions | +10,14 | +9,70 | +10,24 | +6,95 | −9,78 |
| Coût employeur | +10,15 | −24,19 | +10,25 | −102,10 | −9,75 |
| Cumul heures | −20,50 | = | −16,00 | = | = |
| Cumul heures sup | = | +0,36 | = | +1,13 | = |
| Net HS exonérées | −19,71 | −8,14 | −18,66 | −8,23 | −12,61 |

## À corriger, par ordre d'impact

1. ~~Réduction générale : retrancher les heures d'absence non rémunérée du
   SMIC de référence~~ — **fait le 15/09 (f79f3bb3)**. Reste à vérifier l'effet
   sur juin et juillet, où ce même défaut explique probablement le « rythme »
   qui décale Girerd et Marion, et à traiter le cas de l'arrêt maladie (§ 1).
2. Taux liés à l'effectif : formation professionnelle à 0,55 % sous 11
   salariés, forfait social 8 % sur prévoyance et mutuelle patronales, 20 %
   sur la retraite supplémentaire cadre (§ 2).
3. Mutuelle famille : la sortir du bloc cotisations et la poser en retenue
   nette après le net imposable, pour redresser le montant net social (§ 3).
4. Net des heures sup exonérées : 6,8 % et non 9,7 % (§ 4).
5. Compteur d'heures imprimé : y inclure les heures sup conjoncturelles, et
   retrancher les heures sup perdues par absence du compteur d'heures sup
   (§ 5).
6. Plafond Sécu : proratiser de la même façon dans tous les cas d'absence et
   l'imprimer proratisé (§ 6).
7. Historiser le barème SMIC pour que les mois passés s'impriment avec le
   leur (§ 7).
8. Compteurs de congés payés : décompter les congés pris, corriger le solde
   N-1 (§ 8).

## À demander à Gaëlle

- Espinosa, semaine du 5 au 9 janvier : la feuille donne 44 h, Quadra paie
  4 h à 50 %, ce qui suppose 45 h. Quelle saisie a-t-elle faite ?
- Les soldes de congés N-1 d'ouverture (Bugny 28, Espinosa 27, Girerd 27
  chez Quadra contre 25 chez nous).
