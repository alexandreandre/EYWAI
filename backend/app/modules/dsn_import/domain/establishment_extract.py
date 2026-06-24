"""Extraction des paramètres paie entreprise depuis la DSN parsée."""

from __future__ import annotations

import calendar
from typing import Any, Dict, List, Optional, Set

from app.modules.dsn_import.domain.model import (
    ComposantCotisationEtabBlock,
    EtablissementBlock,
    ParsedDsnSet,
)

AT_MP_CODE = "100"

PAYROLL_MERGE_FIELDS = (
    "taux_at_mp",
    "paie_jour_de_fin",
    "paie_occurrence",
    "effectif",
)


def extract_taux_at_mp(etab: EtablissementBlock) -> Optional[float]:
    """Retourne le taux AT/MP (%) : max des composants code 100 sur la période."""
    taux_values: List[float] = []
    for comp in etab.composants_cotisation:
        code = (comp.code or "").strip()
        if code != AT_MP_CODE:
            continue
        if comp.taux and comp.taux > 0:
            taux_values.append(comp.taux)
    if not taux_values:
        return None
    return round(max(taux_values), 4)


def _parse_dsn_day(value: str) -> Optional[int]:
    clean = (value or "").replace("-", "").replace("/", "").strip()
    if len(clean) == 8 and clean.isdigit():
        return int(clean[0:2])
    return None


def _collect_versement_dates(etab: EtablissementBlock) -> List[str]:
    dates: List[str] = []
    for ind in etab.individus:
        for ctr in ind.contrats:
            for ver in ctr.versements:
                d = (ver.date_versement or "").strip()
                if d:
                    dates.append(d)
    return dates


def infer_payroll_calendar(
    etab: EtablissementBlock,
    parsed: Optional[ParsedDsnSet] = None,
) -> Dict[str, Any]:
    """Infère paie_jour_de_fin et paie_occurrence depuis les dates G00.50."""
    dates = _collect_versement_dates(etab)
    days: List[int] = []
    for d in dates:
        day = _parse_dsn_day(d)
        if day is not None:
            days.append(day)

    result: Dict[str, Any] = {
        "paie_jour_de_fin": None,
        "paie_occurrence": None,
        "versement_dates": sorted(set(dates)),
    }
    if not days:
        return result

    max_day = max(days)
    result["paie_jour_de_fin"] = max_day

    year: Optional[int] = None
    month: Optional[int] = None
    for d in dates:
        clean = d.replace("-", "").replace("/", "").strip()
        if len(clean) == 8 and clean.isdigit():
            year = int(clean[4:8])
            month = int(clean[2:4])
            break

    if year and month and max_day >= calendar.monthrange(year, month)[1]:
        result["paie_occurrence"] = -1
    elif len(set(days)) == 1:
        result["paie_occurrence"] = 1
    else:
        result["paie_occurrence"] = len(set(days))

    return result


def build_dsn_organismes_payload(etab: EtablissementBlock) -> List[Dict[str, Any]]:
    """Sérialise les blocs G00.20 pour stockage JSONB entreprise."""
    out: List[Dict[str, Any]] = []
    for org in etab.versements_organismes:
        out.append(
            {
                "identifiant": org.identifiant,
                "libelle": org.libelle,
                "bic": org.bic,
                "iban": org.iban,
                "montant": org.montant,
                "date_debut": org.date_debut,
                "date_fin": org.date_fin,
                "mode_paiement": org.mode_paiement,
            }
        )
    return out


def build_bordereau_payload(etab: EtablissementBlock) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for b in etab.bordereaux:
        out.append(
            {
                "identifiant": b.identifiant,
                "date_debut": b.date_debut,
                "date_fin": b.date_fin,
                "montant": b.montant,
            }
        )
    return out


def enrich_establishment_payload(
    payload: Dict[str, Any],
    etab: EtablissementBlock,
    parsed: Optional[ParsedDsnSet] = None,
) -> Dict[str, Any]:
    """Ajoute les champs paie extraits de la DSN au payload établissement."""
    taux = extract_taux_at_mp(etab)
    calendar = infer_payroll_calendar(etab, parsed)
    dsn_extracted: Dict[str, Any] = {}
    if taux is not None:
        payload["taux_at_mp"] = taux
        dsn_extracted["taux_at_mp"] = taux
    if calendar.get("paie_jour_de_fin") is not None:
        payload["paie_jour_de_fin"] = calendar["paie_jour_de_fin"]
        dsn_extracted["paie_jour_de_fin"] = calendar["paie_jour_de_fin"]
    if calendar.get("paie_occurrence") is not None:
        payload["paie_occurrence"] = calendar["paie_occurrence"]
        dsn_extracted["paie_occurrence"] = calendar["paie_occurrence"]

    orgs = build_dsn_organismes_payload(etab)
    if orgs:
        payload["dsn_organismes"] = orgs
        dsn_extracted["dsn_organismes"] = orgs
    bordereaux = build_bordereau_payload(etab)
    if bordereaux:
        payload["dsn_bordereaux"] = bordereaux
        dsn_extracted["dsn_bordereaux"] = bordereaux

    payload["_dsn_extracted"] = dsn_extracted
    payload["_payroll_conflicts"] = {}
    return payload


def compute_payroll_merge_conflicts(
    payload: Dict[str, Any],
    existing: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Compare champs extraits DSN vs entreprise existante."""
    conflicts: Dict[str, Dict[str, Any]] = {}
    if not existing:
        return conflicts
    for field in PAYROLL_MERGE_FIELDS:
        new_val = payload.get(field)
        if new_val is None:
            continue
        old_val = existing.get(field)
        if old_val is None or old_val == "":
            continue
        if str(old_val) != str(new_val):
            conflicts[field] = {"existing": old_val, "dsn": new_val}
    return conflicts


def apply_payroll_merge(
    payload: Dict[str, Any],
    existing: Optional[Dict[str, Any]],
    apply_fields: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Ne remplit que les champs NULL ou explicitement demandés."""
    merged = dict(payload)
    conflicts = compute_payroll_merge_conflicts(payload, existing)
    merged["_payroll_conflicts"] = conflicts

    if not existing:
        return merged

    for field in PAYROLL_MERGE_FIELDS:
        new_val = payload.get(field)
        if new_val is None:
            merged.pop(field, None)
            continue
        old_val = existing.get(field)
        if field in conflicts:
            if apply_fields and field in apply_fields:
                merged[field] = new_val
            else:
                merged.pop(field, None)
        elif old_val is None or old_val == "":
            merged[field] = new_val
        else:
            merged.pop(field, None)
    return merged
