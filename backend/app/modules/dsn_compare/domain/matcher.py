"""Appariement établissements / salariés entre deux DSN."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.modules.dsn_compare.domain.normalizer import EmployeeSnap, EstablishmentSnap


@dataclass
class EmployeeMatch:
    ref_key: str
    act_key: str
    method: str  # nir | ntt | matricule | name
    quarantine: bool = False


@dataclass
class EstablishmentMatch:
    siret: str
    ref: EstablishmentSnap
    act: EstablishmentSnap
    matched: List[EmployeeMatch] = field(default_factory=list)
    unmatched_ref: List[str] = field(default_factory=list)
    unmatched_act: List[str] = field(default_factory=list)


@dataclass
class MatchResult:
    establishments: List[EstablishmentMatch] = field(default_factory=list)
    unmatched_ref_sirets: List[str] = field(default_factory=list)
    unmatched_act_sirets: List[str] = field(default_factory=list)


def match_employees(
    ref_emps: Dict[str, EmployeeSnap],
    act_emps: Dict[str, EmployeeSnap],
) -> Tuple[List[EmployeeMatch], List[str], List[str]]:
    by_nir: Dict[str, str] = {}
    by_ntt: Dict[str, str] = {}
    by_mat: Dict[str, str] = {}
    by_name: Dict[str, List[str]] = {}
    for key, emp in act_emps.items():
        if emp.nir:
            by_nir[emp.nir] = key
        if emp.ntt:
            by_ntt[emp.ntt] = key
        if emp.matricule:
            by_mat[emp.matricule] = key
        by_name.setdefault(f"{emp.nom}|{emp.prenom}", []).append(key)

    matched: List[EmployeeMatch] = []
    used_act: set[str] = set()
    unmatched_ref: List[str] = []

    for ref_key, ref in ref_emps.items():
        act_key: Optional[str] = None
        method = ""
        quarantine = False
        if ref.nir and ref.nir in by_nir:
            act_key = by_nir[ref.nir]
            method = "nir"
        elif ref.ntt and ref.ntt in by_ntt:
            act_key = by_ntt[ref.ntt]
            method = "ntt"
            quarantine = True
        elif ref.matricule and ref.matricule in by_mat:
            act_key = by_mat[ref.matricule]
            method = "matricule"
            quarantine = True
        else:
            candidates = by_name.get(f"{ref.nom}|{ref.prenom}", [])
            if len(candidates) == 1:
                act_key = candidates[0]
                method = "name"
                quarantine = True
            elif len(candidates) > 1:
                unmatched_ref.append(ref_key)
                continue

        if act_key and act_key not in used_act:
            used_act.add(act_key)
            matched.append(
                EmployeeMatch(
                    ref_key=ref_key,
                    act_key=act_key,
                    method=method,
                    quarantine=quarantine,
                )
            )
        else:
            unmatched_ref.append(ref_key)

    unmatched_act = [k for k in act_emps if k not in used_act]
    return matched, unmatched_ref, unmatched_act


def match_establishments(
    ref_etabs: Dict[str, EstablishmentSnap],
    act_etabs: Dict[str, EstablishmentSnap],
) -> MatchResult:
    result = MatchResult()
    for siret, ref in ref_etabs.items():
        act = act_etabs.get(siret)
        if not act:
            result.unmatched_ref_sirets.append(siret)
            continue
        matched, uref, uact = match_employees(ref.employees, act.employees)
        result.establishments.append(
            EstablishmentMatch(
                siret=siret,
                ref=ref,
                act=act,
                matched=matched,
                unmatched_ref=uref,
                unmatched_act=uact,
            )
        )
    for siret in act_etabs:
        if siret not in ref_etabs:
            result.unmatched_act_sirets.append(siret)
    return result
