"""Appariement matricule Cegid <-> employés EYWAI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.payroll.backtest.models import ReferenceBulletin


@dataclass
class EmployeeMatch:
    employee_id: str
    company_id: str
    matricule: str
    first_name: str
    last_name: str
    employee_folder_name: str
    is_forfait_jour: bool
    reference: Optional[ReferenceBulletin] = None


@dataclass
class MatchingResult:
    matched: List[EmployeeMatch] = field(default_factory=list)
    unmatched_employees: List[Dict[str, Any]] = field(default_factory=list)
    unmatched_references: List[str] = field(default_factory=list)


def _normalize(s: str) -> str:
    return "".join(c for c in s.upper() if c.isalnum())


def resolve_company_id(company_name: str) -> str:
    res = (
        supabase.table("companies")
        .select("id, company_name")
        .ilike("company_name", f"%{company_name}%")
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise SystemExit(f"Aucune entreprise trouvée pour '{company_name}'")
    if len(rows) > 1:
        exact = [r for r in rows if r["company_name"].lower() == company_name.lower()]
        if exact:
            return exact[0]["id"]
    return rows[0]["id"]


def load_active_employees(company_id: str) -> List[Dict[str, Any]]:
    res = (
        supabase.table("employees")
        .select(
            "id, company_id, first_name, last_name, employee_folder_name, "
            "is_forfait_jour, employment_status, specificites_paie, nir"
        )
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .execute()
    )
    return res.data or []


def _digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def _base_root(normalized_key: str) -> str:
    """Retire un suffixe numérique de variante ('OSMANI2' -> 'OSMANI').

    Cegid attribue parfois le même matricule (dérivé du nom) à plusieurs
    salariés homonymes ; l'export de référence les distingue alors en
    suffixant '2', '3', ... sur le matricule de base.
    """
    stripped = normalized_key.rstrip("0123456789")
    return stripped or normalized_key


def _prefix_related(a: str, b: str, min_len: int = 4) -> bool:
    """True si l'une des deux chaînes est un préfixe de l'autre (troncature
    Cegid du matricule dérivé du nom, ex. 'ADAMYOUSSE' pour 'ADAM YOUSSEF')."""
    if len(a) < min_len or len(b) < min_len:
        return False
    return a.startswith(b) or b.startswith(a)


def _candidates_for(emp: Dict[str, Any]) -> List[str]:
    folder = emp.get("employee_folder_name") or ""
    last = emp.get("last_name") or ""
    first = emp.get("first_name") or ""
    return [
        c
        for c in (
            _normalize(folder.split("_")[0] if folder else ""),
            _normalize(last),
            _normalize(folder),
            _normalize(f"{last}{first}"),
            _normalize(f"{first}{last}"),
        )
        if c
    ]


def _resolve_ref(
    candidates: List[str],
    first: str,
    ref_by_norm: Dict[str, tuple[str, ReferenceBulletin]],
    refs_by_root: Dict[str, List[tuple[str, ReferenceBulletin]]],
    used_refs: set[str],
    *,
    allow_prefix: bool,
) -> tuple[str, ReferenceBulletin] | None:
    for cand in candidates:
        if allow_prefix:
            roots = {
                _base_root(k)
                for k in ref_by_norm
                if _prefix_related(cand, k) or _prefix_related(cand, _base_root(k))
            }
        else:
            roots = {_base_root(cand)} if cand in ref_by_norm else set()
        variants: List[tuple[str, ReferenceBulletin]] = []
        for root in roots:
            variants.extend(
                (k, v) for k, v in refs_by_root.get(root, []) if k not in used_refs
            )
        if not variants:
            continue
        if len(variants) == 1:
            return variants[0]
        # Plusieurs homonymes/variantes restants : départager par prénom
        # (contenu dans le nom complet extrait du bulletin), sinon 1er dispo.
        by_name = [
            (k, v)
            for k, v in variants
            if first and _normalize(first) in _normalize(v.nom_complet or "")
        ]
        return (by_name or variants)[0]
    return None


def match_employees(
    company_id: str,
    references: Dict[str, ReferenceBulletin],
) -> MatchingResult:
    employees = load_active_employees(company_id)
    ref_by_norm = {_normalize(k): (k, v) for k, v in references.items()}

    # Regroupe les variantes de référence par racine normalisée, pour pouvoir
    # départager les homonymes par prénom plutôt que par ordre d'itération.
    refs_by_root: Dict[str, List[tuple[str, ReferenceBulletin]]] = {}
    for norm_key, (ref_key, ref) in ref_by_norm.items():
        refs_by_root.setdefault(_base_root(norm_key), []).append((ref_key, ref))

    # NIR (numéro de sécurité sociale) par référence : identifiant fiable,
    # non ambigu même quand deux homonymes ont le même nom bleedé depuis la
    # page suivante (cf. SAFIK/SAFI2, tous deux extraits avec le même
    # nom_complet "SAFI Karimullah" par erreur de découpe PDF).
    refs_by_nir: Dict[str, tuple[str, ReferenceBulletin]] = {}
    for ref_key, ref in references.items():
        nir_digits = _digits(ref.nir or "")
        if nir_digits:
            refs_by_nir.setdefault(nir_digits, (ref_key, ref))

    used_refs: set[str] = set()
    matched: List[EmployeeMatch] = []
    still_unmatched: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []

    # Passe 0 : appariement par NIR exact — le plus fiable, à tenter en
    # premier avant toute heuristique sur le nom.
    for emp in employees:
        emp_nir = _digits(emp.get("nir") or "")
        found = refs_by_nir.get(emp_nir) if emp_nir else None
        if found and found[0] not in used_refs:
            ref_key, ref = found
            used_refs.add(ref_key)
            matched.append(
                EmployeeMatch(
                    employee_id=emp["id"],
                    company_id=company_id,
                    matricule=ref_key,
                    first_name=emp.get("first_name") or "",
                    last_name=emp.get("last_name") or "",
                    employee_folder_name=emp.get("employee_folder_name") or "",
                    is_forfait_jour=bool(emp.get("is_forfait_jour")),
                    reference=ref,
                )
            )
        else:
            pending.append(emp)
    employees = pending

    # Passe 1 : correspondance exacte (nom normalisé == clé de référence).
    for emp in employees:
        candidates = _candidates_for(emp)
        found = _resolve_ref(
            candidates,
            emp.get("first_name") or "",
            ref_by_norm,
            refs_by_root,
            used_refs,
            allow_prefix=False,
        )
        if found:
            ref_key, ref = found
            used_refs.add(ref_key)
            matched.append(
                EmployeeMatch(
                    employee_id=emp["id"],
                    company_id=company_id,
                    matricule=ref_key,
                    first_name=emp.get("first_name") or "",
                    last_name=emp.get("last_name") or "",
                    employee_folder_name=emp.get("employee_folder_name") or "",
                    is_forfait_jour=bool(emp.get("is_forfait_jour")),
                    reference=ref,
                )
            )
        else:
            still_unmatched.append(emp)

    # Passe 2 : troncature Cegid des matricules dérivés du nom (ex. noms
    # composés/longs coupés à ~10 caractères, ou suffixés d'une initiale).
    unmatched_employees: List[Dict[str, Any]] = []
    for emp in still_unmatched:
        candidates = _candidates_for(emp)
        found = _resolve_ref(
            candidates,
            emp.get("first_name") or "",
            ref_by_norm,
            refs_by_root,
            used_refs,
            allow_prefix=True,
        )
        if found:
            ref_key, ref = found
            used_refs.add(ref_key)
            matched.append(
                EmployeeMatch(
                    employee_id=emp["id"],
                    company_id=company_id,
                    matricule=ref_key,
                    first_name=emp.get("first_name") or "",
                    last_name=emp.get("last_name") or "",
                    employee_folder_name=emp.get("employee_folder_name") or "",
                    is_forfait_jour=bool(emp.get("is_forfait_jour")),
                    reference=ref,
                )
            )
        else:
            unmatched_employees.append(emp)

    # Passe 3 : dernier recours, par nom complet extrait du corps du bulletin
    # (fiable même quand le matricule est une troncature imprévisible du nom,
    # ex. 'BOUSSANOR' pour BOUSSANOUNE Rachid — un caractère près de la limite
    # de troncature Cegid, insuffisant pour la passe 2).
    final_unmatched: List[Dict[str, Any]] = []
    for emp in unmatched_employees:
        last_norm = _normalize(emp.get("last_name") or "")
        first_norm = _normalize(emp.get("first_name") or "")
        found: tuple[str, ReferenceBulletin] | None = None
        for ref_key, ref in references.items():
            if ref_key in used_refs:
                continue
            nom_norm = _normalize(ref.nom_complet or "")
            if not nom_norm or not last_norm:
                continue
            if last_norm in nom_norm and (not first_norm or first_norm in nom_norm):
                found = (ref_key, ref)
                break
        if found:
            ref_key, ref = found
            used_refs.add(ref_key)
            matched.append(
                EmployeeMatch(
                    employee_id=emp["id"],
                    company_id=company_id,
                    matricule=ref_key,
                    first_name=emp.get("first_name") or "",
                    last_name=emp.get("last_name") or "",
                    employee_folder_name=emp.get("employee_folder_name") or "",
                    is_forfait_jour=bool(emp.get("is_forfait_jour")),
                    reference=ref,
                )
            )
        else:
            final_unmatched.append(emp)

    unmatched_refs = [k for k in references if k not in used_refs]
    return MatchingResult(
        matched=matched,
        unmatched_employees=final_unmatched,
        unmatched_references=unmatched_refs,
    )
