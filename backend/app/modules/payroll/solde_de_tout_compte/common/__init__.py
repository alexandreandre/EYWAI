"""
Shared utilities and common sections for Solde de Tout Compte PDF generation
"""

from . import pdf_helpers
from . import socle_commun
from .pdf_helpers import (
    setup_custom_styles,
    format_date,
    format_currency,
    safe_float,
    safe_str,
    build_company_header,
    build_title_header,
    build_legal_mentions,
    build_signatures,
    build_footer,
)
from .socle_commun import (
    get_salary_prorata,
    build_remunerations_section,
    build_conges_section,
    build_autres_regularisations_section,
    build_retenues_section,
    build_total_section,
)

__all__ = [
    "pdf_helpers",
    "socle_commun",
    "setup_custom_styles",
    "format_date",
    "format_currency",
    "safe_float",
    "safe_str",
    "build_company_header",
    "build_title_header",
    "build_legal_mentions",
    "build_signatures",
    "build_footer",
    "get_salary_prorata",
    "build_remunerations_section",
    "build_conges_section",
    "build_autres_regularisations_section",
    "build_retenues_section",
    "build_total_section",
]
