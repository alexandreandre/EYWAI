"""
Résolution employé pour import de relevés : matricule GTA puis nom.

Règle anti-homonyme : jamais de match sur prénom seul si plusieurs candidats.
Format Cegid typique : « MATRICULE NOM prénom(s) » (nom de famille en premier).
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Literal, Optional, Tuple

from app.modules.schedules.schemas.ai import AiEmployeeProposal, RosterEmployee

MatchMethod = Literal["matricule", "name_exact", "name_fuzzy", "none"]
ReviewStatus = Literal["ok", "warning", "error", "empty"]

_NAME_PARTICLES = frozenset(
    {"de", "du", "des", "le", "la", "les", "d", "l", "mr", "mme", "me", "m"}
)

_JUNK_NAME_RE = re.compile(
    r"édition|heures\s+et\s+minutes|pointages?|commentaires|retenu|"
    r"entreprise|total\s+pour|semaine\s+du|du\s+\d{1,2}/\d{1,2}|"
    r"presence|présence|jours?\s+de|de\s+presence|de\s+présence|"
    r"^\d|acquis|solde|total\s+pris",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def _normalize_matricule(matricule: str | None) -> str:
    s = (matricule or "").strip()
    if s.isdigit():
        return str(int(s))
    return s


def _tokens(value: str) -> set[str]:
    return set(_normalize(value).split())


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def is_junk_employee_name(raw_name: str) -> bool:
    """Filtre les lignes OCR non salarié (pied de page Cegid, en-têtes…)."""
    if not raw_name or not raw_name.strip():
        return True
    if _JUNK_NAME_RE.search(raw_name):
        return True
    parts = raw_name.split()
    if len(parts) < 2:
        return True
    letter_parts = sum(1 for p in parts if re.search(r"[A-Za-zÀ-ÿ]", p))
    return letter_parts < 2


def _parse_cegid_name(raw_name: str) -> tuple[str, str]:
    """Découpe « NOM Prénom(s) » (convention Cegid)."""
    parts = raw_name.split()
    if len(parts) < 2:
        return "", raw_name.strip()
    return parts[0], " ".join(parts[1:])


def _last_name_matches_ocr(ocr_last: str, emp_last: str) -> bool:
    o = _normalize(ocr_last).replace(" ", "")
    last = _normalize(emp_last).replace(" ", "")
    if not o or not last:
        return False
    if len(o) < 4 or o in _NAME_PARTICLES:
        return False
    if o == last:
        return True
    if len(last) >= 4 and len(o) >= 4 and (last in o or o in last):
        return True
    return len(o) >= 4 and len(last) >= 4 and _levenshtein(o, last) <= 2


def _first_name_matches_ocr(
    ocr_first: str, emp_first: str, *, strict: bool = False
) -> bool:
    o = _normalize(ocr_first)
    f = _normalize(emp_first)
    if not o or not f:
        return False
    if o == f or o in f or f in o:
        return True
    if _levenshtein(o, f) <= 2:
        return True
    o_t = _tokens(ocr_first)
    f_t = _tokens(emp_first)
    if not o_t & f_t:
        return False
    if strict:
        return all(t in f_t or len(t) < 3 for t in o_t)
    return True


def _employees_with_last_name(roster: List[RosterEmployee], last: str) -> List[RosterEmployee]:
    norm_last = _normalize(last)
    return [e for e in roster if _normalize(e.last_name) == norm_last]


def _employees_with_first_name(roster: List[RosterEmployee], first: str) -> List[RosterEmployee]:
    norm_first = _normalize(first)
    return [e for e in roster if _normalize(e.first_name) == norm_first]


def _match_by_cegid_name_order(
    raw_name: str,
    roster: List[RosterEmployee],
    *,
    matricule: str | None = None,
) -> Optional[AiEmployeeProposal]:
    """Rapprochement NOM-prénom Cegid avec tolérance OCR."""
    ocr_last, ocr_first = _parse_cegid_name(raw_name)
    if not ocr_last:
        return None

    by_last = [e for e in roster if _last_name_matches_ocr(ocr_last, e.last_name)]
    if not by_last:
        return None

    chosen: RosterEmployee | None = None
    if len(by_last) == 1:
        chosen = by_last[0]
    else:
        by_first = [
            e for e in by_last if _first_name_matches_ocr(ocr_first, e.first_name, strict=True)
        ]
        if len(by_first) == 1:
            chosen = by_first[0]
        else:
            fuzzy: List[Tuple[int, RosterEmployee]] = []
            for emp in by_last:
                dist = _levenshtein(_normalize(ocr_first), _normalize(emp.first_name))
                if dist <= 3:
                    fuzzy.append((dist, emp))
            fuzzy.sort(key=lambda x: x[0])
            if fuzzy and (len(fuzzy) == 1 or fuzzy[0][0] < fuzzy[1][0]):
                chosen = fuzzy[0][1]

    if chosen is None:
        return None

    proposal = AiEmployeeProposal(raw_name=raw_name or "")
    proposal.time_tracking_id = matricule
    proposal.employee_id = chosen.id
    proposal.matched_name = f"{chosen.first_name} {chosen.last_name}"
    proposal.match_method = "name_fuzzy" if len(by_last) > 1 else "name_exact"

    if matricule and not any(
        _normalize_matricule(e.time_tracking_id) == _normalize_matricule(matricule)
        for e in roster
    ):
        proposal.warnings.append(
            f"Matricule {matricule} absent du dossier EYWAI — "
            f"rapprochement par nom « {ocr_last} »."
        )

    if not _first_name_matches_ocr(ocr_first, chosen.first_name):
        proposal.warnings.append(
            f"Prénom OCR « {ocr_first} » ≠ dossier « {chosen.first_name} » "
            f"(nom de famille utilisé pour le rapprochement)."
        )
        proposal.match_confidence = "medium"
        proposal.review_status = "warning"
    elif len(by_last) == 1:
        proposal.match_confidence = "high"
        proposal.review_status = "ok"
    else:
        proposal.match_confidence = "medium"
        proposal.review_status = "warning"
        proposal.warnings.append(
            f"Correspondance OCR « {raw_name} » → {proposal.matched_name}."
        )

    return proposal


def _fuzzy_name_match(raw_name: str, roster: List[RosterEmployee]) -> List[RosterEmployee]:
    norm_raw = _normalize(raw_name)
    raw_parts = norm_raw.split()
    if len(raw_parts) < 2:
        if len(raw_parts) == 1:
            token = raw_parts[0]
            by_last = _employees_with_last_name(roster, token)
            if len(by_last) == 1:
                return by_last
            by_first = _employees_with_first_name(roster, token)
            if len(by_first) == 1:
                return by_first
        return []
    candidates: List[Tuple[int, RosterEmployee]] = []
    for emp in roster:
        full_a = _normalize(f"{emp.first_name} {emp.last_name}")
        full_b = _normalize(f"{emp.last_name} {emp.first_name}")
        last = _normalize(emp.last_name)
        dist = min(_levenshtein(norm_raw, full_a), _levenshtein(norm_raw, full_b))
        if dist <= 2:
            candidates.append((dist, emp))
            continue
        if len(last) >= 4 and last in norm_raw:
            overlap = len(_tokens(raw_name) & _tokens(f"{emp.first_name} {emp.last_name}"))
            if overlap >= 2:
                candidates.append((3, emp))
            elif len(_employees_with_last_name(roster, emp.last_name)) == 1:
                candidates.append((4, emp))
    candidates.sort(key=lambda x: x[0])
    return [e for _, e in candidates]


def resolve_employee_for_timesheet(
    *,
    raw_name: str,
    matricule: str | None,
    roster: List[RosterEmployee],
) -> AiEmployeeProposal:
    if is_junk_employee_name(raw_name):
        proposal = AiEmployeeProposal(raw_name=raw_name or "")
        proposal.time_tracking_id = matricule
        proposal.warnings.append(f"Ligne ignorée (texte OCR non salarié) : « {raw_name} ».")
        proposal.match_method = "none"
        proposal.review_status = "error"
        return proposal

    proposal = AiEmployeeProposal(raw_name=raw_name or "")
    proposal.time_tracking_id = matricule
    norm_mat = _normalize_matricule(matricule)

    if norm_mat:
        mat_matches = [
            e
            for e in roster
            if _normalize_matricule(e.time_tracking_id) == norm_mat
        ]
        if len(mat_matches) == 1:
            emp = mat_matches[0]
            proposal.employee_id = emp.id
            proposal.matched_name = f"{emp.first_name} {emp.last_name}"
            proposal.match_confidence = "high"
            proposal.match_method = "matricule"
            proposal.review_status = "ok"
            return proposal
        if len(mat_matches) > 1:
            proposal.warnings.append(
                f"Matricule {norm_mat} : plusieurs salariés correspondants."
            )
            proposal.match_confidence = "none"
            proposal.match_method = "matricule"
            proposal.review_status = "error"
            return proposal

    if not raw_name or not roster:
        proposal.review_status = "error" if raw_name else "empty"
        return proposal

    norm_raw = _normalize(raw_name)
    exact: List[RosterEmployee] = []
    partial: List[RosterEmployee] = []
    raw_tokens = _tokens(raw_name)

    for emp in roster:
        full_a = _normalize(f"{emp.first_name} {emp.last_name}")
        full_b = _normalize(f"{emp.last_name} {emp.first_name}")
        if norm_raw in (full_a, full_b):
            exact.append(emp)
            continue
        emp_tokens = _tokens(f"{emp.first_name} {emp.last_name}")
        if raw_tokens and raw_tokens.issubset(emp_tokens):
            partial.append(emp)
        elif emp_tokens & raw_tokens:
            overlap = emp_tokens & raw_tokens
            if len(raw_tokens) >= 2:
                partial.append(emp)
            elif len(overlap) >= 2:
                partial.append(emp)
            elif len(overlap) == 1:
                token = next(iter(overlap))
                if len(_employees_with_last_name(roster, token)) == 1:
                    partial.append(emp)
                elif len(_employees_with_first_name(roster, token)) == 1:
                    partial.append(emp)

    if len(exact) == 1:
        emp = exact[0]
        proposal.employee_id = emp.id
        proposal.matched_name = f"{emp.first_name} {emp.last_name}"
        proposal.match_confidence = "high"
        proposal.match_method = "name_exact"
        proposal.review_status = "ok"
        return proposal

    if len(exact) > 1:
        cegid = _match_by_cegid_name_order(raw_name, roster, matricule=matricule)
        if cegid and cegid.employee_id:
            return cegid
        proposal.warnings.append(
            f"Plusieurs employés correspondent exactement à « {raw_name} »."
        )
        proposal.match_method = "name_exact"
        proposal.review_status = "error"
        return proposal

    cegid_match = _match_by_cegid_name_order(raw_name, roster, matricule=matricule)
    if cegid_match and cegid_match.employee_id:
        return cegid_match

    if len(partial) == 1:
        emp = partial[0]
        proposal.employee_id = emp.id
        proposal.matched_name = f"{emp.first_name} {emp.last_name}"
        proposal.match_confidence = "medium"
        proposal.match_method = "name_exact"
        proposal.review_status = "warning"
        return proposal

    if len(partial) > 1:
        proposal.warnings.append(
            f"« {raw_name} » : plusieurs candidats possibles dans EYWAI "
            "(homonyme ou prénom/nom mal lu par l'OCR — vérifiez le matricule "
            "et associez manuellement au bon salarié)."
        )
        proposal.match_method = "name_exact"
        proposal.review_status = "error"
        return proposal

    fuzzy = _fuzzy_name_match(raw_name, roster)
    if len(fuzzy) == 1:
        emp = fuzzy[0]
        proposal.employee_id = emp.id
        proposal.matched_name = f"{emp.first_name} {emp.last_name}"
        proposal.match_confidence = "medium"
        proposal.match_method = "name_fuzzy"
        proposal.review_status = "warning"
        proposal.warnings.append(
            f"Correspondance approximative OCR « {raw_name} » → "
            f"{proposal.matched_name}."
        )
        return proposal

    if len(fuzzy) > 1:
        proposal.warnings.append(
            f"« {raw_name} » : plusieurs candidats proches — associez manuellement."
        )
        proposal.match_method = "name_fuzzy"
        proposal.review_status = "error"
        return proposal

    proposal.warnings.append(f"Aucun employé reconnu pour « {raw_name} ».")
    if norm_mat:
        proposal.warnings.append(
            f"Matricule {norm_mat} non renseigné dans EYWAI pour ce salarié."
        )
    proposal.match_method = "none"
    proposal.review_status = "error"
    return proposal


def resolve_employee_for_planning_sheet(
    sheet_name: str,
    roster: List[RosterEmployee],
    *,
    exclude_employee_ids: set[str] | None = None,
    hint_name: str | None = None,
) -> AiEmployeeProposal:
    """Rapproche une feuille Excel calendrier (souvent nom de famille seul)."""
    raw = (sheet_name or "").strip()
    proposal = AiEmployeeProposal(raw_name=raw)
    excluded = exclude_employee_ids or set()
    available = [e for e in roster if e.id not in excluded]

    if not raw or not roster:
        proposal.review_status = "empty" if not raw else "error"
        return proposal

    if not available:
        proposal.warnings.append(
            "Tous les salariés du dossier sont déjà associés à une feuille."
        )
        proposal.match_method = "none"
        proposal.review_status = "error"
        return proposal

    candidates = rank_planning_sheet_candidates(
        raw,
        roster,
        exclude_employee_ids=excluded,
        hint_name=hint_name,
        limit=8,
    )
    if len(candidates) > 1 and hint_name:
        picked = _pick_hint_disambiguated_candidate(candidates, hint_name)
        if picked is not None:
            candidates = [picked]

    proposal.warnings.extend(
        _candidate_warnings(raw, candidates, roster, excluded, hint_name)
    )

    if len(candidates) == 1:
        emp = candidates[0]
        proposal.employee_id = emp.id
        proposal.matched_name = f"{emp.first_name} {emp.last_name}"
        proposal.match_confidence = "high" if _is_exact_sheet_match(raw, emp) else "medium"
        proposal.match_method = "name_exact" if proposal.match_confidence == "high" else "name_fuzzy"
        proposal.review_status = "ok" if proposal.match_confidence == "high" else "warning"
        if proposal.review_status == "warning":
            proposal.warnings.append(
                f"Feuille « {raw} » rapprochée de {proposal.matched_name} — confirmez si besoin."
            )
        return proposal

    if len(candidates) > 1:
        labels = ", ".join(f"{e.first_name} {e.last_name}" for e in candidates[:3])
        proposal.warnings.append(
            f"Feuille « {raw} » : plusieurs candidats ({labels}…) — choisissez manuellement."
        )
        proposal.match_method = "name_fuzzy"
        proposal.review_status = "error"
        return proposal

    proposal.warnings.append(f"Aucun employé disponible reconnu pour la feuille « {raw} ».")
    proposal.match_method = "none"
    proposal.review_status = "error"
    return proposal


def rank_planning_sheet_candidates(
    sheet_name: str,
    roster: List[RosterEmployee],
    *,
    exclude_employee_ids: set[str] | None = None,
    hint_name: str | None = None,
    limit: int = 5,
) -> List[RosterEmployee]:
    """Classe les salariés candidats pour une feuille (hors déjà associés)."""
    excluded = exclude_employee_ids or set()
    available = [e for e in roster if e.id not in excluded]
    if not available:
        return []

    scored: List[tuple[int, RosterEmployee]] = []
    norm_sheet = _normalize(sheet_name)
    sheet_tokens = _tokens(sheet_name)
    hint_first = _first_name_hint(hint_name)
    hint_norm = _normalize(hint_name or "")

    for emp in available:
        score = _score_planning_candidate(
            emp,
            norm_sheet=norm_sheet,
            sheet_tokens=sheet_tokens,
            hint_name=hint_name,
            hint_norm=hint_norm,
            hint_first=hint_first,
        )
        if score > 0:
            scored.append((score, emp))

    scored.sort(key=lambda item: (-item[0], item[1].last_name, item[1].first_name))
    return [emp for _, emp in scored[:limit]]


def _first_name_hint(hint_name: str | None) -> str:
    if not hint_name:
        return ""
    parts = hint_name.split()
    if len(parts) < 2:
        return ""
    return _normalize(" ".join(parts[1:]))


def _pick_hint_disambiguated_candidate(
    candidates: List[RosterEmployee],
    hint_name: str,
) -> RosterEmployee | None:
    """Désambiguïse via le nom complet du Sommaire Excel."""
    if len(candidates) < 2:
        return None

    hint_norm = _normalize(hint_name)
    full_matches = [
        emp
        for emp in candidates
        if hint_norm
        in (
            _normalize(f"{emp.first_name} {emp.last_name}"),
            _normalize(f"{emp.last_name} {emp.first_name}"),
        )
    ]
    if len(full_matches) == 1:
        return full_matches[0]

    hint_first = _first_name_hint(hint_name)
    if hint_first:
        first_matches = [
            emp
            for emp in candidates
            if _first_name_matches_ocr(hint_first, emp.first_name, strict=True)
        ]
        if len(first_matches) == 1:
            return first_matches[0]

    return None


def _is_exact_sheet_match(sheet_name: str, emp: RosterEmployee) -> bool:
    norm_sheet = _normalize(sheet_name)
    return norm_sheet == _normalize(emp.last_name)


def _score_planning_candidate(
    emp: RosterEmployee,
    *,
    norm_sheet: str,
    sheet_tokens: set[str],
    hint_name: str | None,
    hint_norm: str,
    hint_first: str,
) -> int:
    score = 0
    last_norm = _normalize(emp.last_name)
    full_a = _normalize(f"{emp.first_name} {emp.last_name}")
    full_b = _normalize(f"{emp.last_name} {emp.first_name}")
    emp_tokens = _tokens(f"{emp.first_name} {emp.last_name}")

    if norm_sheet == last_norm:
        score += 100
    if norm_sheet in (full_a, full_b):
        score += 95
    if sheet_tokens and sheet_tokens.issubset(emp_tokens):
        score += 80
    elif emp_tokens.issubset(sheet_tokens) and len(sheet_tokens) >= 2:
        score += 75
    elif len(last_norm) >= 4 and (last_norm in norm_sheet or norm_sheet in last_norm):
        score += 55

    if hint_norm:
        if hint_norm in (full_a, full_b):
            score += 90
        elif hint_norm in full_a or full_a in hint_norm or full_b in hint_norm:
            score += 70
        hint_tokens = _tokens(hint_name or "")
        overlap = hint_tokens & emp_tokens
        if overlap:
            score += 20 + 10 * len(overlap)
        if hint_first and _first_name_matches_ocr(hint_first, emp.first_name):
            score += 35

    if score > 0 and score < 100:
        dist = min(
            _levenshtein(norm_sheet, full_a),
            _levenshtein(norm_sheet, full_b),
            _levenshtein(norm_sheet, last_norm),
        )
        if dist <= 2:
            score += 10

    return score


def _candidate_warnings(
    raw: str,
    candidates: List[RosterEmployee],
    roster: List[RosterEmployee],
    excluded: set[str],
    hint_name: str | None,
) -> List[str]:
    warnings: List[str] = []
    if hint_name and hint_name.strip() and hint_name.strip().lower() != raw.lower():
        warnings.append(f"Indice Sommaire : « {hint_name.strip()} ».")
    if excluded:
        blocked = rank_planning_sheet_candidates(
            raw,
            roster,
            exclude_employee_ids=set(),
            hint_name=hint_name,
            limit=1,
        )
        if (
            blocked
            and blocked[0].id in excluded
            and (not candidates or candidates[0].id != blocked[0].id)
        ):
            blocked_emp = blocked[0]
            warnings.append(
                "Le rapprochement le plus probable "
                f"({blocked_emp.first_name} {blocked_emp.last_name}) "
                "est déjà pris par une autre feuille."
            )
    return warnings


__all__ = [
    "ReviewStatus",
    "is_junk_employee_name",
    "rank_planning_sheet_candidates",
    "resolve_employee_for_planning_sheet",
    "resolve_employee_for_timesheet",
]
