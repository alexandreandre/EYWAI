# Prompt — Convergence paie MBC mai 2026, catégorie par catégorie

Tu reprends le backtest de la paie **Mont Blanc Composite (MBC), mai 2026**. Objectif :
faire converger chaque bulletin EYWAI vers le réel Cegid **au centime (tier-S ≤ 0,05 €)**
sur brut / net imposable / MNS / net à payer / PAS.

## Lis d'abord la mémoire (3 notes)
`reconciliateur-backtest-paie`, `backtest-paie-mai-2026`, `backtest-forfait-jour-participation-bug`.
Elles contiennent l'historique, les bugs déjà corrigés, la cheat-sheet DSN et l'état.

## État de départ
**20/75 convergés.** Les 55 restants sont classés en 10 catégories (voir plus bas).

## Règles ABSOLUES
- **Un seul type de correction à la fois** (la catégorie que je te donne), puis vérifier, garder si mieux, **revert si pire**.
- **Après TOUT changement MOTEUR** (fichier dans `app/`) : régénérer + vérifier **Colorplast 7/7 ≤ 0,05 €** ET `pytest tests/unit/payroll -q` = **365 passed / 1 failed** (échec préexistant `test_non_cadre_temps_partiel`, sans lien). Les corrections purement DATA (calendrier, monthly_inputs, specificites_paie, mutuelle) n'ont pas ce risque.
- **Ne jamais commit sans demande explicite.**
- Commandes Python **toujours** en arrière-plan via `bash -c 'cd /Users/alex/Desktop/EYWAI/EYWAI/backend && .venv/bin/python -m ...'` (cwd = backend obligatoire, sinon échec).

## Outils (dans `backend/scripts/backtest/`)
- **Réconciliateur auto-vérifiant** : `python -m scripts.backtest.mbc_reconcile [MATRICULE ...]` — parse le bulletin réel, reconstruit la DB (monthly_inputs + specificites + calendrier + vide le pointage corrompu + HS/mutuelle/PAS/absences), régénère, compare, **garde si mieux / revert si pire**. Sans argument = tous les non-convergés.
- **Snapshot état** : `python -m scripts.backtest.mbc_state [--no-regen] [--company Colorplast] [MATRICULE ...]` — tier-S trié + détail par champ. `--no-regen` = lecture instantanée de la DB (pas de régénération).
- **Bulletins réels** : `Config/MBC/Compteur CP (bulletins de mai)/bulletins_md_2026-05/<MATRICULE>.md` (texte Cegid = source de vérité par salarié).
- **DSN** : `Config/MBC/DSN/000001_0526_000001 (1).dsn` (ISO-8859-1 ; `iconv -f ISO-8859-1 -t UTF-8`). Codes : `S21.G00.50.002`=net imposable, `.009`=PAS ; `S21.G00.58` type 03=MNS ; `S21.G00.60`=arrêt (dates) ; `S21.G00.81`=cotisations (base/montant/taux, code 059=PSC).
- **Drive MBC** (`~/Desktop/MBC/`) : `LES VARIABLES/05-2026 HS du mois + prime assiduité.xlsx` (feuilles **heures sup 05-2026** = ajustement HS/mois par salarié colonne « Majo 25% » ; **Acomptes** ; **Maintien suite IJSS** = règles CCN plasturgie) et `CALENDRIER 2026.xlsx`.

## Méthode par catégorie
Je te donnerai **un numéro de catégorie + la liste de matricules** concernés. Pour chacun :
1. Applique **uniquement** la correction propre à cette catégorie (voir ci-dessous).
2. Régénère + compare (`mbc_state`), garde si tier-S baisse, revert sinon.
3. Non-régression si moteur touché.
4. Rends-moi un tableau **avant → après** par salarié + ce qui reste.

## Les 10 catégories et leur correction « nécessaire et suffisante »

1. **Arrondi <1 €** (OSMANI, DULPHY) — irréductible, ne rien faire.
2. **HS du mois non importées** — appliquer l'ajustement HS mensuel du Drive (feuille « heures sup 05-2026 », colonne Majo 25% ; négatif = retirer des HS conjoncturelles). Cible brut.
3. **HS structurelles surévaluées** (brut +13-18, NI≈0) — recaler la quantité/taux des HS structurelles (10,83 h) sur la ligne exacte du bulletin.
4. **Acompte / net-only reliquat** — vérifier acompte salaire (« Acompte MM/AAAA », net-only, déjà géré par le moteur), prêt (SAVP/SAWx/SBUS), + date de reprise d'ancienneté si prime ancienneté manquante (MOHAMEDY).
5. **Participation / MNS** (résiduel MNS seul) — corriger le split participation **numéraire vs PEE** (+ CSG). Lire DSN `S21.G00.58` type 03 (MNS) et la ligne « Participation » du bulletin. Attention forfait-jour (payslip_run_forfait) vs heures.
6. **Trésorerie / net à payer seul** — importer les retenues nettes exactes du bulletin : saisie sur salaire, virement déjà effectué, participation avancée, prêt. Router en net-only.
7. **Arrêt maladie mois courant** (SERE, DALLACOSTA, MATHIEU, LAMOTTE, KIRMIZI) — poser les **jours arret_maladie** au calendrier (dates DSN `S21.G00.60`), config `company_maintenance_settings` (déjà faite, CCN plasturgie), et **IJSS = absence_100% − maintien_bulletin** (back-calcul) injectée via `ijss_brut_override` sur le jour d'arrêt. Base journalière du maintien = salaire journalier réel jours ouvrés (fix moteur `_salaire_journalier_maintien` en cours). Sans maintien si ancienneté insuffisante.
8. **Arrêt maladie cross-mois** (OSMANI2, SAFI2, BABA) — **BLOQUÉ** : nécessite les bulletins/cumuls **avril 2026 (M-1)** + le « Rappel Maintien de salaire 04/26 ». Ne pas traiter sans ces données.
9. **Temps partiel / template planning** (LIKA Rina, RABBENI, POULAIN, CHEVALLIER) — corriger la **durée hebdo réelle + le planning réel** du contrat (template temps plein appliqué à tort).
10. **Cas individuels** (ADAMYOUSSE = élément taxable non-social manquant ; GAUDEY = jours forfait/RTT ; FAIZI = +1 h HS Drive ; KHENE/ASKARI/IBRAHIMA = prime/HS à recaler sur bulletin).

Dis-moi juste : « **Catégorie N** : MATRICULE1, MATRICULE2, … » et je traite.
