"""
Shared utilities and common sections for Solde de Tout Compte PDF generation
"""

from . import html_renderer
from . import pdf_helpers
from . import socle_commun
from .pdf_helpers import (
    setup_custom_styles,
    format_date,
    format_currency,
    safe_float,
    safe_str,
    build_company_header,
)
from .html_renderer import (
    amount_row,
    amounts_section,
    info_row,
    info_section,
    render_solde_tout_compte_html,
)
from .socle_commun import (
    get_salary_prorata,
    compute_remunerations_section,
    compute_conges_section,
    compute_autres_regularisations_section,
    compute_retenues_section,
)

__all__ = [
    "html_renderer",
    "pdf_helpers",
    "socle_commun",
    "setup_custom_styles",
    "format_date",
    "format_currency",
    "safe_float",
    "safe_str",
    "build_company_header",
    "amount_row",
    "amounts_section",
    "info_row",
    "info_section",
    "render_solde_tout_compte_html",
    "get_salary_prorata",
    "compute_remunerations_section",
    "compute_conges_section",
    "compute_autres_regularisations_section",
    "compute_retenues_section",
]
