# Migration Solde de tout compte

## Source de vérité

- **common/** : helpers PDF et socle commun (prorata salaire, sections rémunérations, congés, etc.) — migré depuis `services/solde_common/`.
- **cases/** : un module par type de sortie (démission, rupture conventionnelle, licenciement, retraite, fin période d’essai, generic) — migré depuis `services/solde_cases/`.
- **document_generator.py** : classe `EmployeeExitDocumentGenerator` (certificat de travail, attestation Pôle Emploi, solde de tout compte) — migrée depuis `services/document_generator.py`.

## Appelants

- **app/shared/compat/employee_exit_document_generator.py** : utilise `app.modules.payroll.solde_de_tout_compte.EmployeeExitDocumentGenerator` et expose `get_employee_exit_document_generator()` pour le module employee_exits.
- **api/routers/employee_exits.py** : continue d’importer `EmployeeExitDocumentGenerator` depuis `services.document_generator` (wrapper legacy).
- **services/document_generator.py** : wrapper qui ré-exporte depuis `app.modules.payroll.solde_de_tout_compte`.
- **services/solde_common/** et **services/solde_cases/** : wrappers qui ré-exportent depuis `app.modules.payroll.solde_de_tout_compte.common` et `.cases`, pour `annual_review_pdf_generator` et `promotion_document_service`.

## Comportement

Aucun changement fonctionnel : mêmes points d’entrée publics (`EmployeeExitDocumentGenerator`, méthodes `generate_certificat_travail`, `generate_attestation_pole_emploi`, `generate_solde_tout_compte`), mêmes signatures et réponses. Les endpoints employee exits et la génération de documents restent inchangés.
