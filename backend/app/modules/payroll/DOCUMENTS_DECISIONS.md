# Décisions documents de paie (`app/modules/payroll/documents`)

## Migration depuis `services/`

- **Fichiers migrés** : `payslip_generator.py`, `payslip_generator_forfait.py`, `payslip_editor.py`, `salary_certificate_generator.py`, `simulated_payslip_generator.py`.
- **Contraintes** : comportement et signatures publiques inchangés. Imports adaptés vers `app.core.paths` (PATH_TO_PAYROLL_ENGINE, payroll_engine_templates, payroll_engine_employee_bulletins), `app.core.database`, et `app.modules.payroll.application.analyzer` pour le générateur heures.

## Subprocess

La génération de bulletins est désormais 100 % in-process dans `app` : `payslip_run_heures.run_payslip_generation_heures` et `payslip_run_forfait.run_payslip_generation_forfait` sont appelés directement par `payslip_generator.py` et `payslip_generator_forfait.py`. Les scripts `backend_calculs/generateur_fiche_paie*.py` ne sont plus invoqués.

## Stratégie attestation de salaire / module absences

- **Une seule source de vérité** : `app/modules/payroll/documents/salary_certificate_generator.py`.
- Le module **absences** ne duplique pas la logique ; il **consomme** ce générateur via son **provider** (`ISalaryCertificateProvider`). L’implémentation `SalaryCertificateProvider` dans `app/modules/absences/infrastructure/providers.py` importe `SalaryCertificateGenerator` depuis `app.modules.payroll.documents.salary_certificate_generator`.
- L’ancienne implémentation dans `app/modules/absences/infrastructure/salary_certificate_generator.py` peut être conservée comme doublon déprécié ou supprimée à terme ; les appelants passent par le provider ou par le wrapper `services/salary_certificate_generator.py` qui réexporte depuis payroll/documents.

## Wrappers legacy

- `services/payslip_generator.py`, `services/payslip_generator_forfait.py`, `services/payslip_editor.py`, `services/salary_certificate_generator.py`, `services/simulated_payslip_generator.py` réexportent depuis `app.modules.payroll.documents.*`.
- `app/shared/infrastructure/payslip_services.py` délègue vers `app.modules.payroll.documents`.
