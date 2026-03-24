# Finalisation migration paie — source de vérité unique

Le module **app.modules.payroll** est la seule source de vérité pour la logique paie (moteur, documents, exports, solde de tout compte). Les endpoints et les tests ciblent ce module.

## Dépendances

- **backend_api/requirements.txt** : contient toutes les dépendances nécessaires au module payroll (Jinja2, WeasyPrint, ReportLab, openpyxl, supabase, etc.). Aucune installation séparée depuis `backend_calculs/requirements.txt` n’est nécessaire pour faire tourner l’API.
- **backend_calculs/requirements.txt** : legacy ; conservé pour d’éventuels scripts autonomes ou CI. La logique métier paie exécutée par l’API ne dépend plus de cet environnement.

## Tests

- **tests/test_forfait_jour_complet.py** : importe `analyser_jours_forfait_du_mois` et `calculer_salaire_brut_forfait` depuis `app.modules.payroll.engine` (plus de `backend_calculs`).
- Lancer les tests depuis la racine du backend : `pytest tests/test_forfait_jour_complet.py` (avec `PYTHONPATH` incluant le répertoire backend_api si besoin).

## Références directes au module payroll (hors wrappers)

- **Routers** : payslips, simulation, schedules, exports, employee_exits, absences → appellent `app.modules.payroll.application` ou `app.modules.payroll.documents` / `solde_de_tout_compte.common`.
- **absences** : `SalaryCertificateGenerator` depuis `app.modules.payroll.documents.salary_certificate_generator`.
- **annual_review_pdf_generator**, **promotion_document_service** : helpers PDF depuis `app.modules.payroll.solde_de_tout_compte.common.pdf_helpers`.

## Code legacy et archivage

**Ne pas supprimer** le code legacy tant que :

1. Tous les tests (dont `test_forfait_jour_complet.py`) passent.
2. Les endpoints en production utilisent bien `app.modules.payroll` (vérifié via les imports des routers et services ci‑dessus).

Une fois ces conditions remplies :

- **backend_calculs/** : peut être archivé (déplacé dans un dossier `_archive/backend_calculs` ou équivalent). Les scripts `generateur_fiche_paie*.py` y sont encore invoqués en subprocess par les documents (payslip_generator, payslip_generator_forfait) ; si l’on souhaite archiver, il faudra auparavant remplacer ces appels subprocess par des appels directs au moteur dans `app.modules.payroll.engine` (voir ENGINE_DECISIONS.md).
- **services/** (fichiers paie) : les wrappers (`payslip_generator.py`, `document_generator.py`, `solde_common/*`, `solde_cases/*`, `salary_certificate_generator.py`, etc.) réexportent déjà depuis `app.modules.payroll`. Ils peuvent rester en place comme couche de compatibilité temporaire ; les supprimer uniquement après mise à jour de tout code qui les importe encore.

## Comportement

- Aucun changement fonctionnel attendu : mêmes réponses API, mêmes calculs. La migration ne fait que faire pointer les imports et les tests vers `app.modules.payroll`.
