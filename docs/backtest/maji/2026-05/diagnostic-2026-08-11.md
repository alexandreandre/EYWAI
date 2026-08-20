# Backtest MAJI 05/2026 — diagnostic d'entrée (11/08/2026)

Première mesure : **0/10 salariés convergés**, aucune correction appliquée
volontairement (la session s'est arrêtée sur le garde-fou d'écriture en base).
Ce document sert de point de départ à la session suivante — il évite de
refaire le cadrage et les mesures.

## Cadrage

- 13 fiches en base, 3 salariés partis (BARBERET, JOLLY, PELLET), **10 actifs**,
  exactement les 10 bulletins du cabinet. Appariement : 10/10, aucun orphelin.
- Références lisibles déjà générées :
  `data/maji/bulletins/2026-05/md/<MATRICULE>.md` (+ README récapitulatif).
- DSN cabinet de janvier à juin dans `data/maji/dsn/`.
- `Config/Maji/` créé en **symlinks** vers `data/maji/` (`Compteur CP
  (bulletins de mai)` → `bulletins/2026-05`, `DSN` → `dsn`) : les outils de
  backtest attendent l'ancienne arborescence, `Config/` est gitignoré.

## Écart par salarié (tier S, avant toute correction)

| Matricule | tier S max | Nature dominante |
|---|---|---|
| BLA | 21,96 € | taux horaire et heures d'un temps très partiel |
| SMITH | 66,48 € | brut d'un entrant du mois (04/05) |
| BOULAY | 160,06 € | absences non reprises (2 JF non payés, 1 congé sans solde) |
| BOUALI | 174,07 € | net à payer seul faux — élément net-only manquant |
| FERCHAUT | 245,49 € | idem BOUALI (MNS à 4 € près, net à payer à 245 €) |
| VERNYC | 262,65 € | idem — MNS quasi juste, net à payer très faux |
| HART | 378,78 € | brut trop élevé de 378,78 € (entrant du 07/04) |
| ANDRE | 516,88 € | net à payer seul faux (MNS à 50 €) |
| VIRTH | 1 400,00 € | brut inférieur de 1 400 € — élément de rémunération absent |
| AMATE | 1 884,32 € | brut inférieur de 1 600 € — idem |

## Trois familles, pas dix problèmes

1. **Net à payer seul faux, MNS presque juste** (BOUALI, FERCHAUT, VERNYC,
   ANDRE) : signature classique d'un élément **net-only** manquant — panier,
   indemnité forfaitaire ou remboursement (catalogue n° 16/24 du skill). Les
   écarts (174 / 245 / 263 / 508 €) sont à confronter aux lignes non soumises
   des bulletins md. **C'est le lot le plus rentable : une cause, 4 salariés.**
2. **Brut faux d'un montant rond** (AMATE −1 600 €, VIRTH −1 400 €, HART
   +378,78 €) : élément de rémunération permanent absent ou en trop
   (prime mensuelle, part variable). Montants ronds ⇒ ligne entière, pas un
   arrondi.
3. **Petits cas** : BLA (le cabinet compte 16 h à 15,00 € pile ; nous 14,54 h à
   14,9957 € — la fiche porte 525 €/8,08 h, qui ne donne pas un taux rond :
   **520 €/8 h donne exactement 15,00 €**, correction permanente à faire),
   SMITH et BOULAY (entrants du mois et absences non reprises : 2 « Abs. JF non
   payé » les 08 et 14/05, 1 « Abs. congés s. solde » le 25/05 chez BOULAY,
   toutes visibles sur son bulletin).

## Signaux transverses relevés

- `paie_jour_de_fin = 31` chez MAJI : c'est la valeur invalide du bug n° 15 du
  catalogue, mais le repli calendaire fonctionne (les bulletins se génèrent).
  Rien à corriger, à ne pas re-diagnostiquer.
- « Aucune branche de calcul de prévoyance n'a été exécutée » sur plusieurs
  salariés, alors que les bulletins portent une ligne `EPRD PREVOYANCE NC
  APICIL TA` (0,375 % / 0,375 %) — **prévoyance non paramétrée** sur ces
  fiches (`specificites_paie.prevoyance.adhesion = false` chez BLA).
- L'orchestrateur automatique plante sur MAJI : `remediation._snapshot_employee`
  suppose un `employee_schedules` existant et déréférence `None`. Il a écrit
  3 `set_classification` et 3 `align_pointage_planning` avant de tomber. À
  corriger (ou à contourner en travaillant salarié par salarié, ce que la
  méthode recommande de toute façon).

## Écriture faite en base (prod) pendant la session

- **BLA** : création d'un `employee_schedules` mai 2026 (8 jours × 2 h, source
  `reprise_backtest_2026-08-11`). Sans effet mesuré sur son bulletin — le brut
  reste mensualisé. À supprimer si l'on préfère repartir d'une fiche vierge.

## Ce qui bloque

Les écritures en base sont refusées par le garde-fou de permissions de la
session (`employees.update`). Le backtest travaille sur la **base de
production** (`backend/.env`) : reprendre en session interactive, ou après
avoir autorisé explicitement ces écritures.
