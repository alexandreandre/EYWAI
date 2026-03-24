# Schémas de réponse du module exports (migration depuis schemas.export).
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .requests import ExportType

# Statuts d'export
ExportStatus = Literal["previewed", "generated", "cancelled", "replaced"]


# ============================================================================
# RÉPONSES D'EXPORT (communs)
# ============================================================================


class ExportAnomaly(BaseModel):
    """Anomalie détectée lors de la prévisualisation"""
    type: Literal["error", "warning"]
    message: str
    severity: Literal["blocking", "warning"]
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None


class ExportTotals(BaseModel):
    """Totaux de contrôle pour un export"""
    employees_count: int
    total_brut: Optional[float] = None
    total_cotisations_salariales: Optional[float] = None
    total_cotisations_patronales: Optional[float] = None
    total_net_imposable: Optional[float] = None
    total_net_a_payer: Optional[float] = None
    total_amount: Optional[float] = None


class ExportPreviewResponse(BaseModel):
    """Réponse de prévisualisation d'export"""
    export_type: ExportType
    period: str
    employees_count: int
    totals: ExportTotals
    anomalies: List[ExportAnomaly] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    can_generate: bool = True


class ExportFileInfo(BaseModel):
    """Informations sur un fichier généré"""
    filename: str
    path: str
    size: int
    format: Literal["csv", "xlsx", "zip", "xml"]


class ExportReport(BaseModel):
    """Rapport d'export généré"""
    export_type: ExportType
    period: str
    generated_at: datetime
    generated_by: str
    employees_count: int
    totals: ExportTotals
    anomalies: List[ExportAnomaly] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ExportGenerateResponse(BaseModel):
    """Réponse de génération d'export"""
    export_id: str
    export_type: ExportType
    period: str
    status: ExportStatus
    files: List[ExportFileInfo]
    report: ExportReport
    download_urls: Dict[str, str]


# ============================================================================
# HISTORIQUE
# ============================================================================


class ExportHistoryEntry(BaseModel):
    """Entrée dans l'historique des exports"""
    id: str
    export_type: ExportType
    period: str
    status: ExportStatus
    generated_at: datetime
    generated_by: str
    generated_by_name: Optional[str] = None
    files_count: int
    totals: Optional[ExportTotals] = None


class ExportHistoryResponse(BaseModel):
    """Réponse de l'historique des exports"""
    exports: List[ExportHistoryEntry]
    total: int


# ============================================================================
# ÉCRITURES COMPTABLES (OD)
# ============================================================================


class ODType(BaseModel):
    """Type d'OD comptable"""
    type: Literal["od_salaires", "od_charges_sociales", "od_pas", "od_globale"]
    libelle: str


class AccountingMapping(BaseModel):
    """Mapping comptable rubrique → compte"""
    rubrique_code: str
    rubrique_libelle: str
    compte_comptable: str
    sens: Literal["debit", "credit"]
    type_rubrique: Literal["salaire", "charge_patronale", "dette_salarie", "dette_organisme", "pas", "autre"]
    analytique: Optional[str] = None
    journal: str = "OD"


class EcritureComptable(BaseModel):
    """Une ligne d'écriture comptable"""
    date_ecriture: str
    journal: str
    compte_comptable: str
    libelle: str
    debit: float
    credit: float
    analytique: Optional[str] = None
    reference_export: Optional[str] = None
    periode_paie: str
    employee_id: Optional[str] = None


class ODPreviewResponse(BaseModel):
    """Réponse de prévisualisation d'OD"""
    od_type: str
    period: str
    date_ecriture: str
    nombre_lignes: int
    total_debit: float
    total_credit: float
    equilibre: bool
    ecart: float
    anomalies: List[ExportAnomaly] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    can_generate: bool = True
    mapping_utilise: Dict[str, AccountingMapping] = Field(default_factory=dict)


class ODGenerateResponse(BaseModel):
    """Réponse de génération d'OD"""
    export_id: str
    od_type: str
    period: str
    status: ExportStatus
    files: List[ExportFileInfo]
    report: ExportReport
    download_urls: Dict[str, str]
    equilibre: bool
    total_debit: float
    total_credit: float


# ============================================================================
# DSN MENSUELLE
# ============================================================================


class DSNType(BaseModel):
    """Type de DSN"""
    type: Literal["dsn_mensuelle_normale", "dsn_neant"]
    libelle: str


class DSNEmployeePreview(BaseModel):
    """Prévisualisation DSN pour un salarié"""
    employee_id: str
    nom: str
    prenom: str
    nir: Optional[str] = None
    contrat_type: Optional[str] = None
    brut: float
    net_imposable: float
    pas: float
    cotisations_salariales: float
    cotisations_patronales: float
    organismes: List[str] = Field(default_factory=list)


class DSNOrganismeSummary(BaseModel):
    """Résumé par organisme"""
    organisme: str
    code_organisme: Optional[str] = None
    nombre_salaries: int
    total_cotisations_salariales: float
    total_cotisations_patronales: float


class DSNPreviewResponse(BaseModel):
    """Réponse de prévisualisation DSN"""
    period: str
    dsn_type: str
    establishment_siret: Optional[str] = None
    nombre_salaries: int
    nombre_contrats: int
    masse_salariale_brute: float
    total_charges: float
    total_net_imposable: float
    total_pas: float
    organismes_concernes: List[DSNOrganismeSummary] = Field(default_factory=list)
    employees_preview: List[DSNEmployeePreview] = Field(default_factory=list)
    anomalies: List[ExportAnomaly] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    can_generate: bool = True


class DSNReport(BaseModel):
    """Rapport DSN détaillé"""
    period: str
    dsn_type: str
    establishment_siret: Optional[str] = None
    nombre_salaries: int
    totaux_financiers: Dict[str, float]
    controles: List[ExportAnomaly] = Field(default_factory=list)
    avertissements_acceptes: List[str] = Field(default_factory=list)
    utilisateur_generateur: str
    date_generation: datetime
    version_norme_dsn: str = "V01"


class DSNGenerateResponse(BaseModel):
    """Réponse de génération DSN"""
    export_id: str
    period: str
    status: ExportStatus
    files: List[ExportFileInfo]
    report: DSNReport
    download_urls: Dict[str, str]
    message_teletransmission: str = "Ce fichier doit être télétransmis manuellement sur net-entreprises.fr"


__all__ = [
    "ExportStatus",
    "ExportAnomaly",
    "ExportTotals",
    "ExportPreviewResponse",
    "ExportFileInfo",
    "ExportReport",
    "ExportGenerateResponse",
    "ExportHistoryEntry",
    "ExportHistoryResponse",
    "ODType",
    "AccountingMapping",
    "EcritureComptable",
    "ODPreviewResponse",
    "ODGenerateResponse",
    "DSNType",
    "DSNEmployeePreview",
    "DSNOrganismeSummary",
    "DSNPreviewResponse",
    "DSNReport",
    "DSNGenerateResponse",
]
