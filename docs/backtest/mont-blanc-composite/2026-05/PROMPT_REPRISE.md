# Prompt de reprise — Convergence paie MBC mai 2026

## Objectif
Faire converger **tous les bulletins de paie Mont Blanc Composite (MBC) mai 2026** vers la paie réelle Cegid, au centime (**tier-S ≤ 0,05 €** sur brut / net imposable / MNS / net à payer / PAS). Les changements MOTEUR sont autorisés **à condition de vérifier la non-régression après chaque changement** : Colorplast doit rester 7/7 ≤ 0,02 € et `pytest tests/unit/payroll -q` doit rester 365 passed / 1 failed (échec préexistant `test_non_cadre_temps_partiel`, sans lien). Ne jamais commit sans demande explicite.

## Lis d'abord la mémoire
Trois notes de mémoire contiennent tout l'historique et les patterns :
- `reconciliateur-backtest-paie` — l'outil + les 8 bugs systématiques déjà corrigés
- `backtest-forfait-jour-participation-bug` — bug forfait-jour participation
- `backtest-paie-mai-2026` — cheat-sheet DSN (codes S21.G00.xx), écarts récurrents

## État actuel (départ = 1 convergé)
**11 convergés (≤0,05 €), ~26 à <20 €, sur 75 salariés.** Colorplast 7/7 intact.

## Outils et données disponibles
- **Réconciliateur auto-vérifiant** : `backend/scripts/backtest/mbc_reconcile.py` — parse le bulletin réel, reconstruit la DB, régénère, compare, **revert auto si pire**. Usage : `bash -c 'cd /Users/alex/Desktop/EYWAI/EYWAI/backend && .venv/bin/python -m scripts.backtest.mbc_reconcile [MATRICULE...]'` (en arrière-plan, cwd = backend obligatoire).
- **Bulletins réels (.md)** : `Config/MBC/Compteur CP (bulletins de mai)/bulletins_md_2026-05/<MATRICULE>.md` (texte brut Cegid = source de vérité par salarié).
- **DSN** : `Config/MBC/DSN/000001_0526_000001*.dsn` (ISO-8859-1 ; IJSS = code S21.G00.60 ; net imposable S21.G00.50.002 ; MNS type 03).
- **Drive MBC** (données SOURCES) : `~/Desktop/MBC/`
  - `CALENDRIER 2026.xlsx` — 1 onglet par salarié, colonnes par mois [jour, n°, H.Abs (texte fériés/annotations), CP]. MAI = colonne ~16. Planning + CP + annotations (« carence non payé »), PAS des heures propres jour par jour.
  - `LES VARIABLES/05-2026 HS du mois + prime assiduité.xlsx` : feuilles **Acomptes** (montants exacts : BOUVIER 300, GOISSAUD 500, REMINI 400, AWAD 300, AVAHOIN 400, MOHAMED YOUSSEF 300), **Maintien suite IJSS** (RÈGLES CCN plasturgie par catégorie/ancienneté), **heures sup 05-2026** (HS par salarié/semaine).
- **Comparaison** : `compare_matches` (lecture, pas de régénération) et `_generate_payslip(match, 2026, 5)` depuis `scripts.backtest.backtest_company_payroll`.

## Ce qui a déjà été fait (8 bugs systématiques, tous vérifiés non-régression)
1. Réconciliateur auto-vérifiant construit
2. Mutuelle « Isolé » = 100 % employeur (salarial 0 / patronal 46,86), pas 46,86/46,86
3. `salaire_hors_hs_structurelles` manquant (base 151,67 h + HS en sus)
4. « Prime panier soumises » mal taguée non-taxée
5. **Prime d'ancienneté cadre forfait-jour** supprimée — `calcul_brut_forfait.py` `_calculer_prime_anciennete` gate sur `is_cadre` (CCN plasturgie = non-cadres)
6. **Cantine = retenue nette** — `payslip_generator.py` `_is_net_a_payer_only_correction_input` inclut « cantine »
7. **Flag `is_forfait_jour` inversé** — GAUDEY/DEPONGE/SALAUN sont à l'HEURE (pas de « Forfait annuel » au bulletin), mis à False
8. **« Rbst note de frais » hors MNS** — `_is_frais_pro_non_soumis_input` (mais « Remboursement de notes de frais » BUGNY Colorplast RESTE dans le MNS via exclusion « remboursement de note »)

Config posée : `company_maintenance_settings` de MBC upsert avec `remove_employer_waiting=True, maintain_100_percent=True, apply_legal_maintenance=True` (CCN plasturgie).

## LA DÉCOUVERTE CLÉ (à exploiter)
**L'arrêt maladie est de la CONFIGURATION, pas du code.** Le moteur a déjà toute la machinerie (`maintien_salaire_service.py`). Il suffit de :
1. Peupler les jours `arret_maladie` dans `employee_schedules.planned_calendar.calendrier_prevu` + `actual_hours.calendrier_reel` (structure : `{"jour":N,"type":"arret_maladie","heures_prevues":0,"arret_type":"maladie_simple","subrogation_active":True}`)
2. Config `maintenance_settings` (déjà faite)
→ Testé sur SERE : **149 → 85,69 €**, la ligne « Maintien de salaire employeur » apparaît.

## Les 3 chantiers restants (précisément diagnostiqués)

### Chantier 1 — Méthodologie du maintien (calibration vs Cegid)
Sur SERE, il reste 85,69 € : `maintien_salaire_service.py` ligne ~526-529 calcule `brut_journalier = salaire_base_mensuel / DIVISEUR_JOURS_CALENDAIRES` (jours calendaires /30) et `nb_jours_maintien` en jours calendaires. **Cegid calcule sur les jours OUVRÉS au taux horaire réel** (SERE : maintien réel 361,39 € = 3 jours × ~120,46 €/j ouvré, vs EYWAI maintien_cible 315,08 = 78,77 × 4 jours calendaires ; 78,77 = base IJSS plafonnée). Il faut aligner la base et le décompte du maintien sur la méthode Cegid (jours ouvrés, salaire réel base+HS, pas la base IJSS plafonnée). ⚠️ Touche le maintien de TOUS les clients → vérifier Colorplast (aucun arrêt maladie chez Colorplast a priori, à confirmer) + pytest. Utiliser les RÈGLES exactes de la feuille « Maintien suite IJSS » du Drive.

### Chantier 2 — Déductions fantômes CP/JTC (cluster brut −400)
AWAD/SPIGA/LUSUMBU/BOUSSANOR ont brut −340 à −470 : leur bulletin réel n'a AUCUNE absence, mais le réconciliateur a posé des jours CP/JTC dans le calendrier qui **sur-déduisent** (déduction cachée ~565 € pour AWAD ; l'indemnité CP ne compense pas la retenue, et/ou `actual_hours` incohérent proratise la base). Diagnostiquer : l'indemnité congés payés du moteur (`calcul_brut.py` / `calcul_conges.py`) doit exactement compenser la retenue (net ≈ 0) pour un CP payé ; sinon corriger. Vérifier aussi que les jours JTC (marqués `absence_justifiee` par le réconciliateur) ne déduisent pas (JTC = jour de repos PAYÉ).

### Chantier 3 — `hors_hs_structurelles` à généraliser
La détection dans `mbc_reconcile.py` (`_HS_STRUCT_RE`) ne matche que « H. supp majorées à 25 % 10.8x » → rate les contrats à autre volume d'HS structurelles (BOUSSANOR 7,24 h, etc.). Élargir : poser `salaire_hors_hs_structurelles=True` dès que la base config = le montant « SALAIRE DE BASE » du bulletin (151,67 h × taux) ET qu'il y a une ligne HS structurelle. Testé : BOUSSANOR −470 → −342 avec le flag.

## Bonus data Drive (gains propres)
- **Acomptes** (6 salariés) : ajouter comme retenues nettes (`_is_net_a_payer_only_correction_input` matche déjà « acompte » ? sinon router en net-only). Attention : ces salariés ont aussi des résiduels MNS (participation) → l'acompte seul ne convergera pas leur tier-S mais rapproche le net.

## Méthode / discipline
- **Un salarié (ou micro-batch de cause identique) à la fois**, régénérer, comparer, garder si mieux, **revert si pire** (le réconciliateur le fait ; en manuel, snapshotter avant).
- **Après tout changement MOTEUR** : régénérer + comparer Colorplast (7/7 ≤ 0,02) ET `pytest tests/unit/payroll -q` (365/366).
- Commandes Python **toujours** via `bash -c 'cd /Users/alex/Desktop/EYWAI/EYWAI/backend && .venv/bin/python ...'` en arrière-plan (sinon échec cwd / timeout 2 min).
- Point d'étape à l'utilisateur tous les ~10 salariés traités, avec tableau tier-S avant/après.
- Ordre recommandé : Chantier 3 (le plus propre, plusieurs salariés) → Chantier 1 (arrêt maladie, gros €, config + calibration maintien) → Chantier 2 (déductions fantômes) → finition + re-passage réconciliateur complet.

## Cas cross-mois (à traiter en dernier, plus durs)
OSMANI2/SAFI2/BABA ont des rappels maintien d'avril (« Rappel Maintien de salaire de 04/26 à 04/26 »). Le montant exact est dans le bulletin → l'injecter comme régularisation brut taxée une fois la mécanique maintien du mois courant calibrée.

## Objectif de sortie
Viser 40-60+ convergés. Documenter tout résiduel restant par catégorie. Mettre à jour la mémoire (`reconciliateur-backtest-paie`) avec les nouveaux fixes.
