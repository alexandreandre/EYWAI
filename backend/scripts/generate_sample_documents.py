#!/usr/bin/env python3
"""
Génère les PDF d'aperçu (contrats, avenants, attestations, documents de sortie)
pour chaque salarié actif afin de vérifier les formats dans l'interface RH.

Usage (depuis backend/) :
  .venv-ci-local/bin/python3 scripts/generate_sample_documents.py
  .venv-ci-local/bin/python3 scripts/generate_sample_documents.py --dry-run

Par défaut, nettoie et régénère les documents d'aperçu existants (pas de doublons).
Les sorties preview ont le motif [PREVIEW] et n'altèrent pas le statut employé.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.core.database import get_supabase_admin_client
from app.modules.document_library.schemas.requests import KNOWN_DOCUMENT_TYPES
from app.modules.documents.application.commands import generate_document
from app.modules.documents.schemas.requests import GenerateDocumentRequest
from app.modules.employee_exits.application.dto import build_exit_record
from app.modules.employee_exits.domain.rules import get_initial_status
from app.modules.employee_exits.infrastructure.providers import (
    get_exit_document_generator,
    get_exit_storage_provider,
    get_indemnity_calculator,
)
from app.modules.employee_exits.infrastructure.queries import (
    get_company_by_id,
    get_employee_full,
)
from app.modules.employee_exits.infrastructure.repository import (
    EmployeeExitRepository,
    ExitDocumentRepository,
)
from app.services.document_service import document_service
from app.services.portability_document_generator import portability_generator

PREVIEW_EXIT_TAG = "[PREVIEW]"
PREVIEW_MOTIF = "Aperçu — vérification du format PDF"
BUCKET_GENERATED = "generated_documents"
BUCKET_EXIT = "exit_documents"

CONTRACT_TYPES = frozenset({"cdi", "cdd", "convention_stage", "contrat_alternance"})
AVENANT_TYPES = [
    "avenant_salaire",
    "avenant_poste",
    "avenant_temps",
    "avenant_lieu",
    "avenant_general",
]
ATTESTATION_TYPES = [t for t in KNOWN_DOCUMENT_TYPES if t.startswith("attestation_")]
EMPLOYEE_DOC_TYPES = set(CONTRACT_TYPES) | set(AVENANT_TYPES) | set(ATTESTATION_TYPES) | {
    "attestation_portabilite_prevoyance",
}
EXPECTED_EXIT_DOC_TYPES = frozenset({
    "certificat_travail",
    "attestation_pole_emploi",
    "solde_tout_compte",
    "attestation_portabilite_mutuelle",
})


def _resolve_contract_doc_type(contract_type: Optional[str]) -> str:
    if not contract_type:
        return "cdi"
    normalized = contract_type.strip().lower()
    if "cdd" in normalized:
        return "cdd"
    if "stage" in normalized:
        return "convention_stage"
    if "altern" in normalized or "apprent" in normalized:
        return "contrat_alternance"
    if "cdi" in normalized:
        return "cdi"
    mapping = {
        "stage": "convention_stage",
        "alternance": "contrat_alternance",
        "apprentissage": "contrat_alternance",
    }
    return mapping.get(normalized, "cdi")


def _category_for(doc_type: str) -> str:
    if doc_type in CONTRACT_TYPES:
        return "contrat"
    if "avenant" in doc_type:
        return "avenant"
    if doc_type == "attestation_portabilite_prevoyance":
        return "attestation_sortie"
    return "attestation_courante"


def _salaire_float(employee: Dict[str, Any]) -> Optional[float]:
    sb = employee.get("salaire_de_base")
    if isinstance(sb, dict):
        val = sb.get("valeur", sb.get("amount"))
    else:
        val = sb
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _pick_actor_id(sb: Any, company_id: str) -> str:
    res = (
        sb.table("user_company_accesses")
        .select("user_id, role")
        .eq("company_id", company_id)
        .in_("role", ["admin", "rh", "collaborateur_rh"])
        .limit(1)
        .execute()
    )
    if res.data:
        return str(res.data[0]["user_id"])
    prof = sb.table("profiles").select("id").limit(1).execute()
    if prof.data:
        return str(prof.data[0]["id"])
    raise RuntimeError(f"Aucun utilisateur RH pour company {company_id}")


def _list_active_employees(sb: Any) -> List[Dict[str, Any]]:
    rows = (sb.table("employees").select("*").execute()).data or []
    result: List[Dict[str, Any]] = []
    for row in rows:
        status = str(row.get("employment_status") or "actif").lower()
        if status in ("parti", "en_sortie"):
            continue
        result.append(row)
    return result


def _preview_exit_id(sb: Any, company_id: str, employee_id: str) -> Optional[str]:
    rows = (
        sb.table("employee_exits")
        .select("id, exit_reason")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .execute()
    ).data or []
    for row in rows:
        if PREVIEW_EXIT_TAG in str(row.get("exit_reason") or ""):
            return str(row["id"])
    return None


def _delete_exit_documents(sb: Any, exit_id: str) -> None:
    rows = (
        sb.table("exit_documents")
        .select("id, storage_path")
        .eq("exit_id", exit_id)
        .execute()
    ).data or []
    paths = [r["storage_path"] for r in rows if r.get("storage_path")]
    if paths:
        try:
            sb.storage.from_(BUCKET_EXIT).remove(paths)
        except Exception:
            pass
    for row in rows:
        sb.table("exit_documents").delete().eq("id", row["id"]).execute()


def _clean_employee_preview_docs(sb: Any, company_id: str, employee_id: str) -> None:
    """Supprime les documents d'aperçu précédents (fiche salarié)."""
    rows = (
        sb.table("generated_documents")
        .select("id, document_type, file_url, generation_context")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .execute()
    ).data or []
    to_delete: List[str] = []
    storage_paths: List[str] = []
    for row in rows:
        doc_type = str(row.get("document_type") or "")
        ctx = row.get("generation_context") or {}
        is_preview_ctx = isinstance(ctx, dict) and ctx.get("preview") is True
        is_preview_motif = isinstance(ctx, dict) and PREVIEW_MOTIF in str(
            ctx.get("motif") or ctx.get("motif_avenant") or ""
        )
        if doc_type in EMPLOYEE_DOC_TYPES or is_preview_ctx or is_preview_motif:
            to_delete.append(str(row["id"]))
            path = row.get("file_url")
            if path and str(path).startswith(f"{company_id}/"):
                storage_paths.append(str(path))
    if storage_paths:
        try:
            sb.storage.from_(BUCKET_GENERATED).remove(storage_paths)
        except Exception:
            pass
    for doc_id in to_delete:
        sb.table("generated_documents").delete().eq("id", doc_id).execute()


def _date_effet(employee: Dict[str, Any]) -> date:
    raw = employee.get("hire_date")
    if raw:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            pass
    return date.today()


def _avenant_request(
    doc_type: str, employee: Dict[str, Any], date_effet: date
) -> GenerateDocumentRequest:
    sal = _salaire_float(employee)
    poste = str(employee.get("job_title") or "Poste")
    duree = employee.get("duree_hebdomadaire")
    duree_str = f"{float(duree):g} h" if duree is not None else "35 h"
    lieu = str(employee.get("lieu_travail") or employee.get("workplace") or "Site principal")

    kwargs: Dict[str, Any] = {
        "employee_id": str(employee["id"]),
        "document_type": doc_type,
        "category": "avenant",
        "date_effet": date_effet,
        "motif": PREVIEW_MOTIF,
    }
    if doc_type == "avenant_salaire":
        base = sal if sal is not None else 2500.0
        kwargs["ancien_salaire"] = base
        kwargs["nouveau_salaire"] = round(base + 100, 2)
    elif doc_type == "avenant_poste":
        kwargs["ancien_poste"] = poste
        kwargs["nouveau_poste"] = f"{poste} — aperçu"
    elif doc_type == "avenant_temps":
        kwargs["ancienne_duree"] = duree_str
        kwargs["nouvelle_duree"] = "39 h"
    elif doc_type == "avenant_lieu":
        kwargs["ancien_lieu"] = lieu
        kwargs["nouveau_lieu"] = f"{lieu} (aperçu)"
    return GenerateDocumentRequest(**kwargs)


def _exit_date_fr(exit_data: Dict[str, Any]) -> str:
    raw = exit_data.get("last_working_day") or ""
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw[:10]).strftime("%d/%m/%Y")
        except ValueError:
            return raw
    return date.today().strftime("%d/%m/%Y")


def _generate_exit_docs(
    sb: Any,
    exit_id: str,
    company_id: str,
    employee_id: str,
    actor_id: str,
) -> None:
    exit_repo = EmployeeExitRepository(sb)
    doc_repo = ExitDocumentRepository(sb)
    generator = get_exit_document_generator()
    calculator = get_indemnity_calculator()
    storage = get_exit_storage_provider(sb)

    exit_data = exit_repo.get_by_id(exit_id, company_id)
    if not exit_data:
        raise RuntimeError(f"Sortie preview {exit_id} introuvable")
    employee_full = get_employee_full(employee_id, sb) or {}
    company_data = get_company_by_id(company_id, sb) or {}

    indemnities = calculator.calculate(employee_full, exit_data, sb)
    exit_repo.update(
        exit_id,
        company_id,
        {
            "calculated_indemnities": indemnities,
            "remaining_vacation_days": indemnities.get("indemnite_conges", {}).get(
                "jours_restants", 0
            ),
            "final_net_amount": indemnities.get("total_net_indemnities", 0),
        },
    )
    exit_full_data = {
        **exit_data,
        "employees": employee_full,
        "calculated_indemnities": indemnities,
    }

    for doc_type in (
        "certificat_travail",
        "attestation_pole_emploi",
        "solde_tout_compte",
    ):
        if doc_type == "solde_tout_compte":
            pdf_bytes = generator.generate_solde_tout_compte(
                employee_full, company_data, exit_full_data, indemnities, sb
            )
        elif doc_type == "certificat_travail":
            pdf_bytes = generator.generate_certificat_travail(
                employee_full, company_data, exit_full_data
            )
        else:
            pdf_bytes = generator.generate_attestation_pole_emploi(
                employee_full,
                company_data,
                exit_full_data,
                indemnities=indemnities,
                supabase_client=sb,
            )
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{doc_type}_{ts}.pdf"
        storage_path = f"exits/{exit_id}/{filename}"
        storage.upload(storage_path, pdf_bytes, "application/pdf")
        doc_repo.create(
            {
                "exit_id": exit_id,
                "company_id": company_id,
                "document_type": doc_type,
                "document_category": "generated",
                "storage_path": storage_path,
                "filename": filename,
                "mime_type": "application/pdf",
                "file_size_bytes": len(pdf_bytes),
                "generation_template": f"template_{doc_type}",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "uploaded_by": actor_id,
            }
        )

    exit_type = str(exit_data.get("exit_type") or "rupture_conventionnelle")
    exit_date_fr = _exit_date_fr(exit_data)
    mutuelle_pdf = portability_generator.generate_portabilite_mutuelle(
        employee_full, company_data, exit_date_fr, exit_type
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    mutuelle_name = f"attestation_portabilite_mutuelle_{ts}.pdf"
    mutuelle_path = f"exits/{exit_id}/{mutuelle_name}"
    storage.upload(mutuelle_path, mutuelle_pdf, "application/pdf")
    doc_repo.create(
        {
            "exit_id": exit_id,
            "company_id": company_id,
            "document_type": "attestation_portabilite_mutuelle",
            "document_category": "generated",
            "storage_path": mutuelle_path,
            "filename": mutuelle_name,
            "mime_type": "application/pdf",
            "file_size_bytes": len(mutuelle_pdf),
            "generation_template": "template_attestation_portabilite_mutuelle",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "uploaded_by": actor_id,
        }
    )

    prev_pdf = portability_generator.generate_portabilite_prevoyance(
        employee_full, company_data, exit_date_fr, exit_type
    )
    prev_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prev_name = f"attestation_portabilite_prevoyance_{prev_ts}.pdf"
    prev_storage = f"{company_id}/{employee_id}/{prev_name}"
    sb.storage.from_(BUCKET_GENERATED).upload(
        prev_storage, prev_pdf, {"content-type": "application/pdf"}
    )
    document_service.trace_existing_document(
        company_id=company_id,
        employee_id=employee_id,
        document_type="attestation_portabilite_prevoyance",
        category="attestation_sortie",
        file_url=prev_storage,
        file_name=prev_name,
        is_eywai_template=True,
        generation_context={"exit_id": exit_id, "preview": True},
        generated_by=actor_id,
    )


def _ensure_preview_exit(
    sb: Any,
    employee: Dict[str, Any],
    actor_id: str,
    *,
    dry_run: bool,
    refresh: bool,
) -> Optional[str]:
    company_id = str(employee["company_id"])
    employee_id = str(employee["id"])
    existing = _preview_exit_id(sb, company_id, employee_id)

    if dry_run:
        return existing or "(nouveau)"

    if refresh and existing:
        _delete_exit_documents(sb, existing)

    if not existing:
        today = date.today()
        last_day = today + timedelta(days=30)
        exit_type = "rupture_conventionnelle"
        record = build_exit_record(
            company_id=company_id,
            employee_id=employee_id,
            exit_type=exit_type,
            initial_status=get_initial_status(exit_type),
            exit_request_date=today.isoformat(),
            last_working_day=last_day.isoformat(),
            notice_period_days=0,
            is_gross_misconduct=False,
            notice_indemnity_type="not_applicable",
            notice_start_date=None,
            notice_end_date=None,
            exit_reason=f"{PREVIEW_EXIT_TAG} Documents générés pour vérification des formats",
            initiated_by=actor_id,
        )
        record["status"] = "annulee"
        created = EmployeeExitRepository(sb).create(record)
        existing = str(created["id"])
    elif refresh:
        pass
    else:
        rows = (
            sb.table("exit_documents")
            .select("document_type")
            .eq("exit_id", existing)
            .eq("document_category", "generated")
            .execute()
        ).data or []
        found = {str(r["document_type"]) for r in rows if r.get("document_type")}
        if EXPECTED_EXIT_DOC_TYPES <= found:
            prev = (
                sb.table("generated_documents")
                .select("id")
                .eq("employee_id", employee_id)
                .eq("document_type", "attestation_portabilite_prevoyance")
                .limit(1)
                .execute()
            ).data
            if prev:
                return existing

    _generate_exit_docs(sb, existing, company_id, employee_id, actor_id)
    return existing


def _doc_types_for_employee(employee: Dict[str, Any]) -> Iterable[str]:
    yield _resolve_contract_doc_type(employee.get("contract_type"))
    yield from AVENANT_TYPES
    yield from ATTESTATION_TYPES


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Génère les PDF d'aperçu pour tous les salariés actifs."
    )
    parser.add_argument("--dry-run", action="store_true", help="Affiche sans générer")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Ne pas supprimer les aperçus déjà générés (peut créer des doublons)",
    )
    args = parser.parse_args()
    refresh = not args.keep_existing

    sb = get_supabase_admin_client()
    employees = _list_active_employees(sb)
    if not employees:
        print("Aucun salarié actif trouvé.")
        return 0

    print(f"Salariés actifs : {len(employees)}")
    if refresh and not args.dry_run:
        print("Mode : nettoyage puis régénération des aperçus")
    actors: Dict[str, str] = {}
    stats = {"generated": 0, "skipped": 0, "errors": 0, "exits": 0}

    for emp in employees:
        company_id = str(emp["company_id"])
        employee_id = str(emp["id"])
        name = f"{emp.get('last_name', '')} {emp.get('first_name', '')}".strip()
        if company_id not in actors:
            actors[company_id] = _pick_actor_id(sb, company_id)
        actor_id = actors[company_id]
        date_effet = _date_effet(emp)
        print(f"\n— {name} ({employee_id[:8]}…)")

        if refresh and not args.dry_run:
            _clean_employee_preview_docs(sb, company_id, employee_id)

        for doc_type in _doc_types_for_employee(emp):
            if args.dry_run:
                print(f"  [dry-run] {doc_type}")
                stats["generated"] += 1
                continue
            req = (
                _avenant_request(doc_type, emp, date_effet)
                if "avenant" in doc_type
                else GenerateDocumentRequest(
                    employee_id=employee_id,
                    document_type=doc_type,
                    category=_category_for(doc_type),
                    date_effet=date_effet
                    if doc_type in CONTRACT_TYPES or "avenant" in doc_type
                    else None,
                    motif=PREVIEW_MOTIF if "avenant" in doc_type else None,
                )
            )
            try:
                generate_document(company_id, actor_id, req)
                print(f"  ✓ {doc_type}")
                stats["generated"] += 1
            except Exception as exc:
                print(f"  ✗ {doc_type} : {exc}")
                stats["errors"] += 1

        try:
            exit_id = _ensure_preview_exit(
                sb, emp, actor_id, dry_run=args.dry_run, refresh=refresh
            )
            if exit_id:
                print(f"  ✓ docs sortie (preview {str(exit_id)[:8]}…)")
                stats["exits"] += 1
        except Exception as exc:
            print(f"  ✗ docs sortie : {exc}")
            stats["errors"] += 1

    print(
        f"\nRésumé : {stats['generated']} docs fiche, "
        f"{stats['exits']} sorties preview, "
        f"{stats['errors']} erreur(s)."
    )
    if stats["errors"] == 0:
        print(
            "\n→ Fiche salarié : onglet Documents (Contrat / Autres)\n"
            "→ Docs de sortie : RH > Sorties, filtrer les sorties [PREVIEW]"
        )
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
