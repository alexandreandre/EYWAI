# PDF generation (credentials autonome ; contract en wrapper legacy).
from app.shared.infrastructure.pdf.credentials import generate_credentials_pdf
from app.shared.infrastructure.pdf.contract import generate_contract_pdf

__all__ = ["generate_credentials_pdf", "generate_contract_pdf"]
