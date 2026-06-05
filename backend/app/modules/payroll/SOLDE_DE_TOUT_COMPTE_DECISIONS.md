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

Points d’entrée publics inchangés : `EmployeeExitDocumentGenerator`, méthodes `generate_certificat_travail`, `generate_attestation_pole_emploi`, `generate_solde_tout_compte` (mêmes signatures et type de réponse `bytes`). Les endpoints employee exits restent inchangés.

## Rendu du reçu pour solde de tout compte (format avocat)

- **Moteur** : le reçu pour solde de tout compte est désormais rendu en **HTML → PDF via WeasyPrint** (`common/html_renderer.py`), au lieu des tableaux ReportLab. Cela aligne le document sur le contrat de travail (`shared/infrastructure/pdf/contract.py`) : mise en page sobre « cabinet d’avocat en droit du travail » (serif Times, bordures fines, sans encadrés colorés).
- **Motivation** : les anciens tableaux ReportLab utilisaient des cellules de chaîne à largeur fixe sans retour à la ligne ; les libellés longs débordaient et se chevauchaient. WeasyPrint gère nativement le wrapping.
- **Séparation calcul / rendu** : `common/socle_commun.py` expose des fonctions `compute_*` qui renvoient des **données structurées** (sections / lignes via `amount_row`, `amounts_section`, `info_row`, `info_section`) ; le rendu est centralisé dans `html_renderer.render_solde_tout_compte_html`. Les modules `cases/*` construisent les sections propres à chaque type de rupture puis délèguent au renderer.
- Le certificat de travail et l’attestation France Travail restent en ReportLab (`document_generator.py`), inchangés.
