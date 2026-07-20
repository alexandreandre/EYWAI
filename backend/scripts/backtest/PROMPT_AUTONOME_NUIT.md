# MISSION AUTONOME — Convergence paie MBC mai 2026, puis Lewis mai 2026

## LANCEUR (à coller dans une nouvelle session, en mode « bypass permissions »)
```
/loop Lis et exécute INTÉGRALEMENT backend/scripts/backtest/PROMPT_AUTONOME_NUIT.md. Autonomie totale, aucune question. À chaque réveil : commence par `cd backend && .venv/bin/python -m scripts.backtest.mbc_state --no-regen` pour voir l'état courant et REPRENDS là où tu en es (ne retouche pas les salariés déjà convergés ≤0,05€). Continue MBC mai 2026 jusqu'au max atteignable, puis Lewis mai 2026. Journalise dans backend/scripts/backtest/JOURNAL_NUIT.md. Quand il ne reste que des blocages documentés (données M-1 / contrats manquants), arrête la boucle (ScheduleWakeup stop).
```
`/loop` sans intervalle = auto-cadencé : l'agent travaille en continu et ne se ré-arme que s'il
s'interrompt (résilience). **Règle de reprise** : chaque itération lit l'état courant en premier et
poursuit sur les résiduels — elle ne recommence JAMAIS de zéro.

---

Tu es un agent **autonome**. Tu travailles **sans jamais me poser de question** : tu décides
toi-même, tu appliques, tu vérifies, tu corriges. Tu ne t'arrêtes que quand TOUT est convergé
ou réellement bloqué (données externes manquantes, documenté). Tu tournes toute la nuit.

## Objectif
Faire converger chaque bulletin EYWAI vers le réel Cegid **au centime (tier-S ≤ 0,05 €)** sur
brut / net imposable / MNS / net à payer / PAS, pour **Mont Blanc Composite (MBC) mai 2026**,
puis **Lewis mai 2026**.

## AVANT TOUT — lis la mémoire
Lis les 3 notes : `reconciliateur-backtest-paie`, `backtest-paie-mai-2026`,
`backtest-forfait-jour-participation-bug`. Elles contiennent l'historique, les bugs déjà
corrigés, la cheat-sheet DSN, l'état, et le **diagnostic complet du maintien maladie**.

## Règles ABSOLUES (non négociables)
1. **Discipline revert-safe** : une correction à la fois → régénère → compare → **garde si le
   tier-S baisse, REVERT si ça monte ou stagne**. Ne laisse jamais un salarié pire qu'avant.
2. **Non-régression après TOUT changement dans `app/` (moteur)** :
   - `pytest tests/unit/payroll -q` doit rester **365 passed / 1 failed** (échec préexistant
     `test_non_cadre_temps_partiel`, sans lien). Si un test que TU casses est légitime (tu as
     changé une formule correcte), recalcule et mets à jour l'assertion — sinon revert.
   - **Colorplast doit rester 7/7 ≤ 0,05 €** : `python -m scripts.backtest.mbc_state --company Colorplast`.
   Les corrections **DATA** (calendrier, monthly_inputs, specificites_paie, mutuelle) n'ont pas
   ce risque → pas besoin de repasser Colorplast/pytest pour elles.
3. **Ne commit JAMAIS** (sauf si je le demande explicitement — je ne le ferai pas cette nuit).
4. **Toujours** exécuter le Python en arrière-plan via
   `bash -c 'cd /Users/alex/Desktop/EYWAI/EYWAI/backend && .venv/bin/python -m ...'`
   (cwd = backend obligatoire ; sinon `.venv/bin/python: not found`).
5. **Journalise** ta progression dans `backend/scripts/backtest/JOURNAL_NUIT.md` (append) :
   après chaque catégorie, un tableau avant→après + ce qui reste. Comme ça je lis au réveil.

## Outils
- `python -m scripts.backtest.mbc_reconcile [MATRICULE ...]` — parse le bulletin réel, reconstruit
  la DB (monthly_inputs purge+rebuild, specificites, mutuelle famille, HS structurelles, taux PAS,
  ancienneté, CP/JTC/absences, vide le pointage corrompu), régénère, compare, **garde/revert auto**.
- `python -m scripts.backtest.mbc_state [--no-regen] [--company X] [MATRICULE ...]` — snapshot
  tier-S trié + détail par champ. `--no-regen` = lecture DB instantanée.
- `python -m scripts.backtest.psc_apply MATRICULE ...` — pose la mutuelle famille (net_imposable).
- Bulletins réels : `Config/MBC/Compteur CP (bulletins de mai)/bulletins_md_2026-05/<MAT>.md`.
- DSN : `Config/MBC/DSN/000001_0526_000001 (1).dsn` (ISO-8859-1 → `iconv -f ISO-8859-1 -t UTF-8`).
  Codes : `50.002`=NI, `50.009`=PAS, `58` type 03=MNS, `60`=arrêt(dates), `81`=cotis (059=PSC).
- Drive : `~/Desktop/MBC/LES VARIABLES/05-2026 HS du mois + prime assiduité.xlsx`
  (feuille `heures sup 05-2026` col « Majo 25% » = ajustement HS/mois ; `Acomptes` ; `Maintien suite IJSS`).
- Le réconciliateur est spécifique MBC (regex GAN, COMPANY hardcodé). Pour Lewis, voir la fin.

## État de départ : **20/75 convergés MBC** (arbre propre).

## ALGORITHME — traite les catégories dans CET ordre (data d'abord, moteur ensuite)

Pour chaque catégorie : traite tous ses salariés, régénère, vérifie convergence, revert si pire,
journalise. Puis passe à la suivante.

### Vague 1 — DATA disponible, faible risque, fort rendement
**Cat 2 — HS du mois (Drive)** : MOHAMED −0,25 h, FOFANA −0,5 h, DAWRAN −0,75 h, REMINI −1 h,
OZEN −6,5 h, BARRY −8,25 h, AVAHOUIN2 −10,5 h, BEHIRY −0,5 h, SCHARFF −0,75 h, GUELAI −0,25 h,
FAIZI +1 h (cat 10). → applique l'ajustement HS conjoncturelles (négatif=retirer) via monthly_inputs
`heures_supplementaires_conjoncturelles` ou le canal HS. Vérifie que le brut baisse du bon montant.

**Cat 6 — trésorerie / net à payer seul** : OVIE (−492), GOISSAUD (+513), TULEKI (+564),
LUSUMBU (−89), ZZSORTI113 (−76 = salarié SORTI, solde de tout compte). → lis le bulletin, importe
la retenue nette exacte (saisie, virement déjà versé, prêt, participation avancée) en net-only
(le moteur route « acompte »/« saisie »/« virement salaire » via `_is_net_a_payer_only_correction_input`).

**Cat 4 — acompte/net-only reliquat** : AWAD (−18), SACALA (−18), MOHAMEDY (ancienneté : saisis la
date de reprise d'ancienneté depuis le bulletin → prime ancienneté).

**Cat 10 — individuels** : FAIZI (+1 h HS), KHENE (~3,5 h prime/HS manquante), ASKARI (prime taxable
~11 € en trop), IBRAHIMA (prime taxable + petit NI), ADAMYOUSSE (élément taxable non-social au NI),
GAUDEY (jours forfait/RTT réels). → lis le bulletin, recale l'élément exact.

### Vague 2 — recalage fin sur bulletin
**Cat 3 — HS structurelles surévaluées** (brut +13-18, NI≈0) : SOUCHEYRE, SULPICE, CVITKOVIC,
BOUSSANOR, FANOVO. → compare la ligne « H. supp majorées à 25 % » (quantité 10,83 h × taux) du
bulletin à ce que calcule EYWAI ; recale la quantité/taux (specificites ou salaire de base).

### Vague 3 — MOTEUR (prudent, non-régression à chaque étape)
**Cat 5 — participation / MNS** : GILLET (+77), GUELAI (−97), SALAUN (−321), PORRAL (+74),
BOUVIERP (+22), MIRZADA2 (+12), BLONDEAU/DROZ/LABBE/DEPONGE/BORDELIER (forfait). → le split
participation numéraire vs PEE (et sa CSG) n'est pas exact. Lis DSN `S21.G00.58` type 03 (MNS) et
la ligne « Participation » du bulletin. Corrige le montant PEE vs numéraire dans monthly_inputs
(`_is_participation_pee_input` / `_is_participation_numeraire_input`). Attention forfait-jour
(`payslip_run_forfait.py`) vs heures.

**Cat 7 — arrêt maladie mois courant** : SERE, DALLACOSTA, MATHIEU, LAMOTTE, KIRMIZI.
- DALLACOSTA (arrêt 01-07/05) et MATHIEU (11-31/05) : **sans maintien** → pose juste les jours
  `arret_maladie` au calendrier (jours OUVRÉS uniquement) → l'absence se déduit → converge.
- SERE : IJSS = absence(442,36) − maintien_bulletin(361,39) = **80,97 €**. Implémente le fix moteur
  du maintien décrit dans la mémoire (`_salaire_journalier_maintien` = taux réel × 7 jours ouvrés,
  au lieu de `salaire_mensuel/30,42`) + injecte `ijss_brut_override` (déjà supporté l.943/l.548).
  ⚠ Recalcule l'assertion `test_maintien_corrections.py:272`. Vérifie Colorplast 7/7 + 4 tests maintien.
- LAMOTTE : arrêt quasi complet + saisis le **taux PAS 8,7 %**. KIRMIZI : −1 h HS + arrêt partiel.

### Ne PAS traiter (bloqué, documente juste)
**Cat 8 — cross-mois** : OSMANI2, SAFI2, BABA → nécessitent le bulletin **avril 2026 (M-1)** que tu
n'as pas. Documente et passe.
**Cat 9 — contrats temps partiel** : LIKA (Rina), RABBENI, POULAIN, CHEVALLIER → nécessitent la durée
hebdo + planning réels. Tente de les déduire du bulletin ; si impossible, documente et passe.
**Cat 1 — arrondi <1 €** : OSMANI, DULPHY → irréductible, ne touche pas.

## Quand toutes les catégories sont passées
1. **État des lieux complet** : `python -m scripts.backtest.mbc_state` (régénération totale) →
   compte les convergés, liste les résiduels par champ.
2. **Si des salariés ne convergent pas** et que la donnée existe (bulletin/DSN/Drive) : **reconçois
   un plan intelligent** (identifie la cause racine commune, préfère un fix systémique data ou un
   petit fix moteur non-régressif), **applique-le seul**, revérifie. Répète jusqu'à ce qu'il ne
   reste que des blocages réels (M-1, contrats manquants).
3. Journalise l'état final MBC.

## Puis : Lewis mai 2026
Quand MBC est au maximum atteignable (tous convergés sauf blocages documentés) :
- Données : `Config/Lewis/` (bulletins md + DSN, même structure que MBC) ET `~/Desktop/Lewis/`
  (Drive : variables, calendrier, acomptes…).
- **Le réconciliateur `mbc_reconcile.py` est spécifique MBC.** Pour Lewis, invoque le skill
  **`/backtest-paie-auto`** (backtest autonome de bout en bout pour une entreprise/mois donnés) :
  « fais le backtest paie complet et automatique de Lewis pour mai 2026 ». Ce skill compare tous les
  bulletins, diagnostique via DSN, corrige (data puis moteur non-régressif), boucle jusqu'à
  convergence, documente. Applique-lui la même discipline (revert-safe, non-régression Colorplast/pytest).
- Réutilise les patterns MBC déjà connus (mutuelle isolé/famille, HS structurelles, acompte
  net-only, absences fantômes pointage corrompu, participation PEE) — ils se reproduisent souvent.

## Rappels de sécurité
- Ne casse jamais Colorplast (7/7) ni pytest (365/1). En cas de doute sur un changement moteur : revert.
- Mets à jour la mémoire (`reconciliateur-backtest-paie`) avec les nouveaux fixes systémiques trouvés.
- Si vraiment bloqué sur toute une catégorie faute de données, documente précisément CE QUI MANQUE
  et continue avec le reste — ne t'arrête pas.
