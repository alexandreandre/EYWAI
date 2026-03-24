# Audit de transfert : backend_calculs → app.modules.payroll

> **Runtime disque** : les JSON/templates de paie ne sont plus sous `backend_calculs/` ; ils passent par `app.core.paths` → racine **`app/runtime/payroll/`** (`data/`, `templates/`). Ce document décrit surtout l’équivalence **code** legacy ↔ `app.modules.payroll`.

## 1. Scripts concernés

| Legacy (backend_calculs) | App (source de vérité) |
|-------------------------|-------------------------|
| `generateur_fiche_paie.py` | `app/modules/payroll/documents/payslip_run_heures.py` + `payslip_run_common.py` |
| `generateur_fiche_paie_forfait.py` | `app/modules/payroll/documents/payslip_run_forfait.py` + `payslip_run_common.py` |
| `moteur_paie/*` (contexte, calcul_brut, etc.) | `app/modules/payroll/engine/*` (déjà migré) |

## 2. Helpers et ordre des opérations

### Heures (generateur_fiche_paie.py ↔ payslip_run_heures.py)

| Étape | Legacy | App |
|-------|--------|-----|
| Saisie / acompte | `saisie_du_mois`, `montant_acompte` | Idem |
| Contexte | `ContextePaie(chemin_contrat, chemin_entreprise, chemin_cumuls)` | Idem + `chemin_data_dir` |
| Période | `definir_periode_de_paie(contexte, annee, mois)` | `payslip_run_common.definir_periode_de_paie` |
| Calendrier étendu | `creer_calendrier_etendu(chemin_employe, date_debut, date_fin)` | `payslip_run_common.creer_calendrier_etendu` |
| Calendrier du mois (réduction) | `saisie_horaires_mois_courant.get('calendrier', [])` | `saisie_horaires.get("calendrier", [])` |
| Primes (PPV, catalogue) | Boucle primes_soumises / primes_non_soumises / primes_soumises_impot | Idem |
| Brut | `calculer_salaire_brut(contexte, calendrier_saisie=calendrier_etendu, ...)` | Idem (engine) |
| Cotisations | `calculer_cotisations(contexte, salaire_brut_calcule, ...)` | Idem |
| Réduction générale | `total_heures_mois` puis `calculer_reduction_generale(contexte, salaire_brut_calcule, total_heures_mois)` | Idem |
| Net / impôt | `calculer_net_et_impot(contexte, ...)` | Idem |
| Bulletin | `creer_bulletin_final(contexte, ...)` | Idem |
| Cumuls | `mettre_a_jour_cumuls(contexte, ..., chemin_employe)` | `payslip_run_common.mettre_a_jour_cumuls` |
| PDF | Jinja2 + WeasyPrint, `base_url='.'` | Idem, `base_url=str(engine_root)` |

**Note** : `preparer_calendrier_enrichi` existe dans le legacy mais son résultat (`calendrier_du_mois_enrichi`) n’est pas utilisé ensuite ; l’app ne l’appelle pas (comportement équivalent).

### Forfait (generateur_fiche_paie_forfait.py ↔ payslip_run_forfait.py)

| Étape | Legacy | App |
|-------|--------|-----|
| Contexte / période / calendrier étendu | Idem structure | Idem |
| Calendrier étendu vide | Génération via `analyser_jours_forfait_du_mois` + planned/actual | Idem dans `run_payslip_generation_forfait` |
| Brut | `calculer_salaire_brut_forfait(...)` | Idem (engine) |
| Réduction générale | `heures_equivalentes = nombre_jours_travailles * 7.0` | Idem |
| Cumuls / bulletin / PDF | Idem | Idem |

## 3. Modules moteur (engine)

Tous les appels moteur passent par `app.modules.payroll.engine` :

- `contexte.ContextePaie`
- `calcul_brut.calculer_salaire_brut`
- `calcul_brut_forfait.calculer_salaire_brut_forfait`
- `calcul_cotisations.calculer_cotisations`
- `calcul_reduction_generale.calculer_reduction_generale`
- `calcul_net.calculer_net_et_impot`
- `bulletin.creer_bulletin_final`
- `analyser_jours_forfait.analyser_jours_forfait_du_mois`

Les scripts legacy utilisent `moteur_paie` (wrapper vers `app.modules.payroll.engine`). Les run modules app les importent directement depuis `app.modules.payroll.engine`.

## 4. Fichiers communs (payslip_run_common.py)

- `_get_end_date_for_month`
- `definir_periode_de_paie`
- `mettre_a_jour_cumuls`
- `creer_calendrier_etendu`

Comportement aligné avec les deux scripts legacy (heures et forfait).
