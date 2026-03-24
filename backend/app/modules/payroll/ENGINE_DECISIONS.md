# Décisions moteur de paie (engine) et générateurs

Document des choix effectués lors de la migration du moteur de paie et de la gestion des générateurs de fiche de paie.

## 1. Migration du moteur : `backend_calculs/moteur_paie` → `app/modules/payroll/engine`

- **Fait** : tout le contenu de `backend_calculs/moteur_paie` a été copié dans `app/modules/payroll/engine`.
- **Contraintes respectées** : pas de refactor de la logique ; noms, signatures et comportements inchangés ; seuls les chemins d’import ont été adaptés (imports relatifs au sein du package `engine`).
- **Compatibilité** : les anciens chemins restent valides via des **wrappers** dans `backend_calculs/moteur_paie/` qui réexportent depuis `app.modules.payroll.engine`. Ainsi, tout code qui fait par exemple `from backend_calculs.moteur_paie.contexte import ContextePaie` continue de fonctionner sans modification.

## 2. Générateurs de fiche de paie : `generateur_fiche_paie.py` et `generateur_fiche_paie_forfait.py`

**Fait** : la génération ne passe plus par des subprocess ; elle est 100 % in-process dans `app` (voir section 3).

- **Heures** : `payslip_run_heures.run_payslip_generation_heures` ; **Forfait** : `payslip_run_forfait.run_payslip_generation_forfait`. Les scripts `backend_calculs/generateur_fiche_paie*.py` ne sont plus invoqués par l’API.
- **Raison (historique)** : ces scripts étaient invoqués en **subprocess** par les services (ex. `payslip_generator.py`, `payslip_generator_forfait.py`) en s’exécutant comme scripts Python. Les déplacer dans `app/modules/payroll` obligerait à changer le point d’entrée (ex. `python -m app.modules.payroll.documents.generateur_fiche_paie`) et à mettre à jour tous les appelants, avec un impact plus large.
- **Comportement actuel** : ils importent `moteur_paie` sans préfixe (`from moteur_paie.contexte import ContextePaie`, etc.). Lors de l’exécution depuis `backend_calculs/`, `moteur_paie` est bien résolu vers `backend_calculs.moteur_paie`, qui pointe désormais vers le moteur migré via les wrappers. Aucune modification des générateurs n’est nécessaire pour l’instant.
- **À terme** : on pourra soit migrer ces scripts dans le module payroll (par ex. `documents/` ou un sous-dossier dédié) et basculer les appelants sur un point d’entrée module, soit remplacer les appels subprocess par des **appels directs** au moteur dans `app.modules.payroll.engine` (voir section 3).

## 3. Remplacement des appels subprocess par des appels directs au moteur

- **Objectif** : à terme, remplacer l’invocation des scripts `generateur_fiche_paie*.py` en subprocess par des appels directs aux fonctions du moteur dans `app.modules.payroll.engine` (et, le cas échéant, à une couche service dans le module payroll).
- **Préparation** : la migration du moteur dans `app/modules/payroll/engine` et les wrappers legacy rendent déjà possible d’importer et d’utiliser le moteur depuis le code applicatif (API, services) sans subprocess. Les étapes suivantes pourront consister à :
  1. Exposer des fonctions de génération de bulletin dans le module payroll (engine + couche application/documents si besoin).
  2. Remplacer, dans les services existants, l’appel subprocess par un appel à ces fonctions.
  3. Garder les scripts `generateur_fiche_paie*.py` en compatibilité (CLI, tests, debug) ou les déprécier une fois les appelants migrés.

## 4. Utilitaires paie migrés vers le module payroll

- **`backend_calculs/idcc.py`** → **`app/modules/payroll/engine/idcc.py`**  
  Utilitaire technique (client API PISTE/KALI pour recherche de textes par IDCC). Même comportement, mêmes signatures (`obtenir_token()`, `rechercher_textes_kali(token, idcc)`, `main()`). Un wrapper dans `backend_calculs/idcc.py` réexporte depuis `app.modules.payroll.engine.idcc` pour compatibilité des anciens chemins d'import.
- Aucun autre fichier de `backend_calculs` n'est importé par le moteur ; le moteur ne dépend que de son package `engine` et des libs standard / supabase / dateutil.

## 5. Analyse et écriture paie (analyzer / writer)

- **Source de vérité unique pour `analyser_horaires_du_mois`** : `app/modules/payroll/application/analyzer.py`. Logique migrée depuis `services/payroll_analyzer.py` et `backend_api/payroll_analyzer.py` (fusion). Signature in-memory : `(planned_data_all_months, actual_data_all_months, duree_hebdo_contrat, annee, mois, employee_name)`.
- **`engine/analyser_horaires.py`** : signature fichier `(chemin_employe, annee, mois, duree_hebdo_contrat)` ; charge les calendriers puis délègue à `application.analyzer`.
- **Writer** : `payroll_writer.py` → `app/modules/payroll/application/writer.py`. `generer_et_enregistrer_evenements` inchangée.
- **Appelants** : payslip_generator, schedules, app.shared.payroll_analyzer, schedules/providers. Wrappers legacy : `payroll_analyzer.py`, `services/payroll_analyzer.py`, `payroll_writer.py`.

## 6. Point d’attention connu (non corrigé volontairement)

- **Simulation / calcul inverse** : `ChargerContexte` a été ajouté dans `engine/contexte.py`. Simulation et calcul inverse exposés via `application/simulation_commands.py` ; le router simulation n’utilise plus de subprocess. Comportement préexistant à la migration ; à corriger lors d’un prochain passage sur la simulation (ex. ajout d’une factory `ChargerContexte` ou adaptation des appels).
