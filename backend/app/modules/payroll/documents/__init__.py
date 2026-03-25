# Génération et gestion des documents de paie (bulletins, attestations, simulés).
# Migré depuis services/payslip_*, services/salary_certificate_*, services/simulated_payslip_*.

from app.modules.payroll.documents.payslip_generator import process_payslip_generation
from app.modules.payroll.documents.payslip_generator_forfait import (
    is_forfait_jour,
    process_payslip_generation_forfait,
)
from app.modules.payroll.documents.payslip_editor import (
    regenerate_pdf_from_data,
    save_edited_payslip,
    restore_payslip_version,
)
from app.modules.payroll.documents.salary_certificate_generator import (
    SalaryCertificateGenerator,
)
from app.modules.payroll.documents.simulated_payslip_generator import (
    SimulatedPayslipGenerator,
    generate_simulated_payslip_pdf,
)

__all__ = [
    "process_payslip_generation",
    "is_forfait_jour",
    "process_payslip_generation_forfait",
    "regenerate_pdf_from_data",
    "save_edited_payslip",
    "restore_payslip_version",
    "SalaryCertificateGenerator",
    "SimulatedPayslipGenerator",
    "generate_simulated_payslip_pdf",
]
