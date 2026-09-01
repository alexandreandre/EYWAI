"""Réexport — source de vérité : app.modules.payroll.documents.salary_certificate_generator."""

from app.modules.payroll.documents.salary_certificate_generator import (
    KIND_NET,
    KIND_RETABLI,
    SalaryCertificateGenerator,
    amounts_from_payslip_data,
    resolve_cpam_attestation_kind,
)

__all__ = [
    "KIND_NET",
    "KIND_RETABLI",
    "SalaryCertificateGenerator",
    "amounts_from_payslip_data",
    "resolve_cpam_attestation_kind",
]
