"""Génération du contrat de prêt employeur (PDF)."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.core.paths import payroll_engine_templates
from app.modules.employee_loans.infrastructure.repository import (
    employee_loan_installments_repository,
    employee_loans_repository,
)


def _format_currency(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def generate_loan_contract_pdf(
    loan_id: str,
    company_data: Dict[str, Any],
    employee_data: Dict[str, Any],
) -> bytes:
    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan:
        raise ValueError("Prêt non trouvé.")

    schedule = employee_loan_installments_repository.list_by_loan(loan_id)

    template_dir = payroll_engine_templates()
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("template_contrat_pret.html")

    html = template.render(
        company=company_data,
        employee=employee_data,
        loan=loan,
        schedule=schedule,
        generated_at=datetime.now().strftime("%d/%m/%Y"),
        format_currency=_format_currency,
    )
    pdf_buffer = BytesIO()
    HTML(string=html).write_pdf(pdf_buffer)
    return pdf_buffer.getvalue()


def store_loan_contract(
    loan_id: str,
    company_id: str,
    pdf_bytes: bytes,
) -> str:
    from app.modules.employee_loans.infrastructure.providers import employee_loan_storage

    path = f"{company_id}/{loan_id}/contrat_pret.pdf"
    employee_loan_storage.upload(path, pdf_bytes)
    employee_loans_repository.update(loan_id, {"contract_file_path": path})
    return path
