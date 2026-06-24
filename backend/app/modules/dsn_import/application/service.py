"""Service applicatif import DSN."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.application.commit import commit_batch
from app.modules.dsn_import.application.cumuls import build_cumuls_summary, plan_cumul_items
from app.modules.dsn_import.application.mapping import (
    apply_legal_name_to_preview,
    apply_review_flags,
    build_preview_items,
    build_review_summary,
    enrich_summary_from_items,
    normalize_employee_edits,
)
from app.modules.dsn_import.application.workforce_reconciliation import (
    attach_workforce_reconciliation,
    resolve_monthly_target_company_id,
    validate_workforce_resolutions_for_commit,
    workforce_blocks_commit,
)
from app.modules.dsn_import.application.orphan_employees import attach_reimport_orphans
from app.modules.dsn_import.application.import_checks import (
    attach_import_context_warnings,
    strip_enrichment_warnings,
    strip_import_context_warnings,
)
from app.modules.dsn_import.domain.parser import parse_dsn_files
from app.modules.dsn_import.domain.user_messages import (
    employee_other_company_anomaly,
    parse_warning_anomaly,
    psc_warning_anomaly,
)
from app.modules.dsn_import.domain.validation import validate_parsed_dsn
from app.modules.dsn_import.infrastructure import repository as repo


def parse_and_stage(
    files: List[Tuple[str, bytes]],
    uploaded_by: str,
    *,
    import_mode: Optional[str] = None,
    target_company_id: Optional[str] = None,
    intended_period: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse les fichiers, construit preview, persiste batch + items."""
    parsed = parse_dsn_files(files)
    anomalies = validate_parsed_dsn(parsed)
    for warning in parsed.warnings or []:
        anomalies.append(parse_warning_anomaly(str(warning)))
    preview_items, summary = build_preview_items(parsed)
    cumul_items = plan_cumul_items(parsed)
    all_items = preview_items + cumul_items

    mode = (import_mode or "onboarding").strip().lower()
    if mode not in ("onboarding", "monthly"):
        mode = "onboarding"

    # Détection create vs update vs salariés déjà présents (best effort sans bloquer)
    _enrich_actions(all_items, target_company_id=target_company_id, anomalies=anomalies)
    _attach_psc_warnings(all_items, anomalies)

    summary = enrich_summary_from_items(summary, parsed, all_items)
    if parsed.warnings:
        summary["parse_warnings"] = [str(w) for w in parsed.warnings]
    summary.update(_employee_state_counts(all_items))
    summary["review_summary"] = build_review_summary(all_items)
    if target_company_id:
        summary["target_company_id"] = target_company_id

    periods = sorted(
        {
            str(it.get("mapped_payload", {}).get("period"))
            for it in cumul_items
            if it.get("mapped_payload", {}).get("period")
        }
    )
    summary["cumul_month_count"] = len(periods)
    summary["cumul_periods"] = periods
    summary["cumuls_summary"] = build_cumuls_summary(cumul_items)
    summary["import_mode"] = mode
    resolved_target = resolve_monthly_target_company_id(mode, target_company_id, summary)
    if resolved_target:
        summary["target_company_id"] = resolved_target
        target_company_id = resolved_target

    attach_workforce_reconciliation(
        all_items,
        summary,
        anomalies,
        target_company_id=target_company_id,
        import_mode=mode,
    )
    attach_reimport_orphans(
        all_items,
        summary,
        target_company_id=target_company_id,
        import_mode=mode,
    )

    from app.modules.dsn_import.application.mapping import _find_raison_sociale

    dsn_company_name = _find_raison_sociale(parsed)
    if dsn_company_name:
        summary["dsn_company_name"] = dsn_company_name
    if intended_period:
        summary["intended_period"] = intended_period

    _attach_import_warnings(
        anomalies,
        summary,
        mode=mode,
        target_company_id=target_company_id,
        periods=periods,
    )
    attach_import_context_warnings(
        anomalies,
        summary,
        mode=mode,
        target_company_id=target_company_id,
        periods=periods,
        dsn_company_name=dsn_company_name,
        intended_period=intended_period,
    )

    suggested_name = None
    etab_count = summary.get("establishment_count") or 0
    if siren := parsed.siren:
        from app.modules.dsn_import.application.siren_lookup import lookup_company_name_by_siren

        suggested_name = lookup_company_name_by_siren(siren)
        if suggested_name:
            summary["suggested_company_name"] = suggested_name
            apply_legal_name_to_preview(
                all_items,
            suggested_name,
            single_establishment=etab_count == 1,
        )

    can_commit = not any(a.get("severity") == "blocking" for a in anomalies)
    if workforce_blocks_commit(summary):
        can_commit = False

    file_names = [name for name, _ in files]
    batch_id = repo.insert_batch(
        {
            "uploaded_by": uploaded_by,
            "file_names": file_names,
            "siren": parsed.siren,
            "period_min": parsed.period_min,
            "period_max": parsed.period_max,
            "status": "previewed",
            "summary": summary,
            "preview": {
                "anomalies": anomalies,
                "can_commit": can_commit,
                # Snapshot enrichi pour restaurer l'écran preview après un rechargement.
                "items": all_items,
            },
        }
    )
    if not batch_id:
        raise RuntimeError("Impossible de créer le batch d'import")

    db_items = [
        {
            "batch_id": batch_id,
            "item_type": it["item_type"],
            "source_ref": it["source_ref"],
            "action": it.get("action", "create"),
            "mapped_payload": it.get("mapped_payload", {}),
            "anomalies": it.get("anomalies", []),
            "status": "pending",
        }
        for it in all_items
    ]
    repo.insert_items(db_items)

    return {
        "batch_id": batch_id,
        "summary": summary,
        "anomalies": anomalies,
        "items": all_items,
        "can_commit": can_commit,
    }


def _attach_import_warnings(
    anomalies: List[Dict[str, Any]],
    summary: Dict[str, Any],
    *,
    mode: str,
    target_company_id: Optional[str],
    periods: List[str],
) -> None:
    """Ajoute avertissements onboarding / doublon période / chaînage cumuls."""
    from datetime import date

    if mode == "onboarding" and len(periods) == 1 and date.today().month > 3:
        anomalies.append(
            {
                "type": "onboarding_single_month",
                "message": (
                    "Un seul mois détecté en mode onboarding — pour des cumuls fiables, "
                    "importez janvier → dernier mois clos en une fois."
                ),
                "severity": "warning",
            }
        )

    company_id = target_company_id
    if not company_id:
        sirets = summary.get("sirets") or []
        siret = summary.get("siret") or (sirets[0] if sirets else None)
        if siret:
            co = repo.find_company_by_siret(str(siret))
            company_id = str(co["id"]) if co else None

    if not company_id or not periods:
        return

    company = repo.find_company_by_id(company_id)
    if not company:
        return

    from app.modules.dsn_import.application.coverage import compute_coverage

    cov = compute_coverage(company)
    covered = set(cov.get("months_covered") or [])
    dupes = [p for p in periods if p in covered]
    if dupes:
        summary["duplicate_periods"] = dupes
        anomalies.append(
            {
                "type": "duplicate_period",
                "message": (
                    f"Période(s) déjà importée(s) : {', '.join(dupes)}. "
                    "Confirmez « Remplacer » à la validation si vous souhaitez écraser les cumuls."
                ),
                "severity": "warning",
            }
        )

    if mode == "monthly" and len(periods) == 1:
        period = periods[0]
        try:
            y, m = period.split("-")
            mi = int(m)
            prev_m = mi - 1 if mi > 1 else 12
            prev_period = f"{int(y) - (1 if mi == 1 else 0)}-{prev_m:02d}"
        except ValueError:
            prev_period = None
        if prev_period and prev_period not in covered and mi > 1:
            summary["cumul_chain_warning"] = True
            anomalies.append(
                {
                    "type": "cumul_chain",
                    "message": (
                        f"Le mois précédent ({prev_period}) n'est pas importé — "
                        "les cumuls YTD seront chaînés depuis le disque si disponibles, "
                        "sinon importez les mois manquants en lot."
                    ),
                    "severity": "warning",
                }
            )


def _attach_psc_warnings(items: List[Dict[str, Any]], anomalies: List[Dict[str, Any]]) -> None:
    """Expose les avertissements PSC mutuelle/prévoyance issus du mapping DSN."""
    for it in items:
        if it.get("item_type") != "employee":
            continue
        payload = it.get("mapped_payload") or {}
        psc_meta = payload.get("_psc_meta") or {}
        warnings = psc_meta.get("warnings") or []
        if not warnings:
            continue
        label = it.get("label") or "Salarié"
        source_ref = it.get("source_ref") or ""
        for warning in warnings:
            anomalies.append(
                psc_warning_anomaly(
                    source_ref=source_ref,
                    message=str(warning),
                    employee_label=str(label),
                )
            )


def _enrich_actions(
    items: List[Dict[str, Any]],
    target_company_id: Optional[str] = None,
    anomalies: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Détecte ce qui existe déjà en base pour pré-remplir les actions.

    - Groupe / entreprise existants -> action "update".
    - Salarié déjà présent dans l'entreprise (par NIR) -> action "skip" par
      défaut : on ne réécrit PAS la fiche existante (imports mensuels successifs).
      Les cumuls du mois restent importés. L'utilisateur peut basculer en
      "update" via les overrides s'il veut rafraîchir la fiche.

    Si `target_company_id` est fourni (rattachement manuel à une entreprise du
    groupe), la détection des salariés se fait dans cette entreprise plutôt que
    via le SIRET de la DSN.
    """
    target_co = repo.find_company_by_id(target_company_id) if target_company_id else None
    target_cid = str(target_co["id"]) if target_co else None
    target_company_name = (
        (target_co or {}).get("company_name")
        or (target_co or {}).get("raison_sociale")
        or "l'entreprise cible"
    )

    for it in items:
        payload = it.get("mapped_payload") or {}
        item_type = it.get("item_type")
        if item_type == "group":
            siren = payload.get("siren")
            if target_co or (siren and repo.find_group_by_siren(siren)):
                it["action"] = "update"
        elif item_type == "establishment":
            siret = payload.get("siret")
            existing_co = target_co or (repo.find_company_by_siret(siret) if siret else None)
            if target_co or existing_co:
                it["action"] = "update"
            if existing_co:
                from app.modules.dsn_import.domain.establishment_extract import (
                    compute_payroll_merge_conflicts,
                )

                conflicts = compute_payroll_merge_conflicts(payload, existing_co)
                it["payroll_conflicts"] = conflicts
                payload["_payroll_conflicts"] = conflicts
                it["mapped_payload"] = payload
        elif item_type == "employee":
            company_id = target_cid
            if company_id is None:
                source_ref = it.get("source_ref") or ""
                siret = source_ref.split(":")[1] if ":" in source_ref else ""
                co = repo.find_company_by_siret(siret) if siret else None
                company_id = str(co["id"]) if co else None
            nir = payload.get("nir")
            existing = (
                repo.find_employee_by_nir(company_id, nir)
                if company_id and nir
                else None
            )
            if not existing and nir:
                existing = repo.find_employee_by_nir_global(nir)
            if existing:
                it["is_existing"] = True
                it["existing_employee_id"] = str(existing["id"])
                it["action"] = "skip"
                existing_cid = str(existing.get("company_id") or "")
                if company_id and existing_cid and existing_cid != str(company_id):
                    other_co = repo.find_company_by_id(existing_cid)
                    other_name = (
                        (other_co or {}).get("company_name")
                        or (other_co or {}).get("raison_sociale")
                        or "une autre entreprise"
                    )
                    it["existing_company_id"] = existing_cid
                    it["existing_company_name"] = other_name
                    if anomalies is not None and target_cid:
                        payload = it.get("mapped_payload") or {}
                        anomalies.append(
                            employee_other_company_anomaly(
                                source_ref=it.get("source_ref") or "",
                                employee_name=(
                                    it.get("label")
                                    or f"{payload.get('first_name', '')} {payload.get('last_name', '')}".strip()
                                    or "Ce salarié"
                                ),
                                nir=nir,
                                target_company_name=target_company_name,
                                existing_company_name=other_name,
                            )
                        )
            else:
                it["is_existing"] = False
                it["existing_employee_id"] = None
                if it.get("action") == "skip":
                    it["action"] = "create"
            apply_review_flags(it)


def _apply_review_to_employees(items: List[Dict[str, Any]]) -> None:
    for it in items:
        if it.get("item_type") == "employee":
            apply_review_flags(it)


def _employee_state_counts(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compte les salariés déjà présents vs nouveaux pour le résumé preview."""
    employees = [it for it in items if it.get("item_type") == "employee"]
    existing = sum(1 for it in employees if it.get("is_existing"))
    return {
        "employee_existing_count": existing,
        "employee_new_count": len(employees) - existing,
    }


def get_batch_detail(batch_id: str) -> Optional[Dict[str, Any]]:
    batch = repo.get_batch(batch_id)
    if not batch:
        return None
    items = repo.list_items(batch_id)
    summary = batch.get("summary") or {}
    return {
        "batch": batch,
        "items": items,
        "preview": batch.get("preview") or {},
        "summary": summary,
    }


def revalidate_preview(
    batch_id: str,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
    target_company_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Recalcule anomalies, can_commit, actions et salariés déjà présents après
    une édition preview ou un changement de rattachement (entreprise cible).

    Repart du snapshot complet `batch.preview.items` (qui conserve tous les
    champs UI) puis re-détecte ce qui existe en base. Le snapshot et le résumé
    sont persistés pour rester cohérents au commit et après rechargement.
    """
    from app.modules.dsn_import.application.revalidate import revalidate_batch_preview

    batch = repo.get_batch(batch_id)
    if not batch:
        raise LookupError("Batch introuvable")

    preview = batch.get("preview") or {}
    snapshot = preview.get("items") or []
    payload_edits = payload_edits or {}

    # Repartir d'une copie des items du snapshot, en appliquant les éditions
    # utilisateur sur une copie du payload (clés impactant la détection : NIR…).
    preview_items: List[Dict[str, Any]] = []
    for row in snapshot:
        it = dict(row)
        mapped = dict(row.get("mapped_payload") or {})
        edits = payload_edits.get(it.get("source_ref")) or {}
        if edits and it.get("item_type") == "employee":
            edits = normalize_employee_edits(edits)
        if edits:
            mapped.update(edits)
        it["mapped_payload"] = mapped
        # On recalcule l'action : on retire l'éventuel skip auto pour le re-déduire.
        if it.get("item_type") == "employee":
            it["action"] = "create"
        preview_items.append(it)

    result = revalidate_batch_preview(batch, preview_items, payload_edits)
    mode = str((batch.get("summary") or {}).get("import_mode") or "onboarding")
    batch_summary = batch.get("summary") or {}
    resolved_target = resolve_monthly_target_company_id(
        mode,
        target_company_id or batch_summary.get("target_company_id"),
        {**batch_summary, **result["summary"]},
    )
    if resolved_target:
        target_company_id = resolved_target
    result["anomalies"] = strip_import_context_warnings(result["anomalies"])
    result["anomalies"] = strip_enrichment_warnings(result["anomalies"])
    _enrich_actions(preview_items, target_company_id=target_company_id, anomalies=result["anomalies"])
    attach_workforce_reconciliation(
        preview_items,
        result["summary"],
        result["anomalies"],
        target_company_id=target_company_id,
        import_mode=mode,
    )
    attach_reimport_orphans(
        preview_items,
        result["summary"],
        target_company_id=target_company_id
        or (batch.get("summary") or {}).get("target_company_id"),
        import_mode=mode,
    )
    _attach_psc_warnings(preview_items, result["anomalies"])
    _apply_review_to_employees(preview_items)
    result["summary"].update(_employee_state_counts(preview_items))
    result["summary"]["review_summary"] = build_review_summary(preview_items)
    result["summary"]["target_company_id"] = target_company_id
    result["items"] = preview_items

    periods = list((result["summary"].get("cumul_periods") or []))
    intended = (batch.get("summary") or {}).get("intended_period")
    dsn_name = (batch.get("summary") or {}).get("dsn_company_name")
    attach_import_context_warnings(
        result["anomalies"],
        result["summary"],
        mode=mode,
        target_company_id=target_company_id,
        periods=periods,
        dsn_company_name=dsn_name,
        intended_period=intended,
    )
    result["can_commit"] = not any(
        a.get("severity") == "blocking" for a in result["anomalies"]
    )
    if workforce_blocks_commit(result["summary"]):
        result["can_commit"] = False

    # Persistance du snapshot recalculé (actions + flags) et du résumé.
    new_preview = {
        **preview,
        "items": preview_items,
        "anomalies": result["anomalies"],
        "can_commit": result["can_commit"],
    }
    repo.update_batch(
        batch_id,
        {
            "preview": new_preview,
            "summary": {**(batch.get("summary") or {}), **result["summary"]},
        },
    )
    return result


def list_batches(limit: int = 50) -> List[Dict[str, Any]]:
    return repo.list_batches(limit=limit)


def list_attribution_companies() -> List[Dict[str, Any]]:
    """Entreprises existantes (avec groupe) proposées pour le rattachement manuel."""
    return repo.list_companies_for_attribution()


def execute_commit(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
    target_company_id: Optional[str] = None,
    workforce_resolutions: Optional[List[Dict[str, Any]]] = None,
    current_user_id: Optional[str] = None,
    remove_orphan_imported_employees: bool = False,
) -> Dict[str, Any]:
    return commit_batch(
        batch_id,
        overrides=overrides,
        payload_edits=payload_edits,
        target_company_id=target_company_id,
        workforce_resolutions=workforce_resolutions,
        current_user_id=current_user_id,
        remove_orphan_imported_employees=remove_orphan_imported_employees,
    )


def begin_commit(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
    target_company_id: Optional[str] = None,
    import_mode: Optional[str] = None,
    replace_existing_periods: bool = False,
    workforce_resolutions: Optional[List[Dict[str, Any]]] = None,
    current_user_id: Optional[str] = None,
    remove_orphan_imported_employees: bool = False,
) -> bool:
    """
    Bascule le batch en 'committing' avant lancement en arrière-plan.
    Retourne True si le commit doit être lancé, False s'il tourne déjà.
    """
    batch = repo.get_batch(batch_id)
    if not batch:
        raise LookupError("Batch introuvable")
    status = batch.get("status")
    if status == "committed":
        raise ValueError("Ce batch a déjà été validé")
    if status == "committing":
        return False

    summary = batch.get("summary") or {}
    mode = import_mode or summary.get("import_mode") or "onboarding"
    resolutions_payload = [dict(r) for r in (workforce_resolutions or [])]
    validate_workforce_resolutions_for_commit(summary, resolutions_payload)

    repo.update_batch(
        batch_id,
        {
            "status": "committing",
            "summary": {
                **summary,
                "target_company_id": target_company_id,
                "import_mode": mode,
                "replace_existing_periods": replace_existing_periods,
                "commit_request": {
                    "overrides": overrides or {},
                    "payload_edits": payload_edits or {},
                    "target_company_id": target_company_id,
                    "import_mode": mode,
                    "replace_existing_periods": replace_existing_periods,
                    "workforce_resolutions": resolutions_payload,
                    "current_user_id": current_user_id,
                    "remove_orphan_imported_employees": remove_orphan_imported_employees,
                },
            },
        },
    )
    return True


def run_commit(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
    target_company_id: Optional[str] = None,
    workforce_resolutions: Optional[List[Dict[str, Any]]] = None,
    current_user_id: Optional[str] = None,
    remove_orphan_imported_employees: bool = False,
) -> None:
    """Exécute le commit (tâche d'arrière-plan). Trace l'échec dans le batch."""
    from app.core.logging import get_logger

    from app.modules.dsn_import.domain.user_messages import humanize_commit_error, issue_to_legacy_string

    logger = get_logger("modules.dsn_import.run_commit")
    try:
        commit_batch(
            batch_id,
            overrides=overrides,
            payload_edits=payload_edits,
            target_company_id=target_company_id,
            workforce_resolutions=workforce_resolutions,
            current_user_id=current_user_id,
            remove_orphan_imported_employees=remove_orphan_imported_employees,
        )
    except Exception as exc:
        logger.exception("Commit arrière-plan batch %s échoué", batch_id)
        batch = repo.get_batch(batch_id) or {}
        issue = humanize_commit_error(exc)
        legacy = issue_to_legacy_string(issue)
        repo.update_batch(
            batch_id,
            {
                "status": "failed",
                "error_message": legacy,
                "summary": {
                    **(batch.get("summary") or {}),
                    "commit_report": {
                        "stats": {"created": 0, "updated": 0, "skipped": 0, "failed": 0},
                        "errors": [issue],
                        "error_messages": [legacy],
                        "group_id": None,
                        "companies": {},
                        "imported_employees": [],
                    },
                },
            },
        )


def save_workforce_resolutions(
    batch_id: str,
    resolutions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Persiste les décisions de réconciliation et recalcule le summary."""
    batch = repo.get_batch(batch_id)
    if not batch:
        raise LookupError("Batch introuvable")

    summary = dict(batch.get("summary") or {})
    wf = dict(summary.get("workforce_reconciliation") or {})
    stored: Dict[str, Dict[str, Any]] = {}
    for res in resolutions:
        gap_id = str(res.get("gap_id") or "")
        if gap_id:
            stored[gap_id] = {
                k: v
                for k, v in res.items()
                if k
                in (
                    "gap_id",
                    "employee_id",
                    "action",
                    "exit_type",
                    "last_working_day",
                    "exit_reason",
                    "ignore_reason",
                    "hire_date",
                )
                and v is not None
            }
            if hasattr(res.get("last_working_day"), "isoformat"):
                stored[gap_id]["last_working_day"] = res["last_working_day"].isoformat()
    wf["resolutions"] = stored
    gaps = wf.get("gaps") or []
    for gap in gaps:
        gap_id = gap.get("gap_id")
        if gap_id and gap_id in stored:
            gap["resolution"] = stored[gap_id]
    resolved_count = sum(1 for g in gaps if g.get("resolution"))
    wf["resolved_count"] = resolved_count
    wf["unresolved_count"] = len(gaps) - resolved_count
    summary["workforce_reconciliation"] = wf

    repo.update_batch(batch_id, {"summary": summary})
    return {"summary": summary, "workforce_reconciliation": wf}


def activate_imported_employee(
    employee_id: str,
    company_id: str,
    email: str,
    granted_by_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    from app.modules.employees.application.commands import activate_imported_employee_account

    return activate_imported_employee_account(
        employee_id=employee_id,
        company_id=company_id,
        email=email,
        granted_by_user_id=granted_by_user_id,
    )


def get_company_coverage(company_id: str) -> Dict[str, Any]:
    company = repo.find_company_by_id(company_id)
    if not company:
        raise LookupError("Entreprise introuvable")
    from app.modules.dsn_import.application.coverage import compute_coverage

    return compute_coverage(company)


def get_admin_late_summary() -> Dict[str, Any]:
    from app.modules.dsn_import.application.coverage import compute_admin_late_summary

    companies = repo.list_companies_with_dsn_mode()
    batches = repo.list_committed_batches(limit=500)
    return compute_admin_late_summary(companies, batches=batches)


def get_admin_coverage_matrix(year: int) -> Dict[str, Any]:
    from app.modules.dsn_import.application.coverage import compute_admin_coverage_matrix

    companies = repo.list_companies_with_dsn_mode()
    batches = repo.list_committed_batches(limit=500)
    return compute_admin_coverage_matrix(companies, year=year, batches=batches)


def list_pending_batches(limit: int = 20) -> List[Dict[str, Any]]:
    return repo.list_batches_by_statuses(["previewed", "committing"], limit=limit)


def revoke_period_import(
    company_id: str,
    period: str,
    *,
    revoked_by: Optional[str] = None,
) -> Dict[str, Any]:
    from app.modules.dsn_import.application.revoke_period import revoke_period_import as _revoke

    return _revoke(company_id, period, revoked_by=revoked_by)
