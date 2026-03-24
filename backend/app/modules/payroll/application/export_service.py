"""
Facade applicative des exports paie (journal de paie, virements, OD, cabinet, DSN).
Les routers appellent ce module, pas exports/ directement.
Réexporte les fonctions de app.modules.payroll.exports.
"""

from __future__ import annotations

# Journal de paie
from app.modules.payroll.exports.journal_paie import (
    get_journal_paie_data,
    generate_journal_paie_export,
    preview_journal_paie,
)

# Paiement salaires
from app.modules.payroll.exports.paiement_salaires import (
    get_paiement_salaires_data,
    preview_paiement_salaires,
    generate_paiement_salaires_export,
    generate_bank_file,
)

# Écritures comptables / OD
from app.modules.payroll.exports.ecritures_comptables import (
    preview_od,
    get_payslip_data_for_od,
    generate_od_salaires,
    generate_od_charges_sociales,
    generate_od_pas,
    generate_od_export_file,
)

# Formats cabinet
from app.modules.payroll.exports.formats_cabinet import (
    preview_cabinet_export,
    generate_cabinet_generic_export,
    generate_cabinet_quadra_export,
    generate_cabinet_sage_export,
)

# DSN
from app.modules.payroll.exports.dsn import (
    preview_dsn,
    get_company_data,
    get_dsn_employees_data,
    generate_dsn_xml,
)

__all__ = [
    "get_journal_paie_data",
    "generate_journal_paie_export",
    "preview_journal_paie",
    "get_paiement_salaires_data",
    "preview_paiement_salaires",
    "generate_paiement_salaires_export",
    "generate_bank_file",
    "preview_od",
    "get_payslip_data_for_od",
    "generate_od_salaires",
    "generate_od_charges_sociales",
    "generate_od_pas",
    "generate_od_export_file",
    "preview_cabinet_export",
    "generate_cabinet_generic_export",
    "generate_cabinet_quadra_export",
    "generate_cabinet_sage_export",
    "preview_dsn",
    "get_company_data",
    "get_dsn_employees_data",
    "generate_dsn_xml",
]
