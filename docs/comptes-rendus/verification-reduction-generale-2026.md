# Vérification de la réduction générale 2026 — réponses et conclusion

Date : 25/10/2026. Chantier : spec `docs/superpowers/specs/2026-09-29-verification-reduction-generale-design.md`,
plan `docs/superpowers/plans/2026-09-29-verification-reduction-generale.md` (tâches 9 à 12).
Données du jour : septembre repris de Quadra chez Colorplast et Comitech, bascule au 30/09,
octobre premier mois payé par Martine. Salariés en initiales. Les rapports nominatifs (CSV du
rejeu, `reponses.md`, `conclusion.md`, `octobre.md`) sont dans `data/_rapports/rgdu-2026/`,
hors git. Aucune écriture en base : piège à écritures posé avant tout import de l'application,
filet en lecture seule ; seules des écritures des droits à congés d'ancienneté ont été tentées
par le moteur, et bloquées.

## Méthode, en bref

- **Rejeu à trois colonnes** (`backend/scripts/verification_rgdu/rejouer.py`), par salarié et
  par mois : SMIC de référence de Quadra (DSN de janvier à juin, sinon inversion de sa
  réduction cumulée), de la loi (lu sur ses bulletins, `regle_du_mois`), de Martine (moteur en
  bac à sable, cumuls de Quadra au mois précédent). Colorplast et Comitech de janvier à
  septembre, Mont-Blanc de janvier à juillet (colonne Martine arrêtée à 90 salarié-mois sur 460 :
  Mont-Blanc n'a aucun bulletin Martine). Chaque écart de plus d'une demi-heure de SMIC ou d'un
  euro reçoit un classement final (`classement.py`).
- **Ouvertures au 30/09 et octobre à blanc** (`ouverture.py`) : la formule sur la base que lit
  le moteur redonne-t-elle la réduction cumulée de Quadra ? Puis les 26 bulletins d'octobre
  (planning prévu, saisies d'octobre en base), réduction décomposée en mois isolé, effet légal
  du cumul et écart d'ouverture, comparée à la loi.
- **Sur les mois repris**, Martine calcule avec ses propres données du mois (planning, absences,
  maintien conventionnel posé le 24/10), pas avec le bulletin de Quadra : ses écarts y disent
  d'abord une donnée du mois repris. Le vrai test des règles de Martine est octobre.

## Conclusion par société

### Colorplast — fiable à partir d'octobre 2026, à trois conditions
- **Quadra contre la loi** : conforme hors juin calculé à 12,31 € au lieu du SMIC gelé à
  12,02 € (5 salariés, repris en juillet), juillet-septembre connus seulement par inversion (pas
  de DSN ; baisse d'environ 50 € de SMIC en septembre chez presque tous, sans cause lisible), et
  le maintien conventionnel de M.G. non versé (rattrapé par rappels en octobre).
- **Martine contre la loi (octobre)** : SMIC du mois conforme sur les 8 bulletins. Réduction
  fausse sur 7 bulletins par l'ouverture (net −287,71 €) et sur M.G. par les rappels de maintien.
- **Conditions** : réécrire l'ouverture avec la base de Quadra (script corrigé, vérifié en
  mémoire : 7 bulletins sur 8 tombent sur la loi au centime) ; corriger à la main la réduction de
  M.G. ; compléter les fiches de F.A. et X.P. (sinon bulletin refusé).

### Comitech — fiable à partir d'octobre 2026, une condition
- **Quadra contre la loi** : janvier sans réduction (décision du 17/10 : suivre Quadra, fait),
  juin à 12,31 € repris en juillet, et des mois d'arrêt sans aucun salaire où Quadra déclare
  encore environ 18,5 h de SMIC (vraisemblablement les heures structurelles retirées ; DSN de
  juin : 222,90 € pour 0 € selon la loi) : **+480,19 € de réduction prise en trop (risque de
  redressement faible, signalé)**.
- **Martine contre la loi (octobre)** : les 19 ouvertures redonnent Quadra au palier près ;
  15 bulletins sur 18 conformes (écart ≤ 2,55 €, palier du coefficient) ; 3 faux par les
  rappels de maintien (S.G., D.J., D.S. : −704,98 €).
- **Condition** : corriger à la main ces trois réductions.

### Mont-Blanc — fiable à la bascule, si l'ouverture pose la base de Quadra
- **Quadra contre la loi** (534 salarié-mois, 349 identiques) : juin à 12,31 € repris en
  juillet ; un salarié dont Quadra ne compte pas les heures structurelles (−244,87 €) ; rappels
  de maintien ; point n° 1.
- **Ouverture simulée au 31/07** sur le « Cumul heures » imprimé : 70 salariés sur 76 à plus
  d'un euro, 11 515,43 € de réduction reprise au premier mois. Il faut les clés d'heures de
  Quadra (comme Comitech), et que l'import DSN n'écrive pas les cumuls de réduction (D4).

## Octobre à blanc : 26 bulletins

- **Calcul** : 26 sur 26 sans erreur du moteur. **Génération** : 24 générables, 2 refusés
  (F.A. et X.P., Colorplast : statut « en onboarding », date de naissance et RIB absents,
  `onboarding/domain/profile.py:16-22, 98-123`). Sans date de naissance, la DSN n'émettrait pas
  S21.G00.30.006 (`dsn_export/application/builder.py:1462`) ; sans RIB, le virement les écarte
  (`payroll/exports/paiement_salaires.py:152`).
- **Sans anomalie** : 15 bulletins (Comitech).
- **Anomalies classées** :
  - donnée à corriger — ouverture Colorplast sans la base de Quadra (8 bulletins : L.C. −174,92 ;
    M.G. −234,76 ; M.B. +67,41 ; A.E. +25,55 ; A.B. +11,38 ; X.P. +9,54 ; F.G. +8,02 ; F.A.
    +0,07). Cause : `scripts/reprise_colorplast_solde_ouverture.py`, corrigé (564c3253) ;
  - donnée à corriger — fiches de F.A. et X.P. ;
  - défaut de Martine — rappels de maintien (M.G., S.G., D.J., D.S.) : ajoutés au brut sans le
    SMIC qu'ils rétablissent (BOSS § 800, et c'est ce que fait Quadra) ;
    `payroll/documents/payslip_run_heures.py:1308-1315`. Réduction d'octobre trop basse de
    2 644,37 € ; M.G. rembourserait 606,28 € de réduction au lieu d'en recevoir 1 524,86 € ;
  - attendu — arrêts : S.G. (limite de 135 jours atteinte le 15/09, pas de maintien, alerte
    prévoyance), T.L. (moins d'un an d'ancienneté) ; paliers conformes au barème de la
    plasturgie ; rappels (M.G. 4 lignes, S.G. 404,80, D.S. 615,53, D.J. 431,10) et report du net
    négatif de T.L. (−419,75 €, net d'octobre 1 212,00 €) présents ; soldes de congés non
    imprimés au bac à sable seulement (écriture bloquée par le piège).
- **Réductions au regard de la loi** : SMIC du mois conforme sur les 26 (tolérance du BOSS
  § 630 ; forfait 216 jours à 150,28 h). Réduction conforme sur 16 bulletins (15 Comitech,
  F.A.) ; 7 de plus avec l'ouverture corrigée ; les 4 derniers avec la correction des rappels,
  vérifiée au bac à sable (ligne et cumul enregistrés au centime : S.G. 482,79 ; D.J. 870,73 ;
  D.S. 211,60).

## Réponses aux questions de la spec

| ID | Réponse | Montant | Priorité |
|---|---|---|---|
| F1 | Paramètres conformes (Tmin 0,02, Tdelta 0,3781 / 0,3821, P 1,75, 3 SMIC, 4 décimales) ; la docstring cite encore 2025-887 | 0 € | plus tard |
| F2 | 12,02 € figé ; Quadra a calculé juin à 12,31 € (50 salariés sur les trois sociétés) et l'a repris en juillet ; Martine à 12,02 € | juin +1 699,66 €, juillet −1 543,51 € (Quadra) | — |
| F3 | Effectif moyen de l'année précédente, saisi par année (5, 16, 70) ; règle des cinq ans non codée | 87,51 € / an / salarié au SMIC si faux | avant janvier 2027 |
| F4 | Un calcul par contrat ; Martine conforme (V.L., S.V. : écart 0,00 €) | 352 € évités sur S.V. | — |
| H1 | SMIC mensuel + heures sup et structurelles ; Quadra oublie les structurelles d'un salarié de Mont-Blanc | −244,87 € (Quadra) | — |
| H2 | Congés payés sans baisse ; Martine conforme en octobre | 0 € | — |
| H3 | Rapport des salaires ; Quadra valorise parfois autrement (point n° 2) ; Martine conforme | < 133 € / an | — |
| H4 | Maintien intégral : SMIC entier ; sinon rapport ; Martine conforme ; Quadra déclare ≈ 18,5 h de SMIC des mois sans salaire | +480,19 € (Quadra, Comitech) | signalé |
| H5–H8, H10–H12 | Conformes ; aucune activité partielle dans le périmètre | 0 € | — |
| H9 | Forfait : 151,67 × jours / 218, corrigé ; 150,28 h en octobre | 0 € | — |
| B1 | Brut L242-1 + PPV ; un rappel de maintien rétablit aussi le SMIC des mois d'arrêt (BOSS § 800) : Martine l'oublie | −2 644,37 € en octobre | avant la paie d'octobre |
| B2 | Le cumul « Bruts » est l'assiette, sauf janvier Comitech | 0 € | — |
| A1 | Remise à zéro en janvier : corrigé (`brut_annee_civile`) | — | — |
| A2–A4 | JEI exclusif, inactif rembourse, régularisation progressive ; Quadra aussi | 0 € | — |
| R1 | Comitech : oui (19 ouvertures au palier) ; Colorplast : non, corrigé dans le script | −287,71 € | avant la paie d'octobre |
| R2 | Suivre Quadra (17/10) : fait | 4 635,51 € hors Martine | — |
| R3 | Mont-Blanc : ouverture sur heures imprimées fausse pour 70 salariés sur 76 | 11 515,43 € | avant la bascule de Mont-Blanc |
| R4 | Contrats successifs conformes ; deux embauches bloquées par leur fiche | 2 bulletins | avant la paie d'octobre |
| D1 | SMIC du bloc 79 calculé par le moteur : corrigé | 0 € | — |
| D2 | Tmax corrigé ; reste l'arrondi Urssaf / Agirc-Arrco inversé | 0,01 € / mois | plus tard |
| D3 | Part 106 à la retraite complémentaire : corrigé | 0 € | — |
| D4 | Import DSN : cumul = montant du mois, codes 114-219 au lieu de 018 / 106 : toujours là | toute l'année au premier mois | avant la bascule de Mont-Blanc |
| P1 | SMIC du 1er janvier lu dans l'historique, alerte, testé | 0 € | — |
| P2 | Barème choisi par `is_active` seul, pas par année | tout rejeu de 2026 en 2027 | avant janvier 2027 |
| P3 | Bornes de collecte 0-0,5 : Tmax passerait pour Tdelta | 0,02 de coefficient | avant janvier 2027 |
| P4 | Plus de repli silencieux ; cumuls sans heures refusés | 0 € | — |
| P5 | Un test recopie encore le calcul des heures d'arrêt | — | plus tard |

## Corrections, par priorité

**Avant la paie d'octobre**
1. Ouverture Colorplast : `scripts/reprise_colorplast_solde_ouverture.py --bascule 9` en
   simulation puis `--apply` (corrigé en 564c3253, test `test_reprise_colorplast_base_reduction.py`).
2. Rappels de maintien : corriger à la main la ligne de réduction d'octobre (M.G. 1 524,86 € ;
   S.G. 482,79 € ; D.J. 870,73 € ; D.S. 211,60 €), le cumul suit (`corrections_manuelles.py:760-779`).
3. Fiches de F.A. et X.P. : date de naissance, RIB, statut « Actif ».

**Avant janvier 2027** : rappel de maintien typé qui porte son SMIC (moteur, plan séparé) ;
barème par année (P2) ; bornes de collecte (P3) ; règle des cinq ans de l'effectif (F3).

**Avant la bascule de Mont-Blanc** : ouverture avec la base de Quadra (R3) ; import DSN (D4).

**Plus tard** : arrondi 018 / 106 (D2) ; docstring du coefficient (F1) ; test des heures
d'arrêt (P5).

**Questions à Gaëlle ou à Cegid** : aucune ; textes et données tranchent. Seule donnée absente
partout : les DSN de juillet à septembre de Quadra (sans effet sur Martine, l'ouverture
redonnant le cumul de Quadra).

## Tableaux du rejeu (agrégés, sans clé de salarié)

Impact : réduction cumulée de la colonne moins celle de la loi, sur les cumuls de Quadra
(positif = plus de réduction que la loi).

### colorplast

| Société | Pré-classement | Lignes | Impact Quadra (€) | Impact Quadra en valeur absolue (€) | Impact MARTINE (€) | Impact MARTINE en valeur absolue (€) |
|---|---|---|---|---|---|---|
| colorplast | a_juger_les_deux | 8 | -94.55 | 138.47 | 1736.90 | 1852.12 |
| colorplast | a_juger_quadra | 17 | -68.22 | 435.94 | 0.71 | 0.71 |
| colorplast | arrondi | 23 | 0.00 | 0.00 | 0.00 | 0.00 |
| colorplast | donnee_manquante | 5 | 0.00 | 0.00 | 0.00 | 0.00 |
| colorplast | erreur_eywai | 5 | 0.00 | 0.00 | 1042.39 | 1222.71 |
| colorplast | identique | 3 | 0.00 | 0.00 | 0.00 | 0.00 |

Classement final :

| Société | Classement final | Règle | Lignes | Impact Quadra (€) | Impact MARTINE (€) |
|---|---|---|---|---|---|
| colorplast | arrondi | R-H2 | 1 | -1.95 | 0.00 |
| colorplast | arrondi | R-H2, R-H3 | 2 | 5.91 | 0.00 |
| colorplast | donnee_manquante | R-A2 | 2 | 0.00 | 0.00 |
| colorplast | donnee_manquante | R-D1 | 8 | -188.50 | 270.01 |
| colorplast | donnee_manquante | R-H1 | 1 | 0.00 | -75.36 |
| colorplast | donnee_manquante | R-H2 | 1 | 0.00 | -14.80 |
| colorplast | donnee_manquante | R-H2, R-H7 | 1 | 1.95 | -56.30 |
| colorplast | donnee_manquante | R-H3, R-H7 | 1 | 0.00 | 37.10 |
| colorplast | donnee_manquante | R-H7 | 3 | 0.00 | 0.00 |
| colorplast | erreur_quadra | R-F2 | 8 | 71.74 | -1.31 |
| colorplast | methode_legale_differente | R-A3 | 1 | -26.62 | 898.02 |
| colorplast | methode_legale_differente | R-H3 (point n° 2) | 1 | -5.00 | 0.71 |
| colorplast | methode_legale_differente | R-H4 | 3 | 1.44 | 1422.62 |
| colorplast | methode_legale_differente | R-H4 (point n° 1) | 1 | 1.90 | 275.43 |
| colorplast | methode_legale_differente | R-H7 | 1 | -23.64 | 23.88 |

### comitech

| Société | Pré-classement | Lignes | Impact Quadra (€) | Impact Quadra en valeur absolue (€) | Impact MARTINE (€) | Impact MARTINE en valeur absolue (€) |
|---|---|---|---|---|---|---|
| comitech | a_juger_les_deux | 40 | -125.13 | 2369.83 | -8087.07 | 19706.73 |
| comitech | a_juger_quadra | 37 | 229.38 | 898.64 | 0.00 | 0.00 |
| comitech | arrondi | 56 | 0.00 | 0.00 | 1.20 | 1.20 |
| comitech | donnee_manquante | 9 | 0.00 | 0.00 | 0.00 | 0.00 |
| comitech | erreur_eywai | 15 | 0.83 | 0.83 | 1998.90 | 2602.72 |
| comitech | identique | 4 | 0.00 | 0.00 | 0.00 | 0.00 |

Classement final :

| Société | Classement final | Règle | Lignes | Impact Quadra (€) | Impact MARTINE (€) |
|---|---|---|---|---|---|
| comitech | donnee_manquante | R-A2 | 3 | 0.00 | 0.00 |
| comitech | donnee_manquante | R-D1 | 21 | -477.94 | -2180.18 |
| comitech | donnee_manquante | R-H1 | 1 | 0.00 | -150.70 |
| comitech | donnee_manquante | R-H2 | 7 | 20.85 | -7362.85 |
| comitech | donnee_manquante | R-H2, R-H3 | 4 | -0.28 | -514.38 |
| comitech | donnee_manquante | R-H2, R-H3, R-H6, R-H7 | 1 | 0.00 | -78.47 |
| comitech | donnee_manquante | R-H2, R-H3, R-H7 | 1 | -4.23 | 347.75 |
| comitech | donnee_manquante | R-H2, R-H9 | 2 | 0.00 | -7.76 |
| comitech | donnee_manquante | R-H3 | 2 | 0.83 | 181.58 |
| comitech | donnee_manquante | R-H7 | 3 | 0.00 | 0.00 |
| comitech | donnee_manquante | R-H7, R-H8 | 1 | 0.00 | 0.22 |
| comitech | donnee_manquante | R-H8 | 1 | 0.00 | -61.75 |
| comitech | donnee_manquante | R-H9 | 1 | 0.00 | -3.23 |
| comitech | erreur_quadra | R-F2 | 22 | 87.63 | -126.87 |
| comitech | erreur_quadra | R-H4 | 3 | 480.19 | 1492.58 |
| comitech | erreur_quadra | R-R2 | 15 | 27.98 | 0.00 |
| comitech | methode_legale_differente | R-B1 (point n° 12) | 3 | 198.93 | -1340.13 |
| comitech | methode_legale_differente | R-H3 (point n° 2) | 2 | -48.60 | 207.00 |
| comitech | methode_legale_differente | R-H4 | 4 | 0.00 | 1928.58 |
| comitech | methode_legale_differente | R-H4 (point n° 1) | 4 | -180.28 | 1580.44 |

### mbc

| Société | Pré-classement | Lignes | Impact Quadra (€) | Impact Quadra en valeur absolue (€) | Impact MARTINE (€) | Impact MARTINE en valeur absolue (€) |
|---|---|---|---|---|---|---|
| mbc | a_juger_les_deux | 12 | -208.33 | 690.01 | -549.21 | 1683.51 |
| mbc | a_juger_quadra | 112 | -299.40 | 5825.50 | 0.71 | 0.71 |
| mbc | arrondi | 48 | -0.10 | 0.10 | 1.75 | 1.75 |
| mbc | donnee_manquante | 12 | 0.00 | 0.00 | 0.00 | 0.00 |
| mbc | erreur_eywai | 26 | 0.00 | 0.00 | -89.55 | 3302.67 |
| mbc | identique | 311 | 0.22 | 0.22 | 0.00 | 0.00 |
| mbc | point_non_tranche | 13 | 0.00 | 0.00 | 0.00 | 0.00 |

Classement final :

| Société | Classement final | Règle | Lignes | Impact Quadra (€) | Impact MARTINE (€) |
|---|---|---|---|---|---|
| mbc | arrondi | R-H2, R-H3 | 2 | 0.00 | -0.86 |
| mbc | arrondi | R-H3 | 3 | 0.00 | 7.57 |
| mbc | arrondi | R-H3, R-H4 | 1 | -2.14 | 0.00 |
| mbc | donnee_manquante | R-A2 | 10 | 0.00 | 0.00 |
| mbc | donnee_manquante | R-D1 | 42 | -1846.45 | 345.49 |
| mbc | donnee_manquante | R-H1 | 1 | 0.00 | -220.32 |
| mbc | donnee_manquante | R-H2, R-H3 | 3 | 0.00 | 103.35 |
| mbc | donnee_manquante | R-H3 | 11 | 0.00 | 156.46 |
| mbc | donnee_manquante | R-H3, R-H6 | 1 | 0.00 | 90.57 |
| mbc | donnee_manquante | R-H4 | 3 | 0.00 | -248.27 |
| mbc | donnee_manquante | R-H7 | 1 | 0.00 | 0.00 |
| mbc | erreur_quadra | R-F2 | 61 | -3.22 | -288.52 |
| mbc | erreur_quadra | R-H1 | 6 | -244.87 | 0.00 |
| mbc | methode_legale_differente | R-A3 | 1 | -200.27 | 0.00 |
| mbc | methode_legale_differente | R-B1 (point n° 12) | 8 | 1783.61 | -276.52 |
| mbc | methode_legale_differente | R-H3 (point n° 2) | 2 | 132.19 | 87.37 |
| mbc | methode_legale_differente | R-H4 | 2 | 0.00 | 21.95 |
| mbc | methode_legale_differente | R-H4 (point n° 1) | 15 | -90.46 | 0.00 |
| mbc | methode_legale_differente | R-H7 | 2 | -36.12 | -416.32 |

