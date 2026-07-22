# Loader DSN → calendriers Colorplast (backtest paie jan-juin 2026)

- **Date** : 2026-07-21
- **Statut** : design validé (brainstorming), à implémenter
- **Auteur** : Alexandre + Claude

## Contexte & problème

Le backtest paie s'appuyait jusqu'ici sur des scripts (`colorplast_setup.py`,
`*_reconcile.py`) qui **rétro-injectaient** les événements de paie (HS, absences,
primes) lus **dans les bulletins Cegid cibles**. Conséquence : la convergence était
en partie « fabriquée » — on donnait à EYWAI la réponse, puis on vérifiait qu'il la
reproduisait. Ce n'est pas une validation indépendante de la chaîne de données.

De plus, `colorplast_setup.py` **vide le pointage réel** (`actual_hours`) et code en
dur les heures/absences (`MONTH_DATA`), tapées à la main depuis les bulletins.

## Objectif

Peupler les calendriers / inputs de paie Colorplast (jan-juin 2026) à partir de la
**DSN** (déclaration sociale nominative = données déclarées réelles, source distincte
du bulletin), pour que le backtest teste réellement : *données réelles → moteur EYWAI
→ bulletin*, comparé au bulletin Cegid.

## Décisions (brainstorming)

1. **Source primaire = DSN** (jan-mai), **pointages manuscrits = contrôle** (et source
   pour juin, qui n'a pas de DSN). La DSN est structurée, fiable, et porte les heures.
   Caveat assumé : la DSN est Cegid-dérivée (semi-circulaire) mais reste distincte du
   bulletin ; c'est un bon compromis fiabilité/légitimité/rapidité.
2. **Architecture = loader dédié** (script `scripts/backtest/dsn_calendar_loader.py`),
   pas d'extension de l'import DSN de production (évite le risque de conflit/écrasement
   sur l'existant). Générique (paramètre entreprise) → rejouable sur CARTOL ensuite.

## Ce que la DSN fournit (vérifié sur Colorplast mai)

Par salarié × mois :

| Donnée | Emplacement DSN | Exemple mai |
|---|---|---|
| Quotité contrat (169 h = 39 h/sem) | `S21.G00.40.013` | 169.00 |
| HS structurelles (17,33 h) | rému `S21.G00.51.011=018` | 17,33 h (tous) |
| **HS conjoncturelles** | rému `011=017`, heures `.012`, montant `.013` | ESPINOSA 9,50 h / 211,36 € |
| **Absences / arrêts** | bloc `S21.G00.60` (motif `.001`, dates début/fin) + activité `S21.G00.53` nat 02 | FUCKAR maladie dès 08/05 |
| Base mensualisée | rému `011=002` | (déjà dans `salaire_de_base`) |

- **HS structurelles (17,33 h)** : gérées par le contrat 39 h dans EYWAI → **ne pas
  réinjecter**.
- **Taux 25/50 des HS conjoncturelles** : déduit du **montant ÷ heures** (base×1,25 vs
  base×1,50). Recoupé aux pointages hebdo si une ligne mélange les taux.

## Extraction (loader)

Pour chaque salarié × mois (jan-mai) :
1. Parser les blocs individu (`S21.G00.30`), contrat (`40`), rémunération (`51`),
   activité (`53`), arrêt (`60`).
2. Produire un enregistrement normalisé : `{matricule, mois, hs_25_h, hs_50_h,
   absences:[{date_debut, date_fin, motif, type}]}`.
3. Mapper les motifs d'arrêt DSN (`60.001`) → type EYWAI (01=maladie → `arret_maladie`
   + maintien/IJSS ; autres → à cartographier).

## Écriture (loader → DB)

Isolée, **idempotente**, marqueur `DSN_LOADER` :
- HS conjoncturelles → `monthly_inputs` (`payroll_quantity` = heures ; lignes 25 % et
  50 % séparées).
- Absences → jours précis du `planned_calendar` (type selon motif). Arrêts maladie :
  déclenchent le moteur maintien (cf. mémoire arrêts/maintien).
- **Ne pas** vider `actual_hours` sans raison, **ne pas** injecter depuis les bulletins.
- Purge des lignes `DSN_LOADER` avant réinsertion.

## Juin (pas de DSN)

Lecture des pointages `SEMAINE 22-25` (manuscrits, scannés) → heures/jour → mêmes
sorties. Validation renforcée contre le bulletin (seule ancre pour juin).

## Validation (obligatoire, « bien fait »)

1. Après chargement d'un mois : régénérer les bulletins → comparer au bulletin réel
   (tier-S ≤ 0,05 € par salarié).
2. Recouper les HS/absences DSN contre les **pointages manuscrits** (contrôle
   indépendant : est-ce que la lecture du pointage corrobore la DSN ?).
3. Documenter tout écart résiduel (calcul / donnée / conformité), sans masquer.

## Sécurité

- **Backup** de l'état DB Colorplast (employees/schedules/monthly_inputs) avant toute
  mutation, restaurable.
- Un seul mois à la fois, en avant-plan, vérifié avant de passer au suivant (pas de
  bulk aveugle). Travail en session directe (pas de sous-agent — risque DB).

## Hors périmètre

- Extension de l'import DSN de production (suivi éventuel).
- OCR automatisé des pointages (lecture assistée à la main, cross-check DSN).
- Autres entreprises (le loader est générique mais on valide d'abord Colorplast).

## Détails à trancher en implémentation (avec contrôle bulletin/pointage)

- Cartographie complète des motifs d'arrêt DSN `60.001`.
- Cas où une ligne HS `017` mélange 25 % et 50 % (split via montant/heures + pointage).
- Traitement maintien/IJSS des arrêts maladie de mai (FUCKAR, DASILVA).
- Semaines à cheval sur deux mois (S05, S09, S13…) : rattachement au bon mois.
