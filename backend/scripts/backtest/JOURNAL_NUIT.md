# Journal nuit — Convergence paie MBC mai 2026 puis Lewis

Agent autonome. Discipline revert-safe. Ne commit jamais. Objectif tier-S ≤ 0,05 €.

## État de départ (réveil 1, 2026-07-08)
- MBC : **23/75 convergés** (baseline prompt = 20 ; le travail cat-2 session 08/07 — REMINI, MOHAMED, BEHIRY — est déjà en DB).
- Pas de journal préexistant → je le crée.
- Découverte : une **DSN avril** existe (`Config/MBC/DSN/000001_0426_000001 (3).dsn`) → pourrait débloquer partiellement les cross-mois (OSMANI2, SAFI2, BABA, SCHARFF) que le prompt classait « bloqués M-1 ».

### Résiduels non convergés au départ (52), par catégorie prévue
- Cat 1 arrondi irréductible (NE PAS TOUCHER) : OSMANI 0,67 ; DULPHY 0,77.
- Cat 2 HS/absences frac. (déjà à l'optimum reconciler) : DAWRAN 0,14 ; FOFANA 0,15 ; OZEN 51,55 ; BARRY 55,76 ; AVAHOUIN2 38,07.
- Cat 3 HS structurelles : SOUCHEYRE 13,68 ; SULPICE 14,05 ; CVITKOVIC 14,95 ; BOUSSANOR 14,98 ; FANOVO 17,43.
- Cat 4 acompte/ancienneté : SACALA 18,00 ; AWAD 18,01 ; MOHAMEDY 51,40.
- Cat 5 participation/MNS : BLONDEAU 4,45 ; GAILLET 4,90 ; MIRZADA2 11,73 ; BOUVIERP 21,94 ; PORRAL 74,16 ; GILLET 77,15 ; GUELAI 97,07 ; SALAUN 321,43 ; + forfait DROZ 14,11/LABBE 27,02/BORDELIER 40,55/DEPONGE 43,43.
- Cat 6 trésorerie net-only : LUSUMBU 89,63 ; ZZSORTI113 76,37 ; OVIE 492,04 ; GOISSAUD 513,16 ; TULEKI 564,18.
- Cat 7 arrêt maladie : SERE 85,69 ; KIRMIZI 91,65 ; DALLACOSTA 537,66 ; LAMOTTE 916,53 ; MATHIEU 952,81.
- Cat 8 cross-mois : SCHARFF 126,08 ; OSMANI2 831,09 ; SAFI2 1868,97 ; BABA 2650,33.
- Cat 9 temps partiel : POULAIN 194,50 ; CHEVALLIER 497,46 ; LIKA 801,84 ; RABBENI 1222,78.
- Cat 10 individuels : ASKARI 11,50 ; FAIZI 16,94 ; IBRAHIMA 27,26 ; KHENE 48,86 ; ADAMYOUSSE 191,00 ; GAUDEY 212,60 ; MIRZADA 3,51.

Plan : data d'abord (cat 6, cat 7 sans-maintien, cat 5, cat 3, cat 10), puis moteur (maintien maladie), puis cross-mois via DSN avril, puis Lewis.

---

## Réveil 1 — Cat 6 trésorerie net-only
**Fix systémique (reconciler)** : `_SAISIE_RE` n'attrapait que les saisies au montant NÉGATIF ; le layout Cegid montre parfois la saisie POSITIVE en colonne montant salarial (« Saisie Crédit Logement 500.00 »). Régex généralisée (1er nombre de la ligne, signe-agnostique, toujours traité comme retenue). Bénéficie à Lewis/futurs imports.

| Salarié | avant | après | note |
|---|---|---|---|
| GOISSAUD | 513,16 | **14,64** | saisie crédit logement 500 € importée ; résiduel = brut +14,64 (HS/recup) |
| TULEKI | 564,18 | **100,85** | saisie + mutuelle famille + absence ; résiduel = maintien/HS |
| OVIE | 492,04 | 492,04 (revert) | MNS AUSSI faux → participation numéraire/PEE (cat 5) |
| LUSUMBU | 89,63 | 89,63 (revert) | idem : EYWAI MNS 4035,45 vs réel 4125,08 = −89,63 (participation) |
| ZZSORTI113 | 76,37 | 76,37 (revert) | idem participation (salarié SORTI) |

→ OVIE/LUSUMBU/ZZSORTI reclassés **cat 5 participation** (MNS faux du même montant que le net avant impôt). À traiter avec GUELAI/SALAUN/PORRAL via DSN S21.G00.58 type 03.

## Réveil 1 — Cat 7 arrêt SANS maintien
Nouveau script `cat7_arret.py` : parse « Absence maladie DDMMYY-DDMMYY », pose les jours OUVRÉS en `absence_non_remuneree` (7 h), vide le pointage, revert-safe. Guard SKIP si « Maintien de salaire ».

| Salarié | avant | après | note |
|---|---|---|---|
| DALLACOSTA | 537,66 | **0,01 ✓** | arrêt 01-07/05 + reconciler (mutuelle Isolé, PAS 0) |
| MATHIEU | 952,81 | 106,58 | arrêt 11-31/05 ; résiduel = APPRENTI (participation 1994,76 + CSG APP) → cat 5 |

**Convergés : 23 → 24** (DALLACOSTA).

## Réveil 1 — Cat 7 congés sans solde / arrêt partiel
| Salarié | avant | après | note |
|---|---|---|---|
| LAMOTTE | 916,53 | 95,44 | PAS congé maladie mais **congés sans solde** 04-07/11/18-22 (70 h) + PAS 8,7 % ; reconciler pose les 10 jours ; résiduel brut +95,44 = quote-part HS structurelle pendant absence (subtilité moteur) |
| KIRMIZI | 91,65 | 91,65 (revert) | rebuild empire (essai 268,89) ; brut +91,65 = arrêt partiel + CP + ajustements HS conjoncturelles (−1 h) à recaler manuellement |

SERE (maintien 361,39) et OZEN (maintien 288,59) → chantier moteur maintien.

## Réveil 1 — Cat 9 « temps partiel » (en réalité mixte)
| Salarié | avant | après | note |
|---|---|---|---|
| CHEVALLIER | 497,46 | **0,00 ✓** | en fait TEMPS PLEIN 151,67 avec CP + congés s.solde 20-22/05 ; reconciler nickel |
| RABBENI | 1222,78 | **47,97** | vrai temps partiel (17,49 h) mais planned_calendar en template PLEIN (16j×7,5=120 h) → HC fictives. Fix DATA : heures_prevues jour = durée_hebdo/5 = 3,5 h. Résiduel −47,97 ≈ prime ancienneté (base 804,33 non calculée pour TP) |
| LIKA | 801,84 | 197,31 | idem TP 20,08 h ; daily 4,02 h. Résiduel +197 = heures récup (38,58 h) + CP non modélisés |
| POULAIN | 194,50 | 194,50 (revert) | apprenti (taux 7,93) ; net imposable exonéré IR non modélisé → cat apprenti |

**Convergés : 24 → 25** (CHEVALLIER). Fix planned_calendar temps-partiel = pattern réutilisable (template plein sur contrat partiel).

## Réveil 1 — Cat 10 individuels + fix systémique seniority
- **FAIZI** 16,94 → **0,00 ✓** : +1 h HS conjoncturelle 25 % (monthly_input payroll_quantity=1, label « Heures supplémentaires conjoncturelles »). Brut −16,94 = 1 h × taux × 1,25.
- **KHENE** 48,86 → **0,00 ✓** : `seniority_reference_date` était **None** → prime ancienneté (1628,63 × 3 % = 48,86) non calculée. Posé 2022-05-02.
- **RABBENI** 47,97 → **0,29** : idem seniority 2018-01-11 → prime 6 % ; résiduel 0,29 rounding.
- **TULEKI** 100,85 → **0,00 ✓** : seniority 2018-07-16.
- Batch seniority revert-safe sur les autres non-convergés (MOHAMEDY/OZEN/DEPONGE/BARRY/ADAMYOUSSE/MIRZADA/OSMANI/SCHARFF/LUSUMBU) → tous REVERT (prime déjà calculée via contrat, ou empire). ⚠ Bug de méthode corrigé : après revert il FAUT régénérer le bulletin (payslip stale) — fait.

**Pattern systémique** : `seniority_reference_date=None` + bulletin avec « BANC Prime ancienneté » → prime parfois non calculée (dépend si contrat.date_entree est exploitable). Fix data ponctuel. Candidat futur : que le reconciler pose TOUJOURS la date d'ancienneté du bulletin (même sans reprise) en revert-safe.

**Convergés : 25 → 28** (FAIZI, KHENE, TULEKI). RABBENI 0,29 (quasi).

## Réveil 1 — Cat 4 remboursement transport 50 %
- **SACALA** 18,00 → **0,00 ✓** ; **AWAD** 18,01 → **0,01 ✓** : ligne « SBUS rbst transport 50 % 18.00 » = remboursement 50 % abonnement transport (net-only, non soumis). Mécanisme moteur DATA existant : `specificites_paie.transport.abonnement_mensuel_total` (=36 → 50 % = 18 ajouté au net). Scan des autres non-convergés : aucun autre concerné.

**Convergés : 28 → 30** (SACALA, AWAD).

## BILAN INTERMÉDIAIRE (fin réveil 1) — MBC 23 → 30 convergés
Convergés ce soir : DALLACOSTA, CHEVALLIER, FAIZI, KHENE, TULEKI, SACALA, AWAD (+ RABBENI 0,29 quasi).
Gros gains non convergés : GOISSAUD 513→14, LAMOTTE 916→95, MATHIEU 952→106, LIKA 801→197, RABBENI 1222→0,29.

### Blocages restants (documentés)
1. **Participation numéraire/PEE au MNS** (~14 : OVIE 492, SALAUN 321, GUELAI 97, LUSUMBU 90, ZZSORTI 76, GILLET 77, PORRAL 74, BOUVIERP 22, MIRZADA2 12, GAILLET 5, BLONDEAU 4, + forfait DROZ/LABBE/BORDELIER/DEPONGE + ADAMYOUSSE, MATHIEU/POULAIN apprentis). MURKY/RISQUÉ (a déjà cassé Colorplast) → chantier moteur supervisé. Diagnostic : GUELAI MNS seul faux (net à payer OK) ≠ LUSUMBU/ZZSORTI (net ET MNS faux du même montant) → 2 sous-cas distincts.
2. **Maintien maladie** (OZEN 51, SERE 85, KIRMIZI 91, LAMOTTE 95 + cross-mois BABA 2650, SAFI2 1868, OSMANI2 831, SCHARFF 126). Cross-mois = arrêt commencé en avril (M-1) + « Rappel Maintien ». Nécessite refonte base journalière maintien (jours ouvrés × taux réel) — engine global sans garde-fou Colorplast, DÉLIBÉRÉMENT NON FAIT (cf. mémoire, reverté avant). Chantier supervisé.
3. **CP arbitrage** (GAUDEY 212, ASKARI 11) : ligne « ARBITRAGE DES CONGES PAYES » (monétisation CP) mal gérée.
4. **Rounding irréductible** : DAWRAN 0,14, FOFANA 0,15, RABBENI 0,29, OSMANI 0,67, DULPHY 0,77 ; cat 3 HS struct SOUCHEYRE/SULPICE/CVITKOVIC/BOUSSANOR/FANOVO (~14, optimum reconciler).
5. **Cat 2 absences frac** : BARRY 56, AVAHOUIN2 38, MIRZADA 3,5.

### Handoff fin réveil 1
MBC à **30/75** = max atteignable en DATA pur (sans toucher le moteur). Les résiduels restants exigent :
- soit un chantier moteur SUPERVISÉ (participation MNS/PEE dans `calcul_net.py` ; refonte base journalière maintien dans `maintien_salaire_service.py`) — délibérément NON fait cette nuit (risque de régression prod sans garde-fou Colorplast, cf. mémoire),
- soit des données M-1 (cross-mois BABA/SAFI2/OSMANI2),
- soit du reverse-engineering individuel à faible rendement (CP arbitrage GAUDEY/ASKARI, apprentis POULAIN/MATHIEU, cat-2 frac BARRY/AVAHOUIN2, rounding).
Aucun changement `app/` moteur effectué → Colorplast 7/7 et pytest intacts par construction (toutes mes modifs = données par employee_id MBC + script reconciler).
**Prochain réveil : démarrer Lewis mai 2026** via le skill `/backtest-paie-auto` (« fais le backtest paie complet et automatique de Lewis pour mai 2026 »).

---

# LEWIS mai 2026 — Réveil 2 (démarrage)

## Phase 0/1 — cadrage + premier signal
- Lewis = **métallurgie** (convention META, ≠ plasturgie MBC). company_id b3c747e4-5094-4252-b0e6-5b711a5b4e81.
- 40 refs, **36 matched** (4 unmatched refs), **0/36 convergés**. Écarts 39 → 1916 € (GROSSET 39 le plus proche, BASTER 1916 le plus loin).
- Comparaison réutilise `mbc_state --company Lewis` (regen+compare). Le reconciler `mbc_reconcile.py` est spécifique MBC (regex GAN/plasturgie).

## Diagnostic systémique Lewis (⚠ NON résolu — fixes systématiques simples ÉCHOUENT)
1. **Prévoyance `adhesion=False` pour TOUS** alors que les bulletins portent une prévoyance (« E_V6 PREVOYANCE NON CADRE TU1 META » 0,73 %/0,73 %, base ~brut TU1 ; cadres = barème différent).
2. **Mutuelle « EMUT Mutuelle » barème DSN-import FAUX** : GROSSET config 20,88/0 (libellé « Cadre » à tort) vs bulletin réel **58,03/58,03**. Chaque salarié a son propre `mutuelle_type_id` (certains partagés). 58,03/58,03 = valeur non-cadre récurrente.
3. **PAS** : `type_taux` variés (ex. GROSSET « 13 » = taux neutre) ; HIRARD PAS −86,40 (sous-prélèvement).
4. **CP arbitrage** (« ARBITRAGE DES CONGES PAYES ») + paniers équipe soumis/non soumis + journée de solidarité.

## ⚠ Leçon (test GROSSET, revert-safe) : fixes systématiques mono-dimension EMPIRENT
GROSSET before=39,43 → +mutuelle 58,03/58,03 = **63,47** → +prévoyance 0,73 % = **80,33** (REVERTÉ).
→ GROSSET a plusieurs erreurs **qui se compensent partiellement** (brut +19,97 trop haut, NI −39,43 trop bas, net −20,68 trop bas). Corriger UNE dimension isolément pousse le net dans le mauvais sens. **Conclusion : Lewis exige une reconstruction PAR SALARIÉ ligne à ligne (comme le reconciler MBC), pas des patchs de barème en masse.**

## Prochaine étape (réveil 3) : construire un reconciler adapté Lewis
Adapter `mbc_reconcile.py` → `lewis_reconcile.py` : regex « EMUT Mutuelle », prévoyance META E_V6 0,73 %, panier équipe, CP arbitrage, PAS type_taux. Approche revert-safe identique (rebuild monthly_inputs + mutuelle_type + prévoyance + calendrier → garde si tier baisse). Traiter par écart croissant. **Aucun fix appliqué ce réveil (tout reverté) — Lewis reste 0/36, arbre propre.**

## Réveil 3 — Lewis : diagnostic GROSSET complet + SPEC reconciler
**GROSSET entièrement décodé** (EYWAI `calcul_du_brut` = base 2040 + **4 h HS FANTÔME 67,25** ; rien d'autre). EYWAI est en réalité **totalement dé-configuré** pour mai :
- Brut réel Cegid 2087,28 = base 2040 − CP absence 188,30 (2×7 h @13,45) + prime présence 24 + panier équipe soumis 2,80 + **ARBITRAGE CP 208,78**. EYWAI n'a AUCUN de ces éléments (arbitrage_conges=null, primes_non_soumises=[], monthly_inputs vides) — juste base + HS fantôme.
- **HS fantôme 4 h** : ne vient PAS du calendrier (planned 117 h < 151,67 ; actual vide). Source à investiguer (import pointage équipe S18-21 ?).
- Mutuelle EMUT 58,03/58,03 (config DB 20,88/0 « Cadre » faux). Prévoyance E_V6 META 0,73 % (adhesion=False). Panier non soumis SPAJ 103,60 (net-only) absent. PAS type 13.

**Preuve empirique que les fixes isolés ÉCHOUENT** : mutuelle seule 39→63, +prévoyance→80 (les primes/arbitrage/HS dominent et se compensent). → Il FAUT tout reconstruire d'un coup, en revert-safe (comme le reconciler MBC).

### SPEC `lewis_reconcile.py` (à construire réveil suivant, contexte frais)
Adapter `mbc_reconcile.py`. Réutiliser : `take_snapshot`/`restore_snapshot`/`tier_s`/`_apply_calendar`/`_clear_actual_hours`. Étendre le snapshot pour couvrir la table `company_mutuelle_types` (partagée, hors snapshot MBC). Regex Lewis :
- Primes taxées : `BPRE` (présence), `BPAN` (panier équipe soumis) → monthly_inputs taxés.
- Panier non soumis : `SPAJ Paniers jours non soumis` → net-only (`_is_frais_pro_non_soumis_input`, contient « panier »).
- Mutuelle : `EMUT Mutuelle  sal  taux  sal  pat` → fixer `montant_salarial`/`montant_patronal` du mutuelle_type de l'employé (⚠ certains types partagés — vérifier).
- Prévoyance : `E_V\d PREVOYANCE ... META  base  0.7300  sal  pat` → `specificites_paie.prevoyance.lignes_specifiques` base brut_plafonne, taux lu du bulletin (0,73 % non-cadre ; cadres = autre).
- CP : jours « Congés payés : DDMMYY » (déjà géré) + **ARBITRAGE CP `BQCP`** : ⚠ le reconciler MBC l'EXCLUT (le moteur reconstruit l'indemnité CP depuis le calendrier) — mais ici EYWAI ne le fait pas → comprendre le mécanisme `arbitrage_conges`/`details_conges` avant de décider (prime taxée directe vs flag moteur).
- PAS : `type_taux`/taux depuis DSN `S21.G00.50.009` / bulletin.
- HS fantôme : investiguer la source (pointage équipe) et la neutraliser.
Tester par écart croissant (GROSSET 39, MANDANGUY 111…), revert-safe. La revert-safety garantit zéro régression même si le reconciler est incomplet (les cas non gérés revert simplement).

**État : Lewis 0/36 (arbre propre, tout reverté). MBC 30/75. Aucune modif moteur `app/`.**

## Réveil 3 (suite) — Reconciler Lewis construit + exécuté sur les 36
`backend/scripts/backtest/lewis_reconcile.py` créé (adapté de mbc_reconcile) : reconstruit d'un bloc, revert-safe, primes taxées (BPRE/BPAN) + panier non soumis (SPAJ) + mutuelle EMUT + prévoyance E_V6 META 0,73 % + CP + PAS. Snapshot étendu à `company_mutuelle_types`. Fix contrainte d'unicité mutuelle : **réassigner** vers un type existant portant les bons montants (au lieu d'éditer en place → collision `idx_company_mutuelle_types_dsn_key`).

**Résultat : 0/36 convergés, mais 24 salariés améliorés, gain cumulé +2063 €.** NOBLE 1190→**27** (forfait, quasi). 0 erreur. La correction net-side (mutuelle 58,03/58,03 + prévoyance 0,73 % + CP + panier non soumis) gagne ~30-40 €/salarié, mais les résiduels restent 400-1500 € car dominés par le **BRUT** non reconstruit.

### Levier BRUT restant (clé de la convergence Lewis) — 2 mécanismes moteur à comprendre
1. **HS FANTÔME** : `planned_calendar` à **7,8 h/jour** (GROSSET : 15×7,8=117 h) → le moteur génère 4 h HS 25 % (67 €) absentes du bulletin. Même classe que le fix temps-partiel MBC mais pour temps plein à horaire journalier erroné. Fix : corriger les heures/jour du calendrier (ou durée contractuelle) pour ne pas générer d'HS non déclarée. **Affecte probablement TOUS les Lewis** (barème équipe importé avec 7,8 h/j).
2. **CP ARBITRAGE** (`BQCP ARBITRAGE DES CONGES PAYES`) : monétisation de CP (GROSSET 208,78) qui REMPLACE l'indemnité CP. Poser les jours en `conges_payes` (indemnité) risque de double-compter vs l'arbitrage. Nécessite de comprendre le mécanisme moteur `arbitrage_conges`/`details_conges` (le reconciler MBC EXCLUT BQCP car le moteur reconstruit l'indemnité depuis le calendrier — mais côté Lewis EYWAI ne le fait pas → `arbitrage_conges=null`).
3. **Anomalie NI<MNS** sur bas salaires temps partiel (MANDANGUY : EYWAI NI 457 < MNS 566, inversé ; réel NI 568 > MNS 548) → probable bug moteur calcul NI sur petits salaires.

Décomposition brut GROSSET validée : base 2040 − CP absence 188,30 + présence 24 + panier 2,80 + arbitrage 208,78 = 2087,28. EYWAI = base 2040 + HS fantôme 67,25.

## ÉTAT FINAL DE LA NUIT
- **MBC mai 2026 : 30/75 convergés** (départ 23). 6 fixes DATA systémiques, 0 modif moteur. Reste = participation MNS/PEE + maintien maladie (chantiers moteur supervisés) + cross-mois M-1 + rounding.
- **Lewis mai 2026 : 0/36 convergés, 24 améliorés (+2063 €)**, reconciler net-side construit. Reste = reconstruction BRUT (HS fantôme calendrier + CP arbitrage) + anomalie NI moteur = chantiers supervisés.
- **Zéro modif du moteur `app/`** de toute la nuit → Colorplast 7/7 + pytest intacts par construction. Aucun commit.
- Boucle ARRÊTÉE : il ne reste que des chantiers moteur supervisés (participation, maintien, HS fantôme/CP arbitrage Lewis) et des blocages M-1 — hors périmètre du travail data autonome de nuit.
