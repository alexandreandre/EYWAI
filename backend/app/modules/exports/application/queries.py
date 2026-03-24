# Queries applicatives exports (lectures : prévisualisation, historique, téléchargement).
from typing import Optional

from app.modules.exports.domain import rules as domain_rules
from app.modules.exports.infrastructure import providers
from app.modules.exports.infrastructure import queries as infra_queries
from app.modules.exports.infrastructure import mappers
from app.modules.exports.infrastructure.storage import create_signed_url
from app.modules.exports.schemas import (
    ExportPreviewRequest,
    ExportPreviewResponse,
    ExportHistoryResponse,
    ExportHistoryEntry,
    ExportTotals,
    ExportAnomaly,
)


def preview_export(company_id: str, request: ExportPreviewRequest) -> ExportPreviewResponse:
    """
    Prévisualise un export sans générer de fichier.
    Comportement identique à l'ancien router POST /preview.
    """
    company_id = request.company_id or company_id
    if not domain_rules.is_supported_export_type_for_preview(request.export_type):
        raise ValueError(f"Type d'export '{request.export_type}' non implémenté")

    if request.export_type == "journal_paie":
        preview = providers.preview_journal_paie(company_id, request.period, request.employee_ids)
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
        )
    elif request.export_type == "virement_salaires":
        preview = providers.preview_paiement_salaires(
            company_id,
            request.period,
            request.employee_ids,
            request.excluded_employee_ids,
            request.execution_date,
            request.payment_label,
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
        )
    elif request.export_type in ["od_salaires", "od_charges_sociales", "od_pas", "od_globale"]:
        preview = providers.preview_od(
            company_id,
            request.period,
            request.export_type,
            request.employee_ids,
            request.filters.get("date_ecriture") if request.filters else None,
        )
        totals = ExportTotals(
            employees_count=0,
            total_amount=preview.get("total_debit", 0),
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=0,
            totals=totals,
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
        )
    elif request.export_type in ["export_cabinet_generique", "export_cabinet_quadra", "export_cabinet_sage"]:
        preview = providers.preview_cabinet_export(
            company_id,
            request.period,
            request.export_type,
            request.employee_ids,
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
        )
    elif request.export_type == "dsn_mensuelle":
        dsn_type = (
            request.filters.get("dsn_type", "dsn_mensuelle_normale") if request.filters else "dsn_mensuelle_normale"
        )
        establishment_id = request.filters.get("establishment_id") if request.filters else None
        preview = providers.preview_dsn(
            company_id,
            request.period,
            dsn_type,
            request.employee_ids,
            establishment_id,
        )
        totals = ExportTotals(
            employees_count=preview["nombre_salaries"],
            total_brut=preview.get("masse_salariale_brute"),
            total_cotisations_salariales=None,
            total_cotisations_patronales=None,
            total_net_imposable=preview.get("total_net_imposable"),
            total_net_a_payer=None,
            total_amount=preview.get("masse_salariale_brute"),
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=preview["period"],
            employees_count=preview["nombre_salaries"],
            totals=totals,
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
        )
    else:
        raise ValueError(f"Type d'export '{request.export_type}' non implémenté")


def get_export_history(
    company_id: str,
    export_type: Optional[str] = None,
    period: Optional[str] = None,
) -> ExportHistoryResponse:
    """
    Récupère l'historique des exports pour une entreprise.
    Comportement identique à l'ancien router GET /history.
    """
    exports = infra_queries.list_exports_by_company(company_id, export_type, period)
    user_ids = list({exp["generated_by"] for exp in exports if exp.get("generated_by")})
    profiles_map = infra_queries.get_profiles_map(user_ids)

    history_entries = []
    for exp in exports:
        user_id = exp.get("generated_by")
        profile = profiles_map.get(user_id) if user_id else None
        user_name = mappers.build_display_name_from_profile(profile)
        entry_dict = mappers.build_history_entry_dict(exp, user_name)
        totals_raw = entry_dict.get("totals")
        entry_dict["totals"] = ExportTotals(**totals_raw) if totals_raw else None
        history_entries.append(ExportHistoryEntry(**entry_dict))
    return ExportHistoryResponse(exports=history_entries, total=len(history_entries))


def get_export_for_download(company_id: str, export_id: str) -> str:
    """
    Retourne l'URL signée du premier fichier d'un export.
    Raises:
        ValueError: si l'export n'existe pas ou n'a pas de fichier.
    """
    export = infra_queries.get_export_by_id(export_id, company_id)
    if not export:
        raise ValueError("Export non trouvé")
    file_paths = export.get("file_paths", [])
    if not file_paths:
        raise ValueError("Aucun fichier associé à cet export")
    file_path = file_paths[0]
    return create_signed_url(file_path, 3600)
