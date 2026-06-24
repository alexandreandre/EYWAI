"""Commit idempotent d'un batch d'import DSN."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.company_groups.infrastructure.repository import CompanyGroupRepository
from app.modules.dsn_import.application.cumuls import (
    rebuild_cumuls_with_previous_on_disk,
    write_cumuls_file,
)
from app.modules.dsn_import.domain.user_messages import humanize_commit_error, issue_to_legacy_string
from app.modules.dsn_import.application.mapping import normalize_employee_edits
from app.modules.dsn_import.domain.establishment_extract import apply_payroll_merge
from app.modules.dsn_import.application.psc_catalog import sync_employee_psc_catalog
from app.modules.dsn_import.application.coverage import _periods_from_batch
from app.modules.dsn_import.infrastructure import repository as repo
from app.modules.employees.application.commands import create_employee_imported, update_employee
from app.modules.employees.infrastructure.repository import EmployeeRepository

logger = get_logger("modules.dsn_import.commit")

_group_repo = CompanyGroupRepository()
_employee_repo = EmployeeRepository()


def _patch_contract_end_date_on_skip(
    payload: Dict[str, Any],
    emp_row: Dict[str, Any],
) -> None:
    """Met à jour contract_end_date depuis la DSN sans toucher employment_status."""
    end_date = payload.get("contract_end_date")
    if not end_date:
        return
    employee_id = str(emp_row.get("id") or "")
    if not employee_id:
        return
    existing_end = emp_row.get("contract_end_date")
    if existing_end and str(existing_end)[:10] == str(end_date)[:10]:
        return
    update_employee(employee_id, {"contract_end_date": end_date})


def _apply_workforce_resolutions(
    resolutions: List[Dict[str, Any]],
    company_id: str,
    current_user_id: Optional[str],
) -> Dict[str, Any]:
    """Applique les décisions de réconciliation effectifs post-import."""
    report: Dict[str, Any] = {
        "closed": [],
        "ignored": [],
        "open_exit_deferred": [],
        "acknowledged_new_hires": [],
        "deleted": [],
    }
    if not resolutions or not company_id:
        return report

    from app.modules.employee_exits.application.commands import create_reconciliation_exit

    user_id = current_user_id or "dsn-import-system"

    for res in resolutions:
        gap_id = str(res.get("gap_id") or "")
        action = res.get("action")
        employee_id = str(res.get("employee_id") or "")
        if not gap_id or not employee_id:
            continue
        if action == "ignore":
            report["ignored"].append(
                {
                    "gap_id": gap_id,
                    "employee_id": employee_id,
                    "ignore_reason": res.get("ignore_reason"),
                }
            )
            continue
        if action == "acknowledge_new_hire":
            report["acknowledged_new_hires"].append(
                {
                    "gap_id": gap_id,
                    "employee_id": employee_id,
                    "hire_date": res.get("hire_date"),
                }
            )
            continue
        if action == "open_exit":
            report["open_exit_deferred"].append(
                {
                    "gap_id": gap_id,
                    "employee_id": employee_id,
                    "exit_type": res.get("exit_type") or "demission",
                    "last_working_day": res.get("last_working_day"),
                }
            )
            continue
        if action == "delete_permanently":
            from app.modules.employees.application.commands import delete_employee

            try:
                delete_employee(employee_id, company_id)
                report["deleted"].append(
                    {
                        "gap_id": gap_id,
                        "employee_id": employee_id,
                    }
                )
            except Exception as exc:
                detail = getattr(exc, "detail", str(exc))
                logger.exception(
                    "Suppression définitive réconciliation échouée pour %s",
                    employee_id,
                )
                report.setdefault("failed", []).append(
                    {
                        "gap_id": gap_id,
                        "employee_id": employee_id,
                        "error": str(detail),
                    }
                )
            continue
        if action == "close_departure":
            try:
                created = create_reconciliation_exit(
                    employee_id,
                    company_id,
                    user_id,
                    exit_type=str(res.get("exit_type") or "demission"),
                    last_working_day=res.get("last_working_day"),
                    exit_reason=res.get("exit_reason")
                    or f"Clôture réconciliation DSN ({gap_id})",
                    fast_archive=True,
                    source="dsn_reconciliation",
                )
                report["closed"].append(
                    {
                        "gap_id": gap_id,
                        "employee_id": employee_id,
                        "exit_id": str(created.get("id", "")),
                    }
                )
            except Exception as exc:
                logger.exception("Clôture réconciliation échouée pour %s", employee_id)
                report.setdefault("failed", []).append(
                    {
                        "gap_id": gap_id,
                        "employee_id": employee_id,
                        "error": str(exc),
                    }
                )
    return report

PHASE_LABELS = {
    "group": "Création du groupe",
    "establishment": "Création de l'entreprise",
    "collective_agreement": "Conventions collectives",
    "exit": "Sorties historiques",
    "employee": "Import des salariés",
    "absence": "Absences historiques",
    "cumul": "Reconstruction des cumuls",
    "done": "Finalisation",
}


def _phase_label(item_type: Optional[str]) -> str:
    return PHASE_LABELS.get(item_type or "", "Traitement")


def _company_id_for_siret(
    siret: str,
    company_by_siret: Dict[str, str],
) -> Optional[str]:
    company_id = company_by_siret.get(siret)
    if company_id:
        return company_id
    existing_co = repo.find_company_by_siret(siret)
    return str(existing_co["id"]) if existing_co else None


def _resolve_employee_row(
    company_id: Optional[str],
    nir: Optional[str],
    source_ref: str,
    payload: Dict[str, Any],
    employee_by_ref: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    emp: Optional[Dict[str, Any]] = None
    if company_id and nir:
        emp = repo.find_employee_by_nir(company_id, nir)
    if not emp and nir:
        emp = repo.find_employee_by_nir_global(nir)
    if not emp:
        parts = source_ref.split(":")
        siret = parts[1] if len(parts) > 1 else payload.get("siret", "")
        emp_key = payload.get("employee_key") or nir
        if siret and emp_key:
            emp = employee_by_ref.get(f"emp:{siret}:{emp_key}")
    return emp


def _item_label(item: Optional[Dict[str, Any]]) -> Optional[str]:
    if not item:
        return None
    payload = item.get("mapped_payload") or {}
    item_type = item.get("item_type")
    if item_type == "group":
        return payload.get("group_name") or "Groupe"
    if item_type == "establishment":
        return payload.get("company_name") or payload.get("raison_sociale") or "Entreprise"
    if item_type == "employee":
        name = f"{payload.get('first_name', '')} {payload.get('last_name', '')}".strip()
        return name or "Salarié"
    if item_type == "collective_agreement":
        return f"IDCC {payload.get('idcc', '')}".strip()
    if item_type == "cumul":
        return f"Cumuls {payload.get('period', '')}".strip()
    if item_type == "exit":
        return f"Sortie {payload.get('employee_label', '')}".strip()
    if item_type == "absence":
        return f"Absence {payload.get('employee_label', '')}".strip()
    return item.get("source_ref")


def commit_batch(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
    target_company_id: Optional[str] = None,
    workforce_resolutions: Optional[List[Dict[str, Any]]] = None,
    current_user_id: Optional[str] = None,
    remove_orphan_imported_employees: bool = False,
) -> Dict[str, Any]:
    """
    Exécute le commit d'un batch previewed.
    overrides : {source_ref: action} où action in create|update|skip
    payload_edits : {source_ref: {champ: valeur}} modifications utilisateur
    target_company_id : rattachement manuel à une entreprise existante. Si
        fourni, l'import est attaché à cette entreprise (et son groupe) au lieu
        de créer/résoudre une entreprise via le SIRET de la DSN.
    """
    batch = repo.get_batch(batch_id)
    if not batch:
        raise LookupError("Batch introuvable")
    if batch.get("status") == "committed":
        raise ValueError("Ce batch a déjà été validé")

    items = repo.list_items(batch_id)
    overrides = overrides or {}
    payload_edits = payload_edits or {}

    # Rattachement manuel : on résout l'entreprise cible une seule fois.
    target_company = (
        repo.find_company_by_id(target_company_id) if target_company_id else None
    )
    if target_company_id and not target_company:
        raise ValueError("Entreprise de rattachement introuvable")
    target_cid = str(target_company["id"]) if target_company else None
    target_group_id = (
        str(target_company["group_id"])
        if target_company and target_company.get("group_id")
        else None
    )

    # Index résolutions
    group_id: Optional[str] = target_group_id
    company_by_siret: Dict[str, str] = {}
    employee_by_ref: Dict[str, Dict[str, Any]] = {}
    stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
    errors: List[Dict[str, Any]] = []
    error_messages: List[str] = []
    imported_employees: List[Dict[str, Any]] = []
    periods_committed: set = set()
    dsn_import_stats = {
        "exits_created": 0,
        "absences_created": 0,
        "payroll_fields_applied": 0,
    }

    ordered_types = [
        "group",
        "establishment",
        "collective_agreement",
        "employee",
        "exit",
        "absence",
        "cumul",
    ]
    items_sorted = sorted(
        items,
        key=lambda i: ordered_types.index(i.get("item_type", "employee"))
        if i.get("item_type") in ordered_types
        else 99,
    )

    # Suivi de progression : publié dans batch.summary.commit_progress, lu par le front.
    total = len(items_sorted)
    summary_state: Dict[str, Any] = dict(batch.get("summary") or {})
    emit_every = max(1, total // 25)
    last_phase: Optional[str] = None

    def emit_progress(done: int, item: Optional[Dict[str, Any]], force: bool = False) -> None:
        nonlocal last_phase
        phase = item.get("item_type") if item else "done"
        phase_changed = phase != last_phase
        if not force and not phase_changed and done % emit_every != 0:
            return
        last_phase = phase
        percent = 100 if total == 0 else min(100, round(done / total * 100))
        summary_state["commit_progress"] = {
            "done": done,
            "total": total,
            "percent": percent,
            "phase": phase,
            "phase_label": _phase_label(phase),
            "label": _item_label(item),
        }
        repo.update_batch(batch_id, {"summary": summary_state})

    for idx, item in enumerate(items_sorted):
        emit_progress(idx, item)
        item_id = str(item["id"])
        source_ref = item.get("source_ref", "")
        action = overrides.get(source_ref, item.get("action", "create"))
        if action == "skip":
            if item.get("item_type") == "employee":
                payload = dict(item.get("mapped_payload") or {})
                parts = source_ref.split(":")
                siret = parts[1] if len(parts) > 1 else ""
                cid = _company_id_for_siret(siret, company_by_siret)
                emp_row = _resolve_employee_row(
                    cid, payload.get("nir"), source_ref, payload, employee_by_ref
                )
                if emp_row:
                    employee_by_ref[source_ref] = emp_row
                    _patch_contract_end_date_on_skip(payload, emp_row)
            repo.update_item(item_id, {"status": "skipped", "action": "skip"})
            stats["skipped"] += 1
            continue

        item_type = item.get("item_type")
        payload = dict(item.get("mapped_payload") or {})
        edits = payload_edits.get(source_ref) or {}
        if edits:
            if item_type == "employee":
                edits = normalize_employee_edits(edits)
            payload.update(edits)
            if item_type == "establishment" and edits.get("company_name"):
                payload["raison_sociale"] = edits["company_name"]
            if item_type == "employee":
                if edits.get("last_name") or edits.get("first_name"):
                    payload["_label_override"] = True

        try:
            target_id = None
            if item_type == "group":
                if target_company is not None or payload.get("_scaffold"):
                    # Rattachement ou mono-établissement : pas de conteneur groupe.
                    target_id = target_group_id if target_company is not None else None
                    group_id = target_group_id if target_company is not None else None
                    action = "skip"
                    stats["skipped"] += 1
                else:
                    target_id, created = _commit_group(payload, action)
                    stats["created" if created else "updated"] += 1
                    group_id = target_id
            elif item_type == "establishment":
                apply_fields = set(edits.keys()) if edits else None
                existing_co = (
                    target_company
                    if target_company is not None
                    else repo.find_company_by_siret(payload.get("siret", ""))
                )
                payload = apply_payroll_merge(payload, existing_co, apply_fields)
                if target_company is not None:
                    target_id = target_cid
                    if payload.get("siret"):
                        company_by_siret[payload["siret"]] = target_cid
                    if payload:
                        _commit_establishment_payroll_fields(
                            target_cid, payload, existing_co
                        )
                        dsn_import_stats["payroll_fields_applied"] += 1
                    action = "update"
                    stats["updated"] += 1
                else:
                    target_id, created = _commit_establishment(
                        payload, group_id, action, existing_co
                    )
                    stats["created" if created else "updated"] += 1
                    if payload.get("siret"):
                        company_by_siret[payload["siret"]] = target_id
                    if payload.get("taux_at_mp") is not None:
                        dsn_import_stats["payroll_fields_applied"] += 1
            elif item_type == "exit":
                _commit_exit(
                    payload,
                    source_ref,
                    company_by_siret,
                    employee_by_ref,
                    current_user_id,
                )
                dsn_import_stats["exits_created"] += 1
                stats["created"] += 1
            elif item_type == "absence":
                _commit_absence(
                    payload,
                    source_ref,
                    company_by_siret,
                    employee_by_ref,
                    current_user_id,
                )
                dsn_import_stats["absences_created"] += 1
                stats["created"] += 1
            elif item_type == "collective_agreement":
                _commit_collective_agreement(payload, company_by_siret)
                stats["updated"] += 1
            elif item_type == "employee":
                target_id, created, emp_row = _commit_employee(
                    payload, source_ref, company_by_siret, action
                )
                stats["created" if created else "updated"] += 1
                employee_by_ref[source_ref] = emp_row or {}
                if target_id and emp_row and created and not emp_row.get("user_id"):
                    imported_employees.append(
                        {
                            "employee_id": target_id,
                            "company_id": str(emp_row.get("company_id", "")),
                            "full_name": (
                                f"{emp_row.get('first_name', '')} {emp_row.get('last_name', '')}"
                            ).strip(),
                            "placeholder_email": emp_row.get("email"),
                            "employment_status": emp_row.get("employment_status"),
                        }
                    )
            elif item_type == "cumul":
                _commit_cumul(payload, company_by_siret, employee_by_ref)
                period = payload.get("period")
                if period:
                    periods_committed.add(str(period))
                stats["updated"] += 1

            repo.update_item(
                item_id,
                {
                    "status": "skipped" if action == "skip" else "committed",
                    "action": action,
                    "target_id": target_id,
                },
            )
        except Exception as exc:
            logger.exception("Commit item %s échoué", source_ref)
            issue = humanize_commit_error(
                exc,
                source_ref=source_ref,
                item_label=_item_label(item),
            )
            errors.append(issue)
            error_messages.append(issue_to_legacy_string(issue))
            repo.update_item(item_id, {"status": "failed"})
            stats["failed"] += 1

    status = "committed" if not errors else "failed"
    import_mode = summary_state.get("import_mode")
    workforce_report: Dict[str, Any] = {}
    resolution_company_id = target_cid or (
        str(next(iter(company_by_siret.values()))) if company_by_siret else None
    )
    if status == "committed" and workforce_resolutions and resolution_company_id:
        workforce_report = _apply_workforce_resolutions(
            workforce_resolutions,
            resolution_company_id,
            current_user_id,
        )
    orphan_removal_report: Dict[str, Any] = {}
    if (
        status == "committed"
        and remove_orphan_imported_employees
        and (import_mode or "").strip().lower() == "monthly"
        and resolution_company_id
    ):
        from app.modules.dsn_import.application.orphan_employees import remove_reimport_orphans

        orphan_removal_report = remove_reimport_orphans(items, str(resolution_company_id))
    report = {
        "stats": stats,
        "errors": errors,
        "error_messages": error_messages,
        "group_id": group_id,
        "companies": company_by_siret,
        "imported_employees": imported_employees,
        "target_company_id": target_cid,
        "workforce_reconciliation": workforce_report,
        "orphan_removal": orphan_removal_report,
        "dsn_import_stats": dsn_import_stats,
    }
    summary_state["commit_report"] = report
    summary_state["periods_committed"] = sorted(periods_committed)
    if import_mode:
        summary_state["import_mode"] = import_mode
    summary_state["commit_progress"] = {
        "done": total,
        "total": total,
        "percent": 100,
        "phase": "done",
        "phase_label": "Terminé",
        "label": None,
    }
    repo.update_batch(
        batch_id,
        {"status": status, "summary": summary_state},
    )
    if status == "committed":
        _mark_companies_dsn_transition(set(company_by_siret.values()), target_cid)
        if (import_mode or "").strip().lower() == "onboarding":
            _bootstrap_leave_settings_for_companies(
                set(company_by_siret.values()), target_cid
            )
        if resolution_company_id:
            periods_to_clear = sorted(
                _periods_from_batch(
                    {
                        "period_min": batch.get("period_min"),
                        "period_max": batch.get("period_max"),
                        "summary": summary_state,
                    }
                )
            )
            if periods_to_clear:
                repo.clear_period_revocations(
                    str(resolution_company_id),
                    periods_to_clear,
                )
    return report


def _bootstrap_leave_settings_for_companies(
    company_ids: set, target_cid: Optional[str]
) -> None:
    """Crée les paramètres congés par défaut si absents (onboarding)."""
    from app.modules.absences.domain.ccn_setup_presets import get_leave_preset_for_idcc
    from app.modules.absences.infrastructure.leave_settings_repository import upsert_leave_policy

    ids = {str(cid) for cid in company_ids if cid}
    if target_cid:
        ids.add(str(target_cid))
    client = get_supabase_admin_client()
    for cid in ids:
        try:
            existing = (
                client.table("company_leave_settings")
                .select("id")
                .eq("company_id", cid)
                .limit(1)
                .execute()
            )
            if existing.data:
                continue
            co = repo.find_company_by_id(cid)
            idcc = co.get("idcc") if co else None
            preset = get_leave_preset_for_idcc(idcc)
            upsert_leave_policy(cid, preset)
        except Exception:
            logger.exception("Bootstrap leave_settings entreprise %s échoué", cid)


def _mark_companies_dsn_transition(company_ids: set, target_cid: Optional[str]) -> None:
    """Passe en transition les entreprises qui reçoivent un import DSN (historique visible)."""
    ids = {str(cid) for cid in company_ids if cid}
    if target_cid:
        ids.add(str(target_cid))
    for cid in ids:
        try:
            repo.update_company_dsn_sync_mode_if_native(cid, "transition")
        except Exception:
            logger.exception("MAJ dsn_sync_mode entreprise %s échouée", cid)


def _commit_group(payload: Dict[str, Any], action: str) -> tuple[str, bool]:
    siren = payload.get("siren", "")
    existing = repo.find_group_by_siren(siren)
    if existing and action in ("create", "update"):
        gid = str(existing["id"])
        if action == "update":
            _group_repo.update(gid, {
                k: payload[k]
                for k in ("group_name", "siren", "description")
                if k in payload and payload[k]
            })
        return gid, False
    if existing:
        return str(existing["id"]), False

    row = _group_repo.create(
        {
            "group_name": payload.get("group_name") or f"Groupe {siren}",
            "siren": siren,
            "description": payload.get("description"),
            "is_active": True,
        }
    )
    if not row:
        raise RuntimeError("Création du groupe échouée")
    return str(row["id"]), True


def _commit_establishment_payroll_fields(
    company_id: str,
    payload: Dict[str, Any],
    existing: Optional[Dict[str, Any]],
) -> None:
    """Applique uniquement les champs paie extraits DSN (merge non destructif)."""
    client = get_supabase_admin_client()
    update_data: Dict[str, Any] = {}
    for field in ("taux_at_mp", "paie_jour_de_fin", "paie_occurrence", "effectif"):
        val = payload.get(field)
        if val is None:
            continue
        if existing and existing.get(field) not in (None, ""):
            continue
        update_data[field] = val

    settings_patch: Dict[str, Any] = {}
    if payload.get("dsn_organismes"):
        settings_patch["organismes"] = payload["dsn_organismes"]
    if payload.get("dsn_bordereaux"):
        settings_patch["bordereaux"] = payload["dsn_bordereaux"]
    if settings_patch:
        current_settings = (existing or {}).get("settings") or {}
        if not isinstance(current_settings, dict):
            current_settings = {}
        dsn_meta = dict(current_settings.get("dsn_import") or {})
        dsn_meta.update(settings_patch)
        merged_settings = {**current_settings, "dsn_import": dsn_meta}
        update_data["settings"] = merged_settings

    if update_data:
        client.table("companies").update(update_data).eq("id", company_id).execute()


def _commit_establishment(
    payload: Dict[str, Any],
    group_id: Optional[str],
    action: str,
    existing: Optional[Dict[str, Any]] = None,
) -> tuple[str, bool]:
    siret = payload.get("siret", "")
    existing = repo.find_company_by_siret(siret)
    client = get_supabase_admin_client()
    insert_data = {
        k: payload[k]
        for k in (
            "company_name",
            "raison_sociale",
            "siret",
            "siren",
            "code_naf",
            "naf_ape",
            "effectif",
            "address",
            "adresse_rue",
            "adresse_code_postal",
            "adresse_ville",
            "is_active",
            "taux_at_mp",
            "paie_jour_de_fin",
            "paie_occurrence",
        )
        if k in payload and payload[k] is not None
    }
    if group_id:
        insert_data["group_id"] = group_id

    if existing:
        cid = str(existing["id"])
        if action == "update":
            merge_payload = apply_payroll_merge(payload, existing)
            update_data = {
                k: merge_payload[k]
                for k in insert_data
                if k in merge_payload and merge_payload[k] is not None
            }
            if update_data:
                client.table("companies").update(update_data).eq("id", cid).execute()
            _commit_establishment_payroll_fields(cid, merge_payload, existing)
        elif group_id and not existing.get("group_id"):
            client.table("companies").update({"group_id": group_id}).eq("id", cid).execute()
        return cid, False

    insert_data.setdefault("is_active", True)
    insert_data.setdefault("dsn_sync_mode", "transition")
    settings_patch: Dict[str, Any] = {}
    if payload.get("dsn_organismes"):
        settings_patch["organismes"] = payload["dsn_organismes"]
    if payload.get("dsn_bordereaux"):
        settings_patch["bordereaux"] = payload["dsn_bordereaux"]
    if settings_patch:
        insert_data["settings"] = {"dsn_import": settings_patch}
    resp = client.table("companies").insert(insert_data).execute()
    if not resp.data:
        raise RuntimeError(f"Création entreprise {siret} échouée")
    return str(resp.data[0]["id"]), True


def _commit_collective_agreement(
    payload: Dict[str, Any], company_by_siret: Dict[str, str]
) -> None:
    siret = payload.get("siret", "")
    idcc = payload.get("idcc", "")
    company_id = company_by_siret.get(siret)
    if not company_id:
        existing = repo.find_company_by_siret(siret)
        company_id = str(existing["id"]) if existing else None
    if not company_id:
        raise RuntimeError(f"Entreprise {siret} introuvable pour IDCC {idcc}")
    agreement_id = repo.resolve_collective_agreement_id(idcc)
    if not agreement_id:
        logger.warning("IDCC %s absent du catalogue — assignation ignorée", idcc)
        return
    repo.upsert_company_collective_agreement(company_id, agreement_id)
    client = get_supabase_admin_client()
    client.table("companies").update({"idcc": idcc}).eq("id", company_id).execute()


def _commit_employee(
    payload: Dict[str, Any],
    source_ref: str,
    company_by_siret: Dict[str, str],
    action: str,
) -> tuple[Optional[str], bool, Optional[Dict[str, Any]]]:
    # source_ref = emp:{siret}:{nir}
    parts = source_ref.split(":")
    siret = parts[1] if len(parts) > 1 else ""
    company_id = company_by_siret.get(siret)
    if not company_id:
        existing_co = repo.find_company_by_siret(siret)
        company_id = str(existing_co["id"]) if existing_co else None
    if not company_id:
        raise RuntimeError(f"Établissement {siret} introuvable pour le salarié")

    nir = payload.get("nir")
    existing = _resolve_employee_row(company_id, nir, source_ref, payload, {})

    clean_payload = {
        k: v
        for k, v in payload.items()
        if not k.startswith("_")
        and k not in ("collective_agreement_idcc", "import_source", "ntt", "employee_key")
        and v is not None
    }

    # Colonnes optionnelles (état civil DSN) : on ne les envoie que si la migration
    # les a créées, sinon l'insert échouerait (column does not exist).
    for optional_col in ("sexe", "nom_usage", "matricule"):
        if optional_col in clean_payload and not repo.employee_has_column(optional_col):
            clean_payload.pop(optional_col, None)

    idcc = payload.get("collective_agreement_idcc")
    if idcc:
        agreement_id = repo.resolve_collective_agreement_id(idcc)
        if agreement_id:
            clean_payload["collective_agreement_id"] = agreement_id

    if existing:
        if str(existing.get("company_id")) != str(company_id):
            other_co = repo.find_company_by_id(str(existing["company_id"]))
            other_name = (other_co or {}).get("company_name") or "une autre entreprise"
            raise RuntimeError(
                f"NIR {nir} déjà enregistré chez {other_name} — "
                "ignorez ce salarié à l'import ou corrigez la fiche manuellement."
            )
        if action == "create":
            action = "update"
        # Ne jamais écraser le statut RH (en_sortie / parti) via l'import DSN.
        clean_payload.pop("employment_status", None)
        update_employee(str(existing["id"]), clean_payload)
        try:
            sync_employee_psc_catalog(company_id, str(existing["id"]), payload)
        except Exception:
            logger.exception("Sync PSC mutuelle échoué pour %s", existing["id"])
        return str(existing["id"]), False, existing

    row = create_employee_imported(clean_payload, company_id)
    try:
        sync_employee_psc_catalog(company_id, str(row["id"]), payload)
    except Exception:
        logger.exception("Sync PSC mutuelle échoué pour %s", row["id"])
    return str(row["id"]), True, row


def _resolve_employee_for_dsn_item(
    payload: Dict[str, Any],
    company_by_siret: Dict[str, str],
    employee_by_ref: Dict[str, Dict[str, Any]],
) -> tuple[Optional[str], Optional[str]]:
    siret = payload.get("siret", "")
    nir = payload.get("nir", "")
    company_id = company_by_siret.get(siret)
    if not company_id:
        co = repo.find_company_by_siret(siret)
        company_id = str(co["id"]) if co else None
    if not company_id:
        raise RuntimeError(f"Entreprise {siret} introuvable")

    emp = _resolve_employee_row(
        company_id,
        nir,
        f"emp:{siret}:{nir}",
        payload,
        employee_by_ref,
    )
    if not emp:
        raise RuntimeError(f"Salarié NIR {nir} introuvable pour {siret}")
    return str(emp["id"]), company_id


def _commit_exit(
    payload: Dict[str, Any],
    source_ref: str,
    company_by_siret: Dict[str, str],
    employee_by_ref: Dict[str, Dict[str, Any]],
    current_user_id: Optional[str],
) -> None:
    from app.modules.employee_exits.application.commands import create_reconciliation_exit

    employee_id, company_id = _resolve_employee_for_dsn_item(
        payload, company_by_siret, employee_by_ref
    )
    user_id = current_user_id or "dsn-import-system"
    create_reconciliation_exit(
        employee_id,
        company_id,
        user_id,
        exit_type=str(payload.get("exit_type") or "demission"),
        last_working_day=payload.get("last_working_day"),
        exit_reason=payload.get("exit_reason")
        or f"Import DSN ({payload.get('motif_dsn', '')})",
        fast_archive=True,
        source="dsn_reconciliation",
    )


def _commit_absence(
    payload: Dict[str, Any],
    source_ref: str,
    company_by_siret: Dict[str, str],
    employee_by_ref: Dict[str, Dict[str, Any]],
    current_user_id: Optional[str],
) -> None:
    from app.modules.absences.application.commands import create_reconciliation_absence

    employee_id, company_id = _resolve_employee_for_dsn_item(
        payload, company_by_siret, employee_by_ref
    )
    user_id = current_user_id or "dsn-import-system"
    create_reconciliation_absence(
        employee_id,
        company_id,
        user_id,
        absence_type=str(payload.get("absence_type") or "arret_maladie"),
        selected_days=payload.get("selected_days") or [],
        arret_type=payload.get("arret_type"),
        source="dsn_import",
    )


def _commit_cumul(
    payload: Dict[str, Any],
    company_by_siret: Dict[str, str],
    employee_by_ref: Dict[str, Dict[str, Any]],
) -> None:
    siret = payload.get("siret", "")
    nir = payload.get("nir", "")
    month = int(payload.get("month", 0))
    document = payload.get("cumuls_document") or {}

    company_id = company_by_siret.get(siret)
    if not company_id:
        co = repo.find_company_by_siret(siret)
        company_id = str(co["id"]) if co else None
    if not company_id:
        raise RuntimeError(f"Entreprise {siret} introuvable pour cumuls")

    emp = _resolve_employee_row(
        company_id,
        nir,
        f"emp:{siret}:{payload.get('employee_key') or nir}",
        payload,
        employee_by_ref,
    )
    if not emp or not emp.get("employee_folder_name"):
        raise RuntimeError(f"Salarié NIR {nir} introuvable pour cumuls")

    folder_name = str(emp["employee_folder_name"])
    month_totals = payload.get("month_totals") or {}
    document = rebuild_cumuls_with_previous_on_disk(
        folder_name, month, month_totals, document
    )
    write_cumuls_file(folder_name, month, document)
