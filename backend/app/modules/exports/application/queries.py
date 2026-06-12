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


def preview_export(
    company_id: str, request: ExportPreviewRequest
) -> ExportPreviewResponse:
    """
    Prévisualise un export sans générer de fichier.
    Comportement identique à l'ancien router POST /preview.
    """
    company_id = request.company_id or company_id
    if not domain_rules.is_supported_export_type_for_preview(request.export_type):
        raise ValueError(f"Type d'export '{request.export_type}' non implémenté")

    if request.export_type == "journal_paie":
        preview = providers.preview_journal_paie(
            company_id, request.period, request.employee_ids
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
    elif request.export_type in [
        "od_salaires",
        "od_charges_sociales",
        "od_pas",
        "od_globale",
    ]:
        regroupement = (
            request.filters.get("regroupement", "global") if request.filters else "global"
        )
        preview = providers.preview_od(
            company_id,
            request.period,
            request.export_type,
            request.employee_ids,
            request.filters.get("date_ecriture") if request.filters else None,
            regroupement,
        )
        payslip_totals = preview.get("totals") or {}
        employees_count = int(
            preview.get("employees_count") or payslip_totals.get("employees_count") or 0
        )
        totals = ExportTotals(
            employees_count=employees_count,
            total_brut=payslip_totals.get("total_brut"),
            total_net_a_payer=payslip_totals.get("total_net_a_payer"),
            total_cotisations_salariales=payslip_totals.get("total_cotisations_salariales"),
            total_cotisations_patronales=payslip_totals.get("total_cotisations_patronales"),
            total_amount=preview.get("total_debit", 0),
        )
        balance_debug = preview.get("balance_debug")
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=employees_count,
            totals=totals,
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details={"balance_debug": balance_debug} if balance_debug else None,
        )
    elif request.export_type in [
        "export_cabinet_generique",
        "export_cabinet_quadra",
        "export_cabinet_sage",
    ]:
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
            request.filters.get("dsn_type", "dsn_mensuelle_normale")
            if request.filters
            else "dsn_mensuelle_normale"
        )
        establishment_id = (
            request.filters.get("establishment_id") if request.filters else None
        )
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
    elif request.export_type == "charges_sociales":
        caisses = request.filters.get("caisses") if request.filters else None
        include_consolidated = (
            request.filters.get("include_consolidated", True)
            if request.filters
            else True
        )
        preview = providers.preview_charges_sociales(
            company_id,
            request.period,
            request.employee_ids,
            caisses,
            include_consolidated,
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=preview.get("details"),
        )
    elif request.export_type == "notes_frais":
        expense_types = request.filters.get("expense_types") if request.filters else None
        preview = providers.preview_notes_frais(
            company_id,
            request.period,
            request.employee_ids,
            expense_types,
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=preview.get("details"),
        )
    elif request.export_type == "acomptes":
        preview = providers.preview_acomptes(company_id, request.period)
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=preview.get("details"),
        )
    elif request.export_type == "saisies":
        preview = providers.preview_saisies(company_id, request.period)
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=preview.get("details"),
        )
    elif request.export_type == "fec":
        preview = providers.preview_fec(company_id, request.period, request.employee_ids)
        balance_debug = preview.get("balance_debug")
        details = preview.get("details") or {}
        if balance_debug and "balance_debug" not in details:
            details = {**details, "balance_debug": balance_debug}
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=details or None,
        )
    elif request.export_type == "prets_employeur":
        preview = providers.preview_prets_employeur(company_id, request.period)
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=preview.get("details"),
        )
    elif request.export_type == "paiement_organismes":
        preview = providers.preview_paiement_organismes(
            company_id, request.period, request.employee_ids
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=preview.get("details"),
        )
    elif request.export_type == "attestations_annexes":
        preview = providers.preview_attestations(
            company_id, request.period, request.employee_ids
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=preview.get("details"),
        )
    elif request.export_type == "conges_absences":
        absence_types = (
            request.filters.get("absence_types") if request.filters else None
        )
        preview = providers.preview_conges_absences(
            company_id,
            request.period,
            request.employee_ids,
            absence_types,
        )
        return ExportPreviewResponse(
            export_type=request.export_type,
            period=request.period,
            employees_count=preview["employees_count"],
            totals=ExportTotals(**preview["totals"]),
            anomalies=[ExportAnomaly(**a) for a in preview["anomalies"]],
            warnings=preview["warnings"],
            can_generate=preview["can_generate"],
            details=preview.get("details"),
        )
    elif request.export_type == "recapitulatif_montants":
        preview = providers.preview_recapitulatif_montants(
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
            details=preview.get("details"),
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


def _resolve_file_path_entry(entry: object) -> tuple[str, str]:
    """Retourne (storage_path, filename) depuis une entrée file_paths."""
    if isinstance(entry, dict):
        path = str(entry.get("path") or entry.get("filename") or "")
        filename = str(entry.get("filename") or path.rsplit("/", 1)[-1] or "export")
        return path, filename
    path = str(entry)
    return path, path.rsplit("/", 1)[-1] or "export"


def get_export_for_download(
    company_id: str, export_id: str, file_index: int = 0
) -> str:
    """
    Retourne l'URL signée d'un fichier d'un export (index 0 par défaut).
    Raises:
        ValueError: si l'export n'existe pas ou n'a pas de fichier.
    """
    files = get_export_download_files(company_id, export_id)
    if file_index < 0 or file_index >= len(files):
        raise ValueError("Index de fichier invalide")
    return files[file_index]["download_url"]


def get_export_download_files(company_id: str, export_id: str) -> list[dict[str, str]]:
    """Liste les URLs signées de tous les fichiers d'un export."""
    export = infra_queries.get_export_by_id(export_id, company_id)
    if not export:
        raise ValueError("Export non trouvé")
    file_paths = export.get("file_paths", [])
    if not file_paths or not isinstance(file_paths, list):
        raise ValueError("Aucun fichier associé à cet export")

    result: list[dict[str, str]] = []
    for idx, entry in enumerate(file_paths):
        path, filename = _resolve_file_path_entry(entry)
        if not path:
            continue
        result.append(
            {
                "index": str(idx),
                "filename": filename,
                "path": path,
                "download_url": create_signed_url(path, 3600),
            }
        )
    if not result:
        raise ValueError("Aucun fichier associé à cet export")
    return result
