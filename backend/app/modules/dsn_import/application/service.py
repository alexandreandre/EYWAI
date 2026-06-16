"""Service applicatif import DSN."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.application.commit import commit_batch
from app.modules.dsn_import.application.cumuls import build_cumuls_summary, plan_cumul_items
from app.modules.dsn_import.application.mapping import (
    apply_legal_name_to_preview,
    build_preview_items,
    enrich_summary_from_items,
)
from app.modules.dsn_import.application.import_checks import (
    attach_import_context_warnings,
    strip_import_context_warnings,
)
from app.modules.dsn_import.domain.parser import parse_dsn_files
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
    preview_items, summary = build_preview_items(parsed)
    cumul_items = plan_cumul_items(parsed)
    all_items = preview_items + cumul_items

    mode = (import_mode or "onboarding").strip().lower()
    if mode not in ("onboarding", "monthly"):
        mode = "onboarding"

    # Détection create vs update vs salariés déjà présents (best effort sans bloquer)
    _enrich_actions(all_items, target_company_id=target_company_id)

    summary = enrich_summary_from_items(summary, parsed, all_items)
    summary.update(_employee_state_counts(all_items))
    summary["import_mode"] = mode
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
                "can_commit": not any(a.get("severity") == "blocking" for a in anomalies),
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
        "can_commit": not any(a.get("severity") == "blocking" for a in anomalies),
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


def _enrich_actions(
    items: List[Dict[str, Any]],
    target_company_id: Optional[str] = None,
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

    for it in items:
        payload = it.get("mapped_payload") or {}
        item_type = it.get("item_type")
        if item_type == "group":
            siren = payload.get("siren")
            if target_co or (siren and repo.find_group_by_siren(siren)):
                it["action"] = "update"
        elif item_type == "establishment":
            siret = payload.get("siret")
            if target_co or (siret and repo.find_company_by_siret(siret)):
                it["action"] = "update"
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
            if existing:
                it["is_existing"] = True
                it["existing_employee_id"] = str(existing["id"])
                it["action"] = "skip"
            else:
                it["is_existing"] = False
                it["existing_employee_id"] = None
                if it.get("action") == "skip":
                    it["action"] = "create"


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
        if edits:
            mapped.update(edits)
        it["mapped_payload"] = mapped
        # On recalcule l'action : on retire l'éventuel skip auto pour le re-déduire.
        if it.get("item_type") == "employee":
            it["action"] = "create"
        preview_items.append(it)

    _enrich_actions(preview_items, target_company_id=target_company_id)

    result = revalidate_batch_preview(batch, preview_items, payload_edits)
    result["summary"].update(_employee_state_counts(preview_items))
    result["summary"]["target_company_id"] = target_company_id
    result["items"] = preview_items

    mode = str((batch.get("summary") or {}).get("import_mode") or "onboarding")
    periods = list((result["summary"].get("cumul_periods") or []))
    intended = (batch.get("summary") or {}).get("intended_period")
    dsn_name = (batch.get("summary") or {}).get("dsn_company_name")
    result["anomalies"] = strip_import_context_warnings(result["anomalies"])
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
) -> Dict[str, Any]:
    return commit_batch(
        batch_id,
        overrides=overrides,
        payload_edits=payload_edits,
        target_company_id=target_company_id,
    )


def begin_commit(
    batch_id: str,
    overrides: Optional[Dict[str, str]] = None,
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
    target_company_id: Optional[str] = None,
    import_mode: Optional[str] = None,
    replace_existing_periods: bool = False,
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
    repo.update_batch(
        batch_id,
        {
            "status": "committing",
            "summary": {
                **(batch.get("summary") or {}),
                "target_company_id": target_company_id,
                "import_mode": import_mode or (batch.get("summary") or {}).get("import_mode"),
                "replace_existing_periods": replace_existing_periods,
                "commit_request": {
                    "overrides": overrides or {},
                    "payload_edits": payload_edits or {},
                    "target_company_id": target_company_id,
                    "import_mode": import_mode,
                    "replace_existing_periods": replace_existing_periods,
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
) -> None:
    """Exécute le commit (tâche d'arrière-plan). Trace l'échec dans le batch."""
    from app.core.logging import get_logger

    logger = get_logger("modules.dsn_import.run_commit")
    try:
        commit_batch(
            batch_id,
            overrides=overrides,
            payload_edits=payload_edits,
            target_company_id=target_company_id,
        )
    except Exception as exc:
        logger.exception("Commit arrière-plan batch %s échoué", batch_id)
        batch = repo.get_batch(batch_id) or {}
        repo.update_batch(
            batch_id,
            {
                "status": "failed",
                "error_message": str(exc),
                "summary": {
                    **(batch.get("summary") or {}),
                    "commit_report": {
                        "stats": {"created": 0, "updated": 0, "skipped": 0, "failed": 0},
                        "errors": [str(exc)],
                        "group_id": None,
                        "companies": {},
                        "imported_employees": [],
                    },
                },
            },
        )


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
