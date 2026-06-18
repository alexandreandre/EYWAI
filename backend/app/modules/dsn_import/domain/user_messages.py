"""Messages utilisateur (français) pour l'import DSN."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.modules.employees.application.dto import EmployeeCreateValidationError


def _mask_nir(nir: Optional[str]) -> str:
    if not nir:
        return "—"
    s = str(nir).strip()
    if len(s) <= 4:
        return s
    return f"…{s[-4:]}"


def _employee_display_name(
    *,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    label: Optional[str] = None,
) -> str:
    name = f"{first_name or ''} {last_name or ''}".strip()
    return name or label or "Ce salarié"


def build_issue(
    code: str,
    message: str,
    *,
    hint: Optional[str] = None,
    severity: str = "error",
    source_ref: Optional[str] = None,
    item_label: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    issue_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Fabrique une issue structurée (anomalie preview ou erreur commit)."""
    return {
        "code": code,
        "type": issue_type or code,
        "message": message,
        "hint": hint,
        "severity": severity,
        "source_ref": source_ref,
        "item_label": item_label,
        "meta": meta or {},
    }


def build_anomaly(
    code: str,
    message: str,
    *,
    hint: Optional[str] = None,
    severity: str = "warning",
    source_ref: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return build_issue(
        code,
        message,
        hint=hint,
        severity=severity,
        source_ref=source_ref,
        meta=meta,
        issue_type=code,
    )


def employee_other_company_anomaly(
    *,
    source_ref: str,
    employee_name: str,
    nir: Optional[str],
    target_company_name: str,
    existing_company_name: str,
) -> Dict[str, Any]:
    return build_anomaly(
        "employee_other_company",
        (
            f"{employee_name} (NIR {_mask_nir(nir)}) est déjà enregistré "
            f"chez {existing_company_name}, pas dans {target_company_name}."
        ),
        hint=(
            "Aucune action requise : ce salarié sera ignoré à la création ; "
            "ses cumuls seront ajoutés sur sa fiche existante. "
            "Corrigez le rattachement entreprise uniquement si la fiche est au mauvais endroit."
        ),
        severity="warning",
        source_ref=source_ref,
        meta={
            "existing_company_name": existing_company_name,
            "target_company_name": target_company_name,
            "nir": nir,
        },
    )


def target_siret_missing_anomaly(
    *,
    target_company_name: str,
    dsn_siret: str,
) -> Dict[str, Any]:
    return build_anomaly(
        "target_siret_missing",
        (
            f"La fiche {target_company_name} n'a pas de SIRET renseigné ; "
            f"l'import utilise le SIRET de la DSN ({dsn_siret})."
        ),
        hint="Renseignez le SIRET sur la fiche entreprise pour éviter les confusions futures.",
        severity="warning",
        meta={"dsn_siret": dsn_siret, "target_company_name": target_company_name},
    )


def workforce_reconciliation_summary_anomaly(
    *,
    company_name: str,
    gap_count: int,
    period: Optional[str],
) -> Dict[str, Any]:
    period_label = f" ({period})" if period else ""
    return build_anomaly(
        "workforce_reconciliation_required",
        (
            f"{gap_count} écart(s) effectif(s) détecté(s) chez {company_name}{period_label}. "
            "Une décision est requise avant validation."
        ),
        hint=(
            "Pour chaque salarié : clôture rapide (départ déjà effectué), "
            "ouvrir le parcours départ complet, ou ignorer avec motif."
        ),
        severity="warning",
        meta={"gap_count": gap_count, "period": period},
    )


def employee_workforce_gap_anomaly(*, gap: Dict[str, Any]) -> Dict[str, Any]:
    gap_type = gap.get("gap_type")
    name = gap.get("employee_name") or "Salarié"
    employee_id = gap.get("employee_id")
    if gap_type == "missing_from_dsn":
        message = (
            f"{name} (NIR {gap.get('nir_masked', '—')}) est actif en base "
            "mais absent de la DSN du mois."
        )
        hint = (
            "Le salarié est peut-être sorti des effectifs. "
            "Clôturez le départ ou ignorez si la DSN est incomplète."
        )
        code = "employee_missing_from_dsn"
    else:
        end = gap.get("contract_end_date") or gap.get("suggested_last_working_day") or "—"
        message = (
            f"{name} : fin de contrat {end} détectée dans la DSN "
            "mais le salarié est encore actif en base."
        )
        hint = "Clôturez le départ ou ouvrez le parcours départ complet."
        code = "employee_contract_end_in_dsn"
    return build_anomaly(
        code,
        message,
        hint=hint,
        severity="warning",
        source_ref=f"gap:{employee_id}" if employee_id else None,
        meta={"gap": gap},
    )


def parse_warning_anomaly(message: str) -> Dict[str, Any]:
    return build_anomaly("parse_warning", message, severity="warning")


def psc_warning_anomaly(*, source_ref: str, message: str, employee_label: str) -> Dict[str, Any]:
    return build_anomaly(
        "psc_warning",
        f"{employee_label} : {message}",
        hint="Vérifiez les affiliations mutuelle / prévoyance sur la fiche salarié après import.",
        severity="warning",
        source_ref=source_ref,
    )


def _parse_runtime_message(msg: str) -> Optional[Dict[str, Any]]:
    m = re.match(
        r"NIR (.+) déjà enregistré chez (.+) — ignorez ce salarié",
        msg,
    )
    if m:
        nir, company = m.group(1), m.group(2)
        return build_issue(
            "employee_cross_company",
            f"Ce NIR ({_mask_nir(nir)}) est déjà enregistré chez {company}.",
            hint="Passez l'action du salarié sur « Ignorer » ou corrigez sa fiche entreprise avant de forcer la création.",
            severity="error",
            meta={"nir": nir, "existing_company_name": company},
        )

    m = re.match(r"Salarié NIR (.+) introuvable pour cumuls", msg)
    if m:
        nir = m.group(1)
        return build_issue(
            "employee_not_found_cumul",
            f"Impossible d'enregistrer les cumuls : aucun salarié trouvé pour le NIR {_mask_nir(nir)}.",
            hint="Vérifiez que le salarié est bien importé ou ignoré correctement avant les cumuls du mois.",
            severity="error",
            meta={"nir": nir},
        )

    m = re.match(r"Entreprise (.+) introuvable pour cumuls", msg)
    if m:
        siret = m.group(1)
        return build_issue(
            "establishment_not_found",
            f"L'établissement {siret} est introuvable pour l'enregistrement des cumuls.",
            hint="Vérifiez le rattachement entreprise ou importez d'abord l'établissement de la DSN.",
            severity="error",
            meta={"siret": siret},
        )

    m = re.match(r"Établissement (.+) introuvable pour le salarié", msg)
    if m:
        siret = m.group(1)
        return build_issue(
            "establishment_not_found",
            f"L'établissement {siret} est introuvable pour l'import du salarié.",
            hint="Importez ou rattachez l'établissement de la DSN à une entreprise existante.",
            severity="error",
            meta={"siret": siret},
        )

    m = re.match(r"Entreprise (.+) introuvable pour IDCC (.+)", msg)
    if m:
        siret, idcc = m.group(1), m.group(2)
        return build_issue(
            "establishment_not_found",
            f"L'établissement {siret} est introuvable pour l'IDCC {idcc}.",
            hint="Importez l'établissement avant d'assigner la convention collective.",
            severity="error",
            meta={"siret": siret, "idcc": idcc},
        )

    if msg == "Création du groupe échouée":
        return build_issue(
            "group_creation_failed",
            "La création du groupe a échoué.",
            hint="Vérifiez le SIREN et réessayez ; contactez le support si le problème persiste.",
            severity="error",
        )

    m = re.match(r"Création entreprise (.+) échouée", msg)
    if m:
        siret = m.group(1)
        return build_issue(
            "company_creation_failed",
            f"La création de l'entreprise {siret} a échoué.",
            hint="Vérifiez le SIRET et rattachez l'import à une entreprise existante si besoin.",
            severity="error",
            meta={"siret": siret},
        )

    return None


def _parse_api_error(exc: Exception) -> Optional[Dict[str, Any]]:
    raw = str(exc)
    if "employees_nir_key" in raw or (
        "23505" in raw and "nir" in raw.lower()
    ):
        nir_match = re.search(r"\(nir\)=\(([^)]+)\)", raw)
        nir = nir_match.group(1) if nir_match else None
        return build_issue(
            "duplicate_nir",
            (
                f"Ce numéro de sécurité sociale ({_mask_nir(nir)}) est déjà enregistré "
                "dans une autre fiche salarié."
            ),
            hint=(
                "Ignorez ce salarié à l'import s'il existe déjà, ou corrigez son rattachement "
                "entreprise avant de forcer la création."
            ),
            severity="error",
            meta={"nir": nir, "technical": raw},
        )
    return None


def humanize_commit_error(
    exc: Exception,
    *,
    source_ref: str = "",
    item_label: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Traduit une exception commit en message métier structuré."""
    context = context or {}

    if isinstance(exc, EmployeeCreateValidationError):
        fields = getattr(exc, "field_errors", None) or {}
        detail = "; ".join(f"{k} : {v}" for k, v in fields.items()) if fields else str(exc)
        return build_issue(
            "employee_validation",
            "La fiche salarié n'a pas pu être enregistrée : données invalides.",
            hint=detail or "Corrigez les champs signalés dans la preview puis relancez l'import.",
            severity="error",
            source_ref=source_ref or None,
            item_label=item_label,
            meta={"field_errors": fields, "technical": str(exc)},
        )

    if isinstance(exc, HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        if "sécurité sociale" in detail.lower() or "nir" in detail.lower():
            return build_issue(
                "duplicate_nir",
                detail,
                hint="Ignorez ce salarié ou corrigez son rattachement entreprise.",
                severity="error",
                source_ref=source_ref or None,
                item_label=item_label,
                meta={"technical": str(exc)},
            )
        return build_issue(
            "employee_validation",
            detail,
            severity="error",
            source_ref=source_ref or None,
            item_label=item_label,
            meta={"technical": str(exc)},
        )

    parsed = _parse_api_error(exc)
    if parsed:
        parsed["source_ref"] = source_ref or parsed.get("source_ref")
        parsed["item_label"] = item_label
        return parsed

    if isinstance(exc, RuntimeError):
        parsed_rt = _parse_runtime_message(str(exc))
        if parsed_rt:
            parsed_rt["source_ref"] = source_ref or parsed_rt.get("source_ref")
            parsed_rt["item_label"] = item_label
            return parsed_rt

    if isinstance(exc, LookupError):
        return build_issue(
            "batch_not_found",
            str(exc) or "Lot d'import introuvable.",
            severity="error",
            meta={"technical": str(exc)},
        )

    if isinstance(exc, ValueError):
        return build_issue(
            "commit_invalid",
            str(exc),
            severity="error",
            meta={"technical": str(exc)},
        )

    technical = str(exc)
    return build_issue(
        "unknown",
        "Une erreur inattendue est survenue pendant l'import.",
        hint="Consultez le détail technique ou contactez le support si le problème persiste.",
        severity="error",
        source_ref=source_ref or None,
        item_label=item_label,
        meta={"technical": technical, **context},
    )


def issue_to_legacy_string(issue: Dict[str, Any]) -> str:
    """Format rétrocompatible pour les clients qui lisent errors: string[]."""
    ref = issue.get("source_ref")
    prefix = f"{ref} : " if ref else ""
    msg = issue.get("message") or "Erreur inconnue"
    hint = issue.get("hint")
    if hint:
        return f"{prefix}{msg} — {hint}"
    return f"{prefix}{msg}"
