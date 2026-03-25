# Service applicatif exports — orchestration des cas d'usage.
# Logique migrée depuis api/routers/exports.py ; les routers ne font qu'appeler ce service.
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.modules.exports.application import commands
from app.modules.exports.application import queries
from app.modules.exports.application.dto import ExportRecordForInsert
from app.modules.exports.infrastructure import providers
from app.modules.exports.infrastructure.storage import (
    upload_export_file,
    create_signed_url,
)
from app.modules.exports.domain import rules as domain_rules
from app.modules.exports.infrastructure.queries import get_user_display_name
from app.modules.exports.schemas import (
    ExportPreviewRequest,
    ExportPreviewResponse,
    ExportGenerateRequest,
    ExportGenerateResponse,
    ExportTotals,
    ExportAnomaly,
    ExportFileInfo,
    ExportReport,
    DSNReport,
    DSNGenerateResponse,
    ExportHistoryResponse,
)

BUCKET = "exports"


def preview_export(
    company_id: str, request: ExportPreviewRequest
) -> ExportPreviewResponse:
    """Prévisualise un export sans générer de fichier."""
    return queries.preview_export(company_id, request)


def get_export_history(
    company_id: str,
    export_type: Optional[str] = None,
    period: Optional[str] = None,
) -> ExportHistoryResponse:
    """Récupère l'historique des exports."""
    return queries.get_export_history(company_id, export_type, period)


def get_export_download_url(company_id: str, export_id: str) -> str:
    """Retourne l'URL signée pour télécharger le premier fichier d'un export."""
    return queries.get_export_for_download(company_id, export_id)


def generate_export(
    company_id: str,
    user_id: str,
    request: ExportGenerateRequest,
) -> Union[ExportGenerateResponse, DSNGenerateResponse]:
    """
    Génère un export et enregistre l'historique.
    Comportement identique à l'ancien router POST /generate.
    """
    company_id = request.company_id or company_id
    if not domain_rules.is_supported_export_type_for_generate(request.export_type):
        raise ValueError(f"Type d'export '{request.export_type}' non implémenté")
    user_name = get_user_display_name(user_id)

    if request.export_type == "journal_paie":
        return _generate_journal_paie(company_id, user_id, user_name, request)
    elif request.export_type in [
        "od_salaires",
        "od_charges_sociales",
        "od_pas",
        "od_globale",
    ]:
        return _generate_od(company_id, user_id, user_name, request)
    elif request.export_type in [
        "export_cabinet_generique",
        "export_cabinet_quadra",
        "export_cabinet_sage",
    ]:
        return _generate_cabinet(company_id, user_id, user_name, request)
    elif request.export_type == "dsn_mensuelle":
        return _generate_dsn(company_id, user_id, user_name, request)
    elif request.export_type == "virement_salaires":
        return _generate_virement_salaires(company_id, user_id, user_name, request)
    else:
        raise ValueError(f"Type d'export '{request.export_type}' non implémenté")


def _content_type(extension: str) -> str:
    return f"application/{extension}" if extension == "xlsx" else "text/csv"


def _generate_journal_paie(
    company_id: str,
    user_id: str,
    user_name: str,
    request: ExportGenerateRequest,
) -> ExportGenerateResponse:
    file_content = providers.generate_journal_paie_export(
        company_id, request.period, request.employee_ids, request.format
    )
    period_formatted = request.period.replace("-", "_")
    extension = request.format
    timestamp = int(time.time())
    filename = f"journal_paie_{period_formatted}_{timestamp}.{extension}"
    storage_path = f"exports/{company_id}/{request.export_type}/{filename}"
    final_storage_path = upload_export_file(
        BUCKET, storage_path, file_content, _content_type(extension)
    )
    signed_url = create_signed_url(storage_path, 3600)

    _, totals = providers.get_journal_paie_data(
        company_id, request.period, request.employee_ids
    )
    parameters = {"employee_ids": request.employee_ids, "filters": request.filters}
    export_record: ExportRecordForInsert = {
        "company_id": company_id,
        "export_type": request.export_type,
        "period": request.period,
        "parameters": parameters,
        "file_paths": [final_storage_path],
        "report": {
            "employees_count": totals.get("employees_count", 0),
            "totals": totals,
            "anomalies": [],
            "warnings": [],
        },
        "status": "generated",
        "generated_by": user_id,
    }
    export_id = commands.record_export_history(export_record)

    return ExportGenerateResponse(
        export_id=export_id,
        export_type=request.export_type,
        period=request.period,
        status="generated",
        files=[
            ExportFileInfo(
                filename=filename,
                path=final_storage_path,
                size=len(file_content),
                format=request.format,
            )
        ],
        report=ExportReport(
            export_type=request.export_type,
            period=request.period,
            generated_at=datetime.now(),
            generated_by=user_name,
            employees_count=totals.get("employees_count", 0),
            totals=ExportTotals(**totals),
            anomalies=[],
            warnings=[],
            parameters=parameters,
        ),
        download_urls={filename: signed_url},
    )


def _generate_od(
    company_id: str,
    user_id: str,
    user_name: str,
    request: ExportGenerateRequest,
) -> ExportGenerateResponse:
    date_ecriture = request.filters.get("date_ecriture") if request.filters else None
    if request.export_type == "od_salaires":
        ecritures, od_totals, mappings = providers.generate_od_salaires(
            company_id, request.period, request.employee_ids, date_ecriture
        )
    elif request.export_type == "od_charges_sociales":
        ecritures, od_totals, mappings = providers.generate_od_charges_sociales(
            company_id, request.period, request.employee_ids, date_ecriture
        )
    elif request.export_type == "od_pas":
        ecritures, od_totals, mappings = providers.generate_od_pas(
            company_id, request.period, request.employee_ids, date_ecriture
        )
    else:
        ecritures, od_totals, mappings = providers.generate_od_salaires(
            company_id, request.period, request.employee_ids, date_ecriture
        )

    file_content = providers.generate_od_export_file(
        ecritures, request.export_type, request.period, request.format
    )
    period_formatted = request.period.replace("-", "_")
    type_label = {
        "od_salaires": "od_salaires",
        "od_charges_sociales": "od_charges",
        "od_pas": "od_pas",
        "od_globale": "od_globale",
    }.get(request.export_type, "od")
    filename = f"{type_label}_{period_formatted}.{request.format}"
    storage_path = f"exports/{company_id}/{request.export_type}/{filename}"
    final_storage_path = upload_export_file(
        BUCKET, storage_path, file_content, _content_type(request.format)
    )
    signed_url = create_signed_url(final_storage_path, 3600)

    parameters = {
        "employee_ids": request.employee_ids,
        "filters": request.filters,
        "date_ecriture": date_ecriture,
    }
    anomalies_list: List[Dict[str, Any]] = []
    warnings_list: List[str] = []
    if not od_totals["equilibre"]:
        anomalies_list.append(
            {
                "type": "error",
                "message": f"OD non équilibrée: écart de {od_totals['ecart']:.2f}€",
                "severity": "blocking",
            }
        )
    export_record: ExportRecordForInsert = {
        "company_id": company_id,
        "export_type": request.export_type,
        "period": request.period,
        "parameters": parameters,
        "file_paths": [final_storage_path],
        "report": {
            "nombre_lignes": len(ecritures),
            "total_debit": od_totals["total_debit"],
            "total_credit": od_totals["total_credit"],
            "equilibre": od_totals["equilibre"],
            "ecart": od_totals["ecart"],
            "anomalies": anomalies_list,
            "warnings": warnings_list,
            "mapping_utilise": mappings,
        },
        "status": "generated",
        "generated_by": user_id,
    }
    export_id = commands.record_export_history(export_record)
    totals_export = ExportTotals(
        employees_count=0, total_amount=od_totals["total_debit"]
    )

    return ExportGenerateResponse(
        export_id=export_id,
        export_type=request.export_type,
        period=request.period,
        status="generated",
        files=[
            ExportFileInfo(
                filename=filename,
                path=final_storage_path,
                size=len(file_content),
                format=request.format,
            )
        ],
        report=ExportReport(
            export_type=request.export_type,
            period=request.period,
            generated_at=datetime.now(),
            generated_by=user_name,
            employees_count=0,
            totals=totals_export,
            anomalies=[ExportAnomaly(**a) for a in anomalies_list],
            warnings=warnings_list,
            parameters=parameters,
        ),
        download_urls={filename: signed_url},
    )


def _generate_cabinet(
    company_id: str,
    user_id: str,
    user_name: str,
    request: ExportGenerateRequest,
) -> ExportGenerateResponse:
    if request.export_type == "export_cabinet_generique":
        file_content = providers.generate_cabinet_generic_export(
            company_id, request.period, request.employee_ids, request.format
        )
    elif request.export_type == "export_cabinet_quadra":
        file_content = providers.generate_cabinet_quadra_export(
            company_id, request.period, request.employee_ids, request.format
        )
    else:
        file_content = providers.generate_cabinet_sage_export(
            company_id, request.period, request.employee_ids, request.format
        )
    period_formatted = request.period.replace("-", "_")
    type_label = {
        "export_cabinet_generique": "cabinet_generique",
        "export_cabinet_quadra": "cabinet_quadra",
        "export_cabinet_sage": "cabinet_sage",
    }.get(request.export_type, "cabinet")
    filename = f"{type_label}_{period_formatted}.{request.format}"
    storage_path = f"exports/{company_id}/{request.export_type}/{filename}"
    final_storage_path = upload_export_file(
        BUCKET, storage_path, file_content, _content_type(request.format)
    )
    signed_url = create_signed_url(final_storage_path, 3600)

    _, totals = providers.get_payslip_data_for_od(
        company_id, request.period, request.employee_ids
    )
    parameters = {"employee_ids": request.employee_ids, "filters": request.filters}
    export_record: ExportRecordForInsert = {
        "company_id": company_id,
        "export_type": request.export_type,
        "period": request.period,
        "parameters": parameters,
        "file_paths": [final_storage_path],
        "report": {
            "employees_count": totals.get("employees_count", 0),
            "totals": totals,
            "anomalies": [],
            "warnings": [],
        },
        "status": "generated",
        "generated_by": user_id,
    }
    export_id = commands.record_export_history(export_record)

    return ExportGenerateResponse(
        export_id=export_id,
        export_type=request.export_type,
        period=request.period,
        status="generated",
        files=[
            ExportFileInfo(
                filename=filename,
                path=final_storage_path,
                size=len(file_content),
                format=request.format,
            )
        ],
        report=ExportReport(
            export_type=request.export_type,
            period=request.period,
            generated_at=datetime.now(),
            generated_by=user_name,
            employees_count=totals.get("employees_count", 0),
            totals=ExportTotals(**totals),
            anomalies=[],
            warnings=[],
            parameters=parameters,
        ),
        download_urls={filename: signed_url},
    )


def _generate_dsn(
    company_id: str,
    user_id: str,
    user_name: str,
    request: ExportGenerateRequest,
) -> DSNGenerateResponse:
    dsn_type = (
        request.filters.get("dsn_type", "dsn_mensuelle_normale")
        if request.filters
        else "dsn_mensuelle_normale"
    )
    establishment_id = (
        request.filters.get("establishment_id") if request.filters else None
    )
    preview_data = providers.preview_dsn(
        company_id, request.period, dsn_type, request.employee_ids, establishment_id
    )
    accept_warnings = bool(
        request.filters.get("accept_warnings", False) if request.filters else False
    )
    domain_rules.validate_dsn_can_generate(preview_data, accept_warnings)

    dsn_xml_content = providers.generate_dsn_xml(
        company_id, request.period, dsn_type, request.employee_ids, establishment_id
    )
    if isinstance(dsn_xml_content, str):
        dsn_xml_content = dsn_xml_content.encode("utf-8")

    period_formatted = request.period.replace("-", "_")
    filename = f"dsn_mensuelle_{period_formatted}.xml"
    storage_path = f"exports/{company_id}/{request.export_type}/{filename}"
    final_storage_path = upload_export_file(
        BUCKET, storage_path, dsn_xml_content, "application/xml"
    )
    signed_url = create_signed_url(final_storage_path, 3600)

    company_data = providers.get_company_data(company_id)
    _, totals = providers.get_dsn_employees_data(
        company_id, request.period, request.employee_ids
    )
    parameters = {
        "employee_ids": request.employee_ids,
        "filters": request.filters,
        "dsn_type": dsn_type,
        "establishment_id": establishment_id,
    }
    dsn_report = DSNReport(
        period=request.period,
        dsn_type=parameters["dsn_type"],
        establishment_siret=company_data.get("siret"),
        nombre_salaries=totals["nombre_salaries"],
        totaux_financiers={
            "masse_salariale_brute": totals["masse_salariale_brute"],
            "total_charges": totals["total_charges"],
            "total_net_imposable": totals["total_net_imposable"],
            "total_pas": totals["total_pas"],
        },
        controles=[ExportAnomaly(**a) for a in preview_data["anomalies"]],
        avertissements_acceptes=preview_data["warnings"]
        if request.filters.get("accept_warnings", False)
        else [],
        utilisateur_generateur=user_name,
        date_generation=datetime.now(),
        version_norme_dsn="V01",
    )
    export_record: ExportRecordForInsert = {
        "company_id": company_id,
        "export_type": request.export_type,
        "period": request.period,
        "parameters": parameters,
        "file_paths": [final_storage_path],
        "report": {
            "nombre_salaries": totals["nombre_salaries"],
            "totaux_financiers": dsn_report.totaux_financiers,
            "controles": [
                (a.model_dump() if hasattr(a, "model_dump") else a.dict())
                for a in dsn_report.controles
            ],
            "avertissements_acceptes": dsn_report.avertissements_acceptes,
            "version_norme_dsn": dsn_report.version_norme_dsn,
        },
        "status": "generated",
        "generated_by": user_id,
    }
    export_id = commands.record_export_history(export_record)

    return DSNGenerateResponse(
        export_id=export_id,
        period=request.period,
        status="generated",
        files=[
            ExportFileInfo(
                filename=filename,
                path=final_storage_path,
                size=len(dsn_xml_content),
                format="xml",
            )
        ],
        report=dsn_report,
        download_urls={filename: signed_url},
        message_teletransmission="Ce fichier doit être télétransmis manuellement sur net-entreprises.fr",
    )


def _generate_virement_salaires(
    company_id: str,
    user_id: str,
    user_name: str,
    request: ExportGenerateRequest,
) -> ExportGenerateResponse:
    file_content = providers.generate_paiement_salaires_export(
        company_id,
        request.period,
        request.employee_ids,
        request.excluded_employee_ids,
        request.execution_date,
        request.payment_label,
        request.format,
    )
    bank_file_content = providers.generate_bank_file(
        company_id,
        request.period,
        request.employee_ids,
        request.excluded_employee_ids,
        request.execution_date,
        request.payment_label,
    )
    period_formatted = request.period.replace("-", "_")
    filename = f"virement_salaires_{period_formatted}.{request.format}"
    bank_filename = f"virement_salaires_bancaire_{period_formatted}.csv"
    storage_path = f"exports/{company_id}/{request.export_type}/{filename}"
    bank_storage_path = f"exports/{company_id}/{request.export_type}/{bank_filename}"
    final_storage_path = upload_export_file(
        BUCKET, storage_path, file_content, _content_type(request.format)
    )
    final_bank_storage_path = upload_export_file(
        BUCKET, bank_storage_path, bank_file_content, "text/csv"
    )
    signed_url = create_signed_url(final_storage_path, 3600)
    bank_signed_url = create_signed_url(final_bank_storage_path, 3600)

    _, totals, anomalies, warnings = providers.get_paiement_salaires_data(
        company_id,
        request.period,
        request.employee_ids,
        request.excluded_employee_ids,
        request.execution_date,
        request.payment_label,
    )
    parameters = {
        "employee_ids": request.employee_ids,
        "excluded_employee_ids": request.excluded_employee_ids,
        "execution_date": request.execution_date,
        "payment_label": request.payment_label,
        "filters": request.filters,
    }
    export_record: ExportRecordForInsert = {
        "company_id": company_id,
        "export_type": request.export_type,
        "period": request.period,
        "parameters": parameters,
        "file_paths": [final_storage_path, final_bank_storage_path],
        "report": {
            "employees_count": totals.get(
                "employees_count", totals.get("virements_count", 0)
            ),
            "totals": totals,
            "anomalies": [a for a in anomalies],
            "warnings": warnings,
        },
        "status": "generated",
        "generated_by": user_id,
    }
    export_id = commands.record_export_history(export_record)
    files_list = [
        ExportFileInfo(
            filename=filename,
            path=storage_path,
            size=len(file_content),
            format=request.format,
        ),
        ExportFileInfo(
            filename=bank_filename,
            path=final_bank_storage_path,
            size=len(bank_file_content),
            format="csv",
        ),
    ]
    download_urls = {filename: signed_url, bank_filename: bank_signed_url}
    return ExportGenerateResponse(
        export_id=export_id,
        export_type=request.export_type,
        period=request.period,
        status="generated",
        files=files_list,
        report=ExportReport(
            export_type=request.export_type,
            period=request.period,
            generated_at=datetime.now(),
            generated_by=user_name,
            employees_count=totals.get(
                "employees_count", totals.get("virements_count", 0)
            ),
            totals=ExportTotals(**totals),
            anomalies=[ExportAnomaly(**a) for a in anomalies],
            warnings=warnings,
            parameters=parameters,
        ),
        download_urls=download_urls,
    )
