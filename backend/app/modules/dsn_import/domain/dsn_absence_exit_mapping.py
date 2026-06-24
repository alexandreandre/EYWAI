"""Mapping motifs DSN → enums EYWAI (absences / sorties)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.domain.normalize import normalize_date_dsn

# Motifs fin de contrat DSN (S21.G00.62.002) → ExitType EYWAI
EXIT_MOTIF_MAP: Dict[str, str] = {
    "011": "demission",
    "012": "demission",
    "014": "licenciement",
    "015": "licenciement",
    "020": "rupture_conventionnelle",
    "025": "depart_retraite",
    "026": "depart_retraite",
    "031": "licenciement",
    "032": "licenciement",
    "033": "licenciement",
    "034": "licenciement",
    "035": "licenciement",
    "036": "licenciement",
    "037": "fin_periode_essai",
    "038": "fin_periode_essai",
    "039": "demission",
    "043": "rupture_conventionnelle",
    "098": "demission",
    "099": "demission",
}

# Motif suspension G00.60 → type absence
SUSPENSION_ABSENCE_MAP: Dict[str, str] = {
    "01": "sans_solde",
    "02": "sans_solde",
    "03": "arret_maladie",
}

# Codes arrêt G00.41 (si .004 renseigné) → (AbsenceType, ArretType)
ARRET_MOTIF_MAP: Dict[str, Tuple[str, Optional[str]]] = {
    "01": ("arret_maladie", "maladie_simple"),
    "02": ("arret_at", "accident_travail"),
    "03": ("arret_maladie_pro", "maladie_professionnelle"),
    "04": ("arret_maternite", None),
    "05": ("arret_paternite", None),
}


def map_exit_motif(motif: str) -> str:
    code = (motif or "").strip().zfill(3)[:3]
    return EXIT_MOTIF_MAP.get(code, "demission")


def map_suspension_to_absence(motif: str) -> str:
    code = (motif or "").strip().zfill(2)[:2]
    return SUSPENSION_ABSENCE_MAP.get(code, "sans_solde")


def map_arret_motif(motif: str) -> Tuple[str, Optional[str]]:
    code = (motif or "").strip().zfill(2)[:2]
    return ARRET_MOTIF_MAP.get(code, ("arret_maladie", "maladie_simple"))


def daterange_days(start: date, end: date) -> List[date]:
    if end < start:
        return [start]
    days: List[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def build_absence_payload_from_arret(
    arret: Any,
    *,
    siret: str,
    nir: str,
    employee_label: str,
) -> Optional[Dict[str, Any]]:
    """Construit un payload preview absence depuis un bloc G00.41."""
    start_raw = arret.date_debut or arret.rubriques.get("S21.G00.41.001", "")
    start = normalize_date_dsn(start_raw)
    if not start:
        return None

    end_raw = arret.date_fin or arret.rubriques.get("S21.G00.41.004", "")
    end = normalize_date_dsn(end_raw) or start

    motif = arret.motif or arret.rubriques.get("S21.G00.41.003", "")
    absence_type, arret_type = map_arret_motif(motif)

    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except ValueError:
        return None

    selected = daterange_days(start_d, end_d)
    source_key = f"{start}:{end}:{absence_type}"

    return {
        "absence_type": absence_type,
        "arret_type": arret_type,
        "selected_days": [d.isoformat() for d in selected],
        "date_debut": start,
        "date_fin": end,
        "motif_dsn": motif,
        "siret": siret,
        "nir": nir,
        "employee_label": employee_label,
        "source_key": source_key,
        "dsn_block": "G00.41",
    }


def build_absence_payload_from_suspension(
    suspension: Any,
    *,
    siret: str,
    nir: str,
    employee_label: str,
) -> Optional[Dict[str, Any]]:
    start = normalize_date_dsn(suspension.date_debut)
    end = normalize_date_dsn(suspension.date_fin)
    if not start or not end:
        return None

    motif = suspension.motif or suspension.type_suspension or ""
    absence_type = map_suspension_to_absence(motif)

    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except ValueError:
        return None

    selected = daterange_days(start_d, end_d)
    source_key = f"{start}:{end}:{absence_type}:suspension"

    return {
        "absence_type": absence_type,
        "arret_type": None,
        "selected_days": [d.isoformat() for d in selected],
        "date_debut": start,
        "date_fin": end,
        "motif_dsn": motif,
        "siret": siret,
        "nir": nir,
        "employee_label": employee_label,
        "source_key": source_key,
        "dsn_block": "G00.60",
    }


def build_exit_payload_from_fin_contrat(
    fin: Any,
    *,
    siret: str,
    nir: str,
    employee_label: str,
) -> Optional[Dict[str, Any]]:
    lwd = normalize_date_dsn(fin.date_fin)
    if not lwd:
        return None
    motif = fin.motif or ""
    exit_type = map_exit_motif(motif)
    source_key = f"{lwd}:{exit_type}:{motif}"

    return {
        "exit_type": exit_type,
        "last_working_day": lwd,
        "exit_request_date": lwd,
        "motif_dsn": motif,
        "date_notification": normalize_date_dsn(fin.date_notification),
        "siret": siret,
        "nir": nir,
        "employee_label": employee_label,
        "source_key": source_key,
        "dsn_block": "G00.62",
    }
