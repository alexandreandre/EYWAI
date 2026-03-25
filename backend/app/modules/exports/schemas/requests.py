# Schémas de requête du module exports (migration depuis schemas.export).
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Types d'exports disponibles (partagé avec les réponses)
ExportType = Literal[
    "journal_paie",
    "charges_sociales",
    "conges_absences",
    "notes_frais",
    "ecritures_comptables",
    "od_salaires",
    "od_charges_sociales",
    "od_pas",
    "od_globale",
    "export_cabinet_generique",
    "export_cabinet_quadra",
    "export_cabinet_sage",
    "dsn_mensuelle",
    "virement_salaires",
    "recapitulatif_montants",
]


# ============================================================================
# REQUÊTES D'EXPORT
# ============================================================================


class ExportPreviewRequest(BaseModel):
    """Requête pour prévisualiser un export"""

    export_type: ExportType
    period: str = Field(
        ..., pattern=r"^\d{4}-\d{2}$", description="Période au format YYYY-MM"
    )
    company_id: Optional[str] = None
    employee_ids: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    excluded_employee_ids: Optional[List[str]] = None
    execution_date: Optional[str] = None
    payment_label: Optional[str] = None


class ExportGenerateRequest(BaseModel):
    """Requête pour générer un export"""

    export_type: ExportType
    period: str = Field(
        ..., pattern=r"^\d{4}-\d{2}$", description="Période au format YYYY-MM"
    )
    company_id: Optional[str] = None
    employee_ids: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    format: Literal["csv", "xlsx"] = "csv"
    excluded_employee_ids: Optional[List[str]] = None
    execution_date: Optional[str] = None
    payment_label: Optional[str] = None


# ============================================================================
# EXPORTS SPÉCIFIQUES
# ============================================================================


class ChargesSocialesExportRequest(BaseModel):
    """Requête spécifique pour l'export charges sociales"""

    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    company_id: Optional[str] = None
    caisses: Optional[List[str]] = None
    include_consolidated: bool = True


class CongesAbsencesExportRequest(BaseModel):
    """Requête spécifique pour l'export congés/absences"""

    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    company_id: Optional[str] = None
    employee_ids: Optional[List[str]] = None
    absence_types: Optional[
        List[Literal["conge_paye", "rtt", "maladie", "sans_solde"]]
    ] = None
    status: Literal["validated"] = "validated"


class NotesFraisExportRequest(BaseModel):
    """Requête spécifique pour l'export notes de frais"""

    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    company_id: Optional[str] = None
    employee_ids: Optional[List[str]] = None
    status: Optional[List[Literal["validated", "paid"]]] = None
    expense_types: Optional[
        List[Literal["Transport", "Restaurant", "Hôtel", "Fournitures", "Autre"]]
    ] = None


# ============================================================================
# ÉCRITURES COMPTABLES (OD)
# ============================================================================


class ODExportRequest(BaseModel):
    """Requête pour générer une OD comptable"""

    od_type: Literal["od_salaires", "od_charges_sociales", "od_pas", "od_globale"]
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    company_id: Optional[str] = None
    employee_ids: Optional[List[str]] = None
    establishment_id: Optional[str] = None
    regroupement: Literal["global", "par_etablissement", "par_analytique"] = "global"
    date_ecriture: Optional[str] = None


# ============================================================================
# DSN MENSUELLE
# ============================================================================


class DSNPreviewRequest(BaseModel):
    """Requête pour prévisualiser une DSN"""

    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    company_id: Optional[str] = None
    establishment_id: Optional[str] = None
    dsn_type: Literal["dsn_mensuelle_normale", "dsn_neant"] = "dsn_mensuelle_normale"
    employee_ids: Optional[List[str]] = None


class DSNGenerateRequest(BaseModel):
    """Requête pour générer une DSN"""

    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    company_id: Optional[str] = None
    establishment_id: Optional[str] = None
    dsn_type: Literal["dsn_mensuelle_normale", "dsn_neant"] = "dsn_mensuelle_normale"
    employee_ids: Optional[List[str]] = None
    accept_warnings: bool = False


__all__ = [
    "ExportType",
    "ExportPreviewRequest",
    "ExportGenerateRequest",
    "ChargesSocialesExportRequest",
    "CongesAbsencesExportRequest",
    "NotesFraisExportRequest",
    "ODExportRequest",
    "DSNPreviewRequest",
    "DSNGenerateRequest",
]
