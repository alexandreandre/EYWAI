# Plan — heures de récupération

Spec : `docs/superpowers/specs/2026-11-05-heures-de-recuperation-design.md`. Branche `feat/heures-recuperation`, partie de `origin/feat/dsn-octobre` (41d21353). TDD : chaque tâche commence par un test rouge.

## Tâche 1 — Domaine : mise au compteur à l'équivalent majoré
`modulation/domain/hour_account_rules.py` : `mettre_hs_au_compteur(calendrier, bornes, majorations, solde, plafond, heures_a_payer)` → calendrier réduit, HS mises par type, repos crédité. Tests : 4 h à 25 % → 5 h ; mixte 25/50 ; plafond en heures de repos ; HS hors fenêtre intactes ; heures imposées à payer.

## Tâche 2 — Domaine : solde reporté d'une année sur l'autre, état du mois
`solde_au(mouvements, annee, mois)` (cumul de tous les mouvements actifs jusqu'au mois inclus) ; `etat_du_mois(mouvements, annee, mois)` → acquis, pris (avec dates), payé, solde. Exclusion des crédits de paie du mois (bac à sable, recalcul).

## Tâche 3 — Hook de paie
`payroll_hook.apply_modulation_hour_account_to_calendar` : fenêtre des variables, majorations du barème, plafond pour « tout au compteur », décision du mois (« payer ») respectée quel que soit son statut, solde hors crédits du mois. `payslip_run_heures` lui passe fenêtre et taux, et pose `contexte.recuperation_du_mois`.

## Tâche 4 — Bulletin
`engine/bulletin.py` : `solde_conges["recuperation"]` quand le réglage est actif ; `bulletin_view.construire_compteurs` : colonne « Récup. (h) », notes « 7 h le 13/07 », mention D3171-11 dès 7 h. Ligne informative « Heures sup mises au compteur de récupération ».

## Tâche 5 — Absence « Récupération »
Prise en heures (`heures_par_jour`) ; débit = heures saisies ; annulation qui rend les heures (mouvement `cancelled`). Libellés « Récupération (heures sup) ».

## Tâche 6 — Paiement du solde
Débit `debit_payout` du mois ; le run du mois ajoute la prime « Paiement solde heures de récupération » (heures × taux de base). API + bouton.

## Tâche 7 — Écrans
Réglage société (une carte : payées / au compteur + plafond, conditions L3121-37 dites à l'activation) ; carte du bulletin (heures du mois au compteur, « Payer ces heures ce mois-ci » avec la conséquence, « Payer le solde ») ; solde dans les absences.

## Tâche 8 — Données (sur « lance »)
Script `scripts/recuperation_reprise_30_09.py` : simulé par défaut, liste des changements ; `--ecrire` sur accord.

## Tâche 9 — Vérifications
Tests unitaires, filet avant/après (0 écart), revue du diff, fusion dans `feat/dsn-octobre`, déploiement, parcours RH sur le site de test, CHANGELOG.
