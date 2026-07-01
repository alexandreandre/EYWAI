"""
Résolution employé pour import de relevés : matricule GTA puis nom.

Règle anti-homonyme : jamais de match sur prénom seul si plusieurs candidats.
Format Cegid typique : « MATRICULE NOM prénom(s) » (nom de famille en premier).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Literal, Optional, Tuple

from app.modules.schedules.schemas.ai import AiEmployeeProposal, RosterEmployee
from app.modules.schedules.application.handwritten_weekly import (
    is_handwritten_weekly_format,
)

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


def _word_parts(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalize(value))


def _compact_name(value: str) -> str:
    return "".join(_word_parts(value))


def _first_name_matches_code(code: str, first_name: str) -> bool:
    code_parts = _word_parts(code)
    first_parts = _word_parts(first_name)
    if not code_parts or not first_parts:
        return False

    compact_code = "".join(code_parts)
    initials = "".join(part[0] for part in first_parts if part)
    if compact_code == initials:
        return True

    if len(compact_code) >= 2 and any(
        part.startswith(compact_code) for part in first_parts
    ):
        return True

    return len(compact_code) == 1 and first_parts[0].startswith(compact_code)


def _planning_first_name_code(source: str, last_name: str) -> str:
    source_parts = _word_parts(source)
    last_parts = _word_parts(last_name)
    if not source_parts or not last_parts:
        return ""

    for start in range(0, len(source_parts) - len(last_parts) + 1):
        if source_parts[start : start + len(last_parts)] == last_parts:
            return " ".join(source_parts[start + len(last_parts) :])
    return ""


def is_single_name_allowed(raw_name: str, format_hint: str | None = None) -> bool:
    """Autorise les prénoms seuls sur feuilles manuscrites hebdo."""
    if not is_handwritten_weekly_format(format_hint):
        return False
    raw = (raw_name or "").strip()
    if len(raw.split()) != 1:
        return False
    return re.fullmatch(r"[A-Za-zÀ-ÿ'\-]{3,}", raw) is not None


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


def is_junk_employee_name(raw_name: str, format_hint: str | None = None) -> bool:
    """Filtre les lignes OCR non salarié (pied de page Cegid, en-têtes…)."""
    if not raw_name or not raw_name.strip():
        return True
    if is_single_name_allowed(raw_name, format_hint):
        return False
    if _JUNK_NAME_RE.search(raw_name):
        return True
    parts = raw_name.split()
    if len(parts) < 2:
        return True
    if any(re.fullmatch(r"\d+", p) for p in parts):
        if not re.match(r"^\d{3,6}\s", raw_name.strip()):
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


def _employees_with_last_name(
    roster: List[RosterEmployee], last: str
) -> List[RosterEmployee]:
    norm_last = _normalize(last)
    return [e for e in roster if _normalize(e.last_name) == norm_last]


def _employees_with_first_name(
    roster: List[RosterEmployee], first: str
) -> List[RosterEmployee]:
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
            e
            for e in by_last
            if _first_name_matches_ocr(ocr_first, e.first_name, strict=True)
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


def _fuzzy_name_match(
    raw_name: str, roster: List[RosterEmployee]
) -> List[RosterEmployee]:
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
            overlap = len(
                _tokens(raw_name) & _tokens(f"{emp.first_name} {emp.last_name}")
            )
            if overlap >= 2:
                candidates.append((3, emp))
            elif len(_employees_with_last_name(roster, emp.last_name)) == 1:
                candidates.append((4, emp))
    candidates.sort(key=lambda x: x[0])
    return [e for _, e in candidates]


def _compact_fuzzy_match(
    raw_name: str, roster: List[RosterEmployee]
) -> List[RosterEmployee]:
    """Rattrape les noms dont l'OCR a inséré des espaces au mauvais endroit
    (ex: « F RERE G UV » pour « FRERE Guy », « DOVH OPOL OI » pour
    « DOVHOPOL Oleksandr »). Compare les noms compactés (sans espaces) par
    distance d'édition relative, insensible à la découpe en tokens."""
    compact_raw = _compact_name(raw_name)
    if len(compact_raw) < 6:
        return []

    scored: List[Tuple[int, RosterEmployee]] = []
    for emp in roster:
        compact_last_first = _compact_name(f"{emp.last_name}{emp.first_name}")
        compact_first_last = _compact_name(f"{emp.first_name}{emp.last_name}")
        if not compact_last_first:
            continue
        dist = min(
            _levenshtein(compact_raw, compact_last_first),
            _levenshtein(compact_raw, compact_first_last),
        )
        max_len = max(len(compact_raw), len(compact_last_first))
        if max_len == 0:
            continue
        ratio = 1 - dist / max_len
        if ratio >= 0.6:
            scored.append((dist, emp))

    scored.sort(key=lambda x: x[0])
    if not scored:
        return []
    if len(scored) == 1:
        return [scored[0][1]]
    # N'accepte un candidat unique que s'il se détache nettement du suivant ;
    # sinon on remonte tous les candidats proches pour arbitrage manuel.
    if scored[0][0] + 2 <= scored[1][0]:
        return [scored[0][1]]
    return [e for _, e in scored]


def resolve_employee_for_timesheet(
    *,
    raw_name: str,
    matricule: str | None,
    roster: List[RosterEmployee],
    format_hint: str | None = None,
) -> AiEmployeeProposal:
    single_tokens = _normalize(raw_name).split()
    if len(single_tokens) == 1 and roster:
        token = single_tokens[0]
        by_first = _employees_with_first_name(roster, token)
        if len(by_first) == 1:
            emp = by_first[0]
            proposal = AiEmployeeProposal(raw_name=raw_name or "")
            proposal.time_tracking_id = matricule
            proposal.employee_id = emp.id
            proposal.matched_name = f"{emp.first_name} {emp.last_name}"
            proposal.match_confidence = "medium"
            proposal.match_method = "name_exact"
            proposal.review_status = "warning"
            proposal.warnings.append(
                f"Prénom seul « {raw_name} » rapproché de {proposal.matched_name}."
            )
            return proposal
        if len(by_first) > 1:
            proposal = AiEmployeeProposal(raw_name=raw_name or "")
            proposal.time_tracking_id = matricule
            labels = ", ".join(f"{e.first_name} {e.last_name}" for e in by_first[:3])
            proposal.warnings.append(
                f"Prénom seul « {raw_name} » ambigu ({labels}) — associez manuellement."
            )
            proposal.match_method = "name_exact"
            proposal.review_status = "error"
            return proposal

    if is_junk_employee_name(raw_name, format_hint=format_hint):
        proposal = AiEmployeeProposal(raw_name=raw_name or "")
        proposal.time_tracking_id = matricule
        proposal.warnings.append(
            f"Ligne ignorée (texte OCR non salarié) : « {raw_name} »."
        )
        proposal.match_method = "none"
        proposal.review_status = "error"
        return proposal

    proposal = AiEmployeeProposal(raw_name=raw_name or "")
    proposal.time_tracking_id = matricule
    norm_mat = _normalize_matricule(matricule)

    if norm_mat:
        mat_matches = [
            e for e in roster if _normalize_matricule(e.time_tracking_id) == norm_mat
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

    compact_fuzzy = _compact_fuzzy_match(raw_name, roster)
    if len(compact_fuzzy) == 1:
        emp = compact_fuzzy[0]
        proposal.employee_id = emp.id
        proposal.matched_name = f"{emp.first_name} {emp.last_name}"
        proposal.match_confidence = "medium"
        proposal.match_method = "name_fuzzy"
        proposal.review_status = "warning"
        proposal.warnings.append(
            f"Nom OCR fragmenté « {raw_name} » reconstruit → "
            f"{proposal.matched_name} (à vérifier)."
        )
        return proposal

    if len(compact_fuzzy) > 1:
        labels = ", ".join(f"{e.first_name} {e.last_name}" for e in compact_fuzzy[:3])
        proposal.warnings.append(
            f"« {raw_name} » (OCR fragmenté) : plusieurs candidats proches "
            f"({labels}) — associez manuellement."
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
    precomputed_candidates: List[RosterEmployee] | None = None,
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

    if precomputed_candidates is not None:
        candidates = [e for e in precomputed_candidates if e.id not in excluded][:8]
    else:
        candidates = rank_planning_sheet_candidates(
            raw,
            roster,
            exclude_employee_ids=excluded,
            hint_name=hint_name,
            limit=8,
        )
    exact_candidates = [emp for emp in candidates if _is_exact_sheet_match(raw, emp)]
    if len(exact_candidates) == 1:
        candidates = exact_candidates
    if len(candidates) > 1:
        picked = _pick_planning_code_disambiguated_candidate(candidates, raw)
        if picked is not None:
            candidates = [picked]
    if len(candidates) > 1 and hint_name:
        picked = _pick_planning_code_disambiguated_candidate(candidates, hint_name)
        if picked is None:
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
        proposal.match_confidence = (
            "high" if _is_confident_planning_match(raw, emp, hint_name) else "medium"
        )
        proposal.match_method = (
            "name_exact" if proposal.match_confidence == "high" else "name_fuzzy"
        )
        proposal.review_status = (
            "ok" if proposal.match_confidence == "high" else "warning"
        )
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

    first_name_match = _pick_unique_first_name_hint_candidate(
        available, hint_name, raw
    )
    if first_name_match is not None:
        proposal.employee_id = first_name_match.id
        proposal.matched_name = f"{first_name_match.first_name} {first_name_match.last_name}"
        proposal.match_confidence = "high"
        proposal.match_method = "name_fuzzy"
        proposal.review_status = "ok"
        proposal.warnings.append(
            f"Indice « {hint_name} » rapproché par prénom unique de {proposal.matched_name}."
        )
        return proposal

    proposal.warnings.append(
        f"Aucun employé disponible reconnu pour la feuille « {raw} »."
    )
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
            if _planning_first_name_code(hint_name, emp.last_name)
            and _first_name_matches_ocr(hint_first, emp.first_name, strict=True)
        ]
        if len(first_matches) == 1:
            return first_matches[0]

    return None


def _pick_planning_code_disambiguated_candidate(
    candidates: List[RosterEmployee],
    source: str,
) -> RosterEmployee | None:
    """Désambiguïse les feuilles NOM + initiales/préfixe prénom."""
    if len(candidates) < 2 or not source:
        return None

    matches = [
        emp
        for emp in candidates
        if (
            code := _planning_first_name_code(source, emp.last_name)
        )
        and _first_name_matches_code(code, emp.first_name)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _pick_unique_first_name_hint_candidate(
    available: List[RosterEmployee],
    hint_name: str | None,
    sheet_name: str,
) -> RosterEmployee | None:
    if not available or not hint_name:
        return None
    if len(_word_parts(sheet_name)) < 2:
        return None
    hint_first = _planning_first_name_code(hint_name, sheet_name)
    if not hint_first:
        return None
    matches = [
        emp
        for emp in available
        if _first_name_matches_ocr(hint_first, emp.first_name, strict=True)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _is_exact_sheet_match(sheet_name: str, emp: RosterEmployee) -> bool:
    norm_sheet = _normalize(sheet_name)
    return norm_sheet == _normalize(emp.last_name) or _compact_name(
        sheet_name
    ) == _compact_name(emp.last_name)


def _is_confident_planning_match(
    sheet_name: str,
    emp: RosterEmployee,
    hint_name: str | None,
) -> bool:
    if _is_exact_sheet_match(sheet_name, emp):
        return True

    raw_code = _planning_first_name_code(sheet_name, emp.last_name)
    if raw_code and _first_name_matches_code(raw_code, emp.first_name):
        return True

    if hint_name:
        hint_norm = _normalize(hint_name)
        full_a = _normalize(f"{emp.first_name} {emp.last_name}")
        full_b = _normalize(f"{emp.last_name} {emp.first_name}")
        if hint_norm in (full_a, full_b):
            return True

        hint_code = _planning_first_name_code(hint_name, emp.last_name)
        if hint_code and _first_name_matches_code(hint_code, emp.first_name):
            return True

        sheet_compact = _compact_name(sheet_name)
        last_compact = _compact_name(emp.last_name)
        hint_first = _first_name_hint(hint_name)
        if (
            sheet_compact
            and last_compact
            and sheet_compact in last_compact
            and hint_first
            and _first_name_matches_ocr(hint_first, emp.first_name, strict=True)
        ):
            return True

    return False


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
    last_compact = _compact_name(emp.last_name)
    sheet_compact = _compact_name(norm_sheet)
    hint_compact = _compact_name(hint_name or "")
    full_a = _normalize(f"{emp.first_name} {emp.last_name}")
    full_b = _normalize(f"{emp.last_name} {emp.first_name}")
    emp_tokens = _tokens(f"{emp.first_name} {emp.last_name}")

    if norm_sheet == last_norm or (sheet_compact and sheet_compact == last_compact):
        score += 100
    if norm_sheet in (full_a, full_b):
        score += 95
    if sheet_tokens and sheet_tokens.issubset(emp_tokens):
        score += 80
    elif emp_tokens.issubset(sheet_tokens) and len(sheet_tokens) >= 2:
        score += 75
    elif (
        len(last_compact) >= 4
        and sheet_compact
        and (last_compact in sheet_compact or sheet_compact in last_compact)
    ):
        score += 55

    if hint_norm:
        if hint_norm in (full_a, full_b):
            score += 90
        elif hint_norm in full_a or full_a in hint_norm or full_b in hint_norm:
            score += 70
        hint_tokens = _tokens(hint_name or "")
        last_tokens = _tokens(emp.last_name)
        hint_has_last = (
            bool(last_compact)
            and bool(hint_compact)
            and (last_compact in hint_compact or hint_compact in last_compact)
        ) or (bool(last_tokens) and last_tokens.issubset(hint_tokens))
        overlap = hint_tokens & emp_tokens
        if hint_has_last and overlap:
            score += 20 + 10 * len(overlap)
        if (
            hint_first
            and hint_has_last
            and _planning_first_name_code(hint_name or "", emp.last_name)
            and _first_name_matches_ocr(hint_first, emp.first_name)
        ):
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


_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1, "none": 0}
_STATUS_RANK = {"ok": 3, "warning": 2, "error": 1, "empty": 0}


def deduplicate_employee_matches(
    employees: List[AiEmployeeProposal],
) -> List[AiEmployeeProposal]:
    """Un même salarié ne doit jamais être rapproché par deux lignes du même
    document (ex: deux noms OCR différents matchés au même employee_id, ou le
    même salarié présent sur deux fichiers d'un import multi-fichiers). En cas
    de collision, on garde la ligne la plus fiable et on repasse les autres en
    attente d'association manuelle plutôt que d'écraser silencieusement les
    heures de l'une par l'autre."""
    by_employee: Dict[str, List[int]] = {}
    for idx, emp in enumerate(employees):
        if emp.employee_id:
            by_employee.setdefault(emp.employee_id, []).append(idx)

    for indices in by_employee.values():
        if len(indices) < 2:
            continue

        def _rank(i: int) -> tuple:
            emp = employees[i]
            return (
                _CONFIDENCE_RANK.get(emp.match_confidence or "none", 0),
                _STATUS_RANK.get(emp.review_status or "error", 0),
                len(emp.days),
            )

        best_idx = max(indices, key=_rank)
        winner = employees[best_idx]
        for idx in indices:
            if idx == best_idx:
                continue
            loser = employees[idx]
            loser.employee_id = None
            loser.matched_name = None
            loser.match_confidence = "none"
            loser.match_method = "none"
            loser.review_status = "error"
            loser.warnings.append(
                f"Même salarié que « {winner.raw_name} » (déjà rapproché à "
                f"{winner.matched_name or winner.raw_name}) — associez "
                "manuellement le bon salarié."
            )

    return employees


__all__ = [
    "ReviewStatus",
    "deduplicate_employee_matches",
    "is_junk_employee_name",
    "is_single_name_allowed",
    "rank_planning_sheet_candidates",
    "resolve_employee_for_planning_sheet",
    "resolve_employee_for_timesheet",
]
