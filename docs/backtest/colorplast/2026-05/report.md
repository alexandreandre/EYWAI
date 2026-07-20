# Backtest paie — Colorplast — 05/2026

**Statut final : 7/7 salariés convergent (tier S ≤ 0,05 €).**

Session du 2026-07-06, complétée grâce (1) au texte intégral des bulletins Cegid fourni par l'utilisateur puis (2) aux DSN réelles (`Config/Colorplast/DSN/000005_0526_000001 (2).dsn`), qui ont permis de vérifier chaque hypothèse au centime plutôt que de deviner.

## Résultat

| Matricule | Tier S initial (session) | **Tier S final** |
|---|---|---|
| BUGNY | 0.00 € | ✅ 0.00 € |
| COTTE | 0.02 € | ✅ 0.02 € |
| FUCKAR | 449.87 € | ✅ **0.01 €** |
| DEMORY | 585.60 € | ✅ **0.00 €** |
| ESPINOSA | 925.58 € | ✅ **0.00 €** |
| GAUTHERON | 1004.96 € | ✅ **0.00 €** |
| GIRERD | 5265.81 € | ✅ **0.01 €** |

## Bugs moteur corrigés (généraux, impact au-delà de Colorplast)

1. **Aucun arrêt maladie/AT n'a jamais déduit de salaire sur la plateforme.** Les événements `arret_maladie`/`ferie` à 0 h étaient filtrés avant d'atteindre `calcul_brut.py` (`analyzer.py`, agrégation des événements). Fix : ne plus filtrer ces types à 0 h.
2. **Une absence chevauchant un week-end/férié écrasait ces jours en absence** au lieu de les laisser neutres (`CalendarUpdateProvider.update_calendar_from_days`, `providers.py`). Fix : ne retyper que les jours `type=="travail"`.
3. **Repli journalier sur durée légale (35h/5=7h), pas contractuelle** pour une absence isolée (`calcul_brut._heures_journalieres_contrat`, plafonné à `min(contrat, 35)/5`).
4. **Jour férié non payé si ancienneté < seuil** : nouveau paramètre `specificites_paie.jours_feries_anciennete_min_mois` (absent = comportement inchangé). 1er mai protégé sans condition ; "journée de solidarité" neutralisée via `companies.settings.jour_solidarite`.
5. **Réduction des HS structurelles mensualisées pendant une absence** : nouvelle ligne "Réduction HS structurelles (jours d'absence)", correctement exclue du calcul de défiscalisation IR des heures sup (taguée `is_reduction_hs`).
6. **HS conjoncturelles à 50 % jamais supportées** : ajout d'un second canal `heures_supplementaires_conjoncturelles_50` (contexte, moteur, générateur), en plus du canal 25 % existant.
7. **Participation en PEE jamais câblée côté générateur** : `payslip_generator.py` ne renseignait jamais `part_pee` depuis `monthly_inputs` (le moteur `payslip_run_heures.py` savait déjà le gérer). Ajout de `_is_participation_pee_input`.
8. **Montant net social (MNS) et participation 100 % PEE** : formule corrigée pour que la CSG/CRDS totale de la part PEE contribue au MNS (rémunération due au titre du mois même si placée en épargne salariale), alors que la part numéraire nette continue de contribuer normalement. Validé exactement sur GIRERD via DSN (`S21.G00.58` type `03`).
9. **`net_avant_impot` (bulletin) ne doit pas être une copie de `montant_net_social`** — coïncidence propre à BUGNY/COTTE, fausse dès qu'il y a une régularisation nette ou une participation PEE. Recalculé en `net_a_payer + PAS réintégré` (`bulletin.py`). Le mapping backtest (`rubric_map.py`) dupliquait aveuglément `montant_net_social` sous les deux clés.
10. **Régularisations "hors assiette" (absentes de la DSN) modélisées via le mécanisme d'acompte** (`_is_net_a_payer_only_correction_input`) : "Report NAP négatif" et "SMU2 GAN MUTUELLE FAMILLE" ne réduisent que le net à payer, jamais le montant net social — confirmé en cherchant ces montants dans la DSN réelle (absents des deux, donc de purs ajustements de trésorerie du cabinet).

## Corrections de données (DB, par salarié)

- **FUCKAR** : absence 04→08/05 requalifiée `sans_solde`→`arret_maladie` (plage corrigée 05-08/05) ; `jours_feries_anciennete_min_mois=3` ; HS conjoncturelle 2,5 h ajoutée ; **taux prévoyance corrigé 1,5 %/0,93 %→0,465 %/0,465 %** (confirmé DSN : la config initiale, héritée d'un import antérieur, était fausse).
- **DEMORY** : absence 23-29/05 requalifiée `sans_solde`→`arret_at` ; même règle ancienneté jours fériés ; **taux prévoyance corrigé de la même façon**.
- **GIRERD** : `is_forfait_jour` corrigé à `False` ; coefficient 710→830 ; participation renommée en PEE ; **barème mutuelle partagé "Isolé (Cadre)" corrigé** (189,96 €/0 €→29,24 €/29,23 €, même bug d'import DSN déjà connu et déjà corrigé pour le barème "Non-Cadre" équivalent) ; cotisations prévoyance cadre (0,465 %/0,465 %) et retraite supplémentaire cadre (2,5 %/2,5 %) ajoutées.
- **ESPINOSA** : coefficient DSN 710→750 (metadata, sans effet calcul) ; acompte sur participation -1000 € ajouté ; HS conjoncturelles 3 h (25 %) + 6,5 h (50 %) ajoutées ; régularisation GAN mutuelle famille -98,12 € ajoutée.
- **GAUTHERON** : pointage réel d'avril corrigé (jours 27-28-29, données d'import erronées) ; acompte sur participation -1100 € ajouté ; régularisation GAN mutuelle famille -98,12 € ajoutée.

## Fausses pistes explorées et écartées (documentées pour ne pas les retenter)

- **CSG/CRDS sur HS non déductible à 6,8 % au lieu de 9,7 % pour l'exonération IR** : semblait coller exactement à la valeur DSN `S21.G00.58` type `01` ("montant net des heures compl/suppl exo.") pour FUCKAR/DEMORY/GIRERD pris isolément — mais cette valeur DSN s'est révélée **purement informative** (cumul annuel de suivi du plafond d'exonération), pas un terme du calcul du net imposable. Appliquer ce changement cassait les 5 autres salariés déjà exacts. La vraie cause du résidu FUCKAR/DEMORY était un taux de prévoyance mal saisi (voir ci-dessus).
- **Réintégration de la prévoyance/retraite sup. patronale au net imposable** (via un code DSN `S21.G00.54` type `93` qui semblait correspondre exactement) : cassait BUGNY/COTTE/ESPINOSA/GAUTHERON. Ce code DSN sert probablement à une déclaration statistique distincte, sans lien avec le calcul du net imposable.

## Tests

`pytest tests/unit/payroll/` : 365 passed / 1 failed. L'échec (`test_golden_bulletins.py::test_non_cadre_temps_partiel`) est confirmé **non lié** à ces changements (isolé via `git stash` avant toute modification de cette session).
