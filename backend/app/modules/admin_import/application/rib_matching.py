"""Rapprochement salarié pour import RIB (paie : matricule = nom tronqué)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.modules.schedules.application.employee_match import (
    is_junk_employee_name,
    resolve_employee_for_timesheet,
)
from app.modules.schedules.schemas.ai import RosterEmployee

_NAME_PARTICLES = frozenset(
    {"de", "du", "des", "le", "la", "les", "d", "l", "mr", "mme", "me", "m"}
)
_JUNK_NAME_TOKEN_RE = re.compile(
    r"presence|présence|assiduit|atelier|panier|soumises?|prime|indemn|"
    r"jours?|acquis|solde|pris|bulletin|periode|période|"
    r"heures?|minutes?|commentaires?|montant|taux|retenue|ouvr",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def _normalize_token(value: str) -> str:
    return _normalize(value).replace(" ", "")


def _parse_full_name(raw: str) -> Tuple[str, str]:
    """Découpe « Prénom NOM » ou « NOM Prénom » paie."""
    parts = [p for p in (raw or "").split() if p]
    if len(parts) < 2:
        return "", (parts[0] if parts else "")
    if parts[-1].isupper() and len(parts[-1]) >= 2 and not parts[0].isupper():
        return " ".join(parts[:-1]), parts[-1]
    if parts[0].isupper() and len(parts[0]) >= 2 and not parts[-1].isupper():
        return " ".join(parts[1:]), parts[0]
    return " ".join(parts[:-1]), parts[-1]


def _row_identity_fields(
    *,
    matricule: str,
    email: str,
    first_name: str,
    last_name: str,
    full_name: str,
) -> Tuple[str, str, str, str, str]:
    fn = first_name.strip()
    ln = last_name.strip()
    full = full_name.strip()

    if full and not fn and not ln:
        fn, ln = _parse_full_name(full)
    elif fn and not ln and " " in fn:
        fn, ln = _parse_full_name(fn)
    elif ln and not fn and " " in ln:
        fn, ln = _parse_full_name(ln)

    identity = f"{fn} {ln}".strip() if fn and ln else full or email or (f"Matricule {matricule}" if matricule else "")
    return fn, ln, full, identity, matricule.strip()


def _match_by_email(email: str, employees: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    target = email.strip().lower()
    if not target:
        return None
    matches = [e for e in employees if (e.get("email") or "").strip().lower() == target]
    return matches[0] if len(matches) == 1 else None


def _match_by_names(
    first_name: str,
    last_name: str,
    employees: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    fn = _normalize(first_name)
    ln = _normalize(last_name)
    if not fn or not ln:
        return None
    matches = [
        e
        for e in employees
        if _normalize(e.get("first_name") or "") == fn
        and _normalize(e.get("last_name") or "") == ln
    ]
    return matches[0] if len(matches) == 1 else None


def _folder_last_key(emp: Dict[str, Any]) -> str:
    folder = str(emp.get("employee_folder_name") or "")
    return _normalize_token(folder.split("_")[0] if "_" in folder else folder)


def _last_key(emp: Dict[str, Any]) -> str:
    return _normalize_token(emp.get("last_name") or "")


def _matricule_match_score(matricule: str, emp: Dict[str, Any]) -> int:
    """Score de rapprochement matricule paie → dossier (nom tronqué, tokens composés)."""
    key = _normalize_token(matricule)
    if not key:
        return 0

    best = 0
    for candidate in (_last_key(emp), _folder_last_key(emp)):
        if not candidate:
            continue
        if candidate == key:
            best = max(best, 100)
        elif len(key) >= 4 and candidate.startswith(key):
            best = max(best, 88 + min(len(key), 8))
        elif len(candidate) >= 4 and key.startswith(candidate[: len(key)]):
            best = max(best, 72)

    mat_tokens = [t for t in _normalize(matricule).split() if len(t) >= 2]
    last_tokens = [t for t in _normalize(emp.get("last_name") or "").split() if len(t) >= 2]
    if mat_tokens and last_tokens:
        matched = sum(
            1
            for i, tok in enumerate(mat_tokens)
            if i < len(last_tokens)
            and (
                last_tokens[i].startswith(tok)
                or tok.startswith(last_tokens[i][: max(3, len(tok))])
            )
        )
        if matched == len(mat_tokens):
            best = max(best, 78 + 6 * matched)

    return best


def _match_by_time_tracking_id(
    matricule: str,
    employees: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Matricule paie exact (ex. MIRZADA2, ZZSORTI113) → time_tracking_id salarié."""
    from app.modules.schedules.application.employee_match import _normalize_matricule

    norm_mat = _normalize_matricule(matricule)
    if not norm_mat:
        return None
    matches = [
        emp
        for emp in employees
        if _normalize_matricule(str(emp.get("time_tracking_id") or "")) == norm_mat
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _match_by_payroll_matricule(
    matricule: str,
    employees: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Matricule paie type Sage/Cegid : nom de famille tronqué (ex. BRISMONTIE → BRISMONTIER,
    BUSIZA LUS → BUSIZA LUSELA).
    """
    key = _normalize_token(matricule)
    if not key or key.isdigit():
        return None

    scored = [( _matricule_match_score(matricule, emp), emp) for emp in employees]
    scored = [(score, emp) for score, emp in scored if score >= 70]
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) == 1:
        return scored[0][1]
    if scored[0][0] >= scored[1][0] + 6:
        return scored[0][1]
    return None


def _is_reliable_payslip_identity(
    first_name: str,
    last_name: str,
    full_name: str,
) -> bool:
    """Filtre les noms OCR absurdes (ex. « de présence 24.00 »)."""
    full = (full_name or "").strip()
    if full and is_junk_employee_name(full):
        return False

    tokens = [
        token
        for token in _normalize(f"{first_name} {last_name} {full_name}").split()
        if token
    ]
    if len(tokens) < 2:
        return False
    if tokens[0] in _NAME_PARTICLES:
        return False
    if any(_JUNK_NAME_TOKEN_RE.search(token) for token in tokens):
        return False
    if any(any(ch.isdigit() for ch in token) for token in tokens):
        return False
    alpha_tokens = [token for token in tokens if any(ch.isalpha() for ch in token)]
    return len(alpha_tokens) >= 2


def _name_token_set(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in _normalize(part).split():
            if len(token) >= 2:
                tokens.add(token)
    return tokens


def _names_compatible_with_employee(
    first_name: str,
    last_name: str,
    emp: Dict[str, Any],
    *,
    full_name: str = "",
) -> bool:
    """Même personne si les tokens du nom bulletin couvrent le dossier (ordre paie variable)."""
    payslip_tokens = _name_token_set(first_name, last_name, full_name)
    emp_tokens = _name_token_set(
        str(emp.get("first_name") or ""),
        str(emp.get("last_name") or ""),
    )
    if not payslip_tokens or not emp_tokens:
        return True
    overlap = payslip_tokens & emp_tokens
    if overlap == payslip_tokens or overlap == emp_tokens:
        return True
    return len(overlap) >= min(2, len(payslip_tokens), len(emp_tokens))


def resolve_rib_row_match(
    *,
    roster: List[RosterEmployee],
    employees: List[Dict[str, Any]],
    matricule: str,
    email: str,
    first_name: str,
    last_name: str,
    full_name: str,
    patronymic_name: str = "",
    strict_matricule_fallback: bool = False,
) -> Dict[str, Any]:
    fn, ln, _full, identity, mat = _row_identity_fields(
        matricule=matricule,
        email=email,
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
    )
    warnings: List[str] = []

    if email:
        found = _match_by_email(email, employees)
        if found:
            return _result(found, "email", "high", "ok", warnings)

    pat = patronymic_name.strip()
    if pat:
        patronymic_fn = fn
        if not patronymic_fn and _full:
            parsed_fn, _ = _parse_full_name(_full)
            patronymic_fn = parsed_fn
        if patronymic_fn:
            found = _match_by_names(patronymic_fn, pat, employees)
            if found:
                return _result(found, "patronymic", "high", "ok", warnings)
        found = _match_by_payroll_matricule(pat, employees)
        if found:
            return _result(found, "patronymic_matricule", "high", "ok", warnings)

    if mat:
        found = _match_by_time_tracking_id(mat, employees)
        if found:
            return _result(found, "matricule", "high", "ok", warnings)

        found = _match_by_payroll_matricule(mat, employees)
        if found:
            label = f"{found.get('first_name', '')} {found.get('last_name', '')}".strip()
            if fn and ln and _normalize(label) != _normalize(f"{fn} {ln}"):
                if _names_compatible_with_employee(fn, ln, found, full_name=_full):
                    return _result(found, "matricule", "high", "ok", warnings)
                warnings.append(
                    f"Matricule paie « {mat} » → {label} (vérifiez le prénom dans le fichier)."
                )
                return _result(found, "matricule", "medium", "warning", warnings)
            return _result(found, "matricule", "high", "ok", warnings)

    reliable_identity = _is_reliable_payslip_identity(fn, ln, _full)

    if fn and ln and reliable_identity:
        found = _match_by_names(fn, ln, employees)
        if found:
            return _result(found, "name_exact", "high", "ok", warnings)

    if strict_matricule_fallback and mat:
        warnings.append(
            f"Matricule paie « {mat} » : aucun salarié correspondant dans EYWAI."
        )
        if _full:
            warnings.append(
                f"Nom lu sur le bulletin : « {_full} » — associez manuellement."
            )
        return {
            "employee_id": None,
            "matched_name": None,
            "match_confidence": "none",
            "match_method": "none",
            "review_status": "error",
            "warnings": warnings,
        }

    if not reliable_identity:
        if mat:
            warnings.append(
                f"Matricule paie « {mat} » : aucun salarié correspondant dans EYWAI."
            )
        if _full:
            warnings.append(
                f"Identité bulletin illisible (« {_full} ») — associez manuellement."
            )
        else:
            warnings.append("Identité bulletin illisible — associez manuellement.")
        return {
            "employee_id": None,
            "matched_name": None,
            "match_confidence": "none",
            "match_method": "none",
            "review_status": "error",
            "warnings": warnings,
        }

    proposal = resolve_employee_for_timesheet(
        raw_name=identity,
        matricule=mat or None,
        roster=roster,
    )
    if proposal.employee_id:
        return {
            "employee_id": proposal.employee_id,
            "matched_name": proposal.matched_name,
            "match_confidence": proposal.match_confidence or "none",
            "match_method": proposal.match_method or "none",
            "review_status": proposal.review_status or "error",
            "warnings": warnings + list(proposal.warnings),
        }

    warnings.append(f"Aucun salarié trouvé pour « {identity} ».")
    return {
        "employee_id": None,
        "matched_name": None,
        "match_confidence": "none",
        "match_method": "none",
        "review_status": "error",
        "warnings": warnings,
    }


def _result(
    emp: Dict[str, Any],
    method: str,
    confidence: str,
    status: str,
    warnings: List[str],
) -> Dict[str, Any]:
    return {
        "employee_id": str(emp["id"]),
        "matched_name": f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip(),
        "match_confidence": confidence,
        "match_method": method,
        "review_status": status,
        "warnings": warnings,
    }
