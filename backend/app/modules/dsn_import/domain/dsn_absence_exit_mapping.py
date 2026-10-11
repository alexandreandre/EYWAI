"""Mapping motifs DSN → enums MARTINE (absences / sorties)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, Tuple

from app.modules.dsn_import.domain.normalize import normalize_date_dsn
from app.shared.domain.absence_calendar import daterange_days

# Motifs de rupture DSN (S21.G00.62.002) → type de départ de Martine.
# Source : cahier technique DSN 2026.1 (NEODeS, 24/12/2025), rubrique
# S21.G00.62.002 « Motif de la rupture du contrat », p. 273-274 (copie locale
# docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt). Chaque motif va
# au type le plus proche ; la mise à la retraite (038) n'a pas encore de type
# propre et rejoint les départs à la retraite. Le motif d'origine reste dans
# « Import DSN (0xx) » et c'est lui que la DSN de Martine réémet.
EXIT_MOTIF_MAP: Dict[str, str] = {
    # Licenciements et ruptures à l'initiative de l'employeur
    "011": "licenciement",  # liquidation ou redressement judiciaire
    "012": "licenciement",  # fermeture définitive de l'établissement
    "014": "licenciement",  # motif économique
    "015": "licenciement",  # fin de chantier ou d'opération
    "020": "licenciement",  # autre motif
    "025": "licenciement",  # autre fin de contrat pour motif économique
    "026": "licenciement",  # motif économique après acceptation d'un CSP
    "065": "licenciement",  # décès de l'employeur ou internement
    "082": "licenciement",  # résiliation judiciaire
    "083": "licenciement",  # force majeure ou fait du prince
    "086": "licenciement",  # convention CATS
    "087": "licenciement",  # faute grave
    "088": "licenciement",  # faute lourde
    "089": "licenciement",  # force majeure
    "091": "licenciement",  # inaptitude d'origine non professionnelle
    "092": "licenciement",  # inaptitude d'origine professionnelle
    "093": "licenciement",  # décision d'une autorité administrative
    "112": "licenciement",  # accord de performance collective
    "113": "licenciement",  # motif spécifique (L2254-2)
    "115": "licenciement",  # articles 18 et 19 de la loi 2017-1339
    "117": "licenciement",  # motif économique après refus d'un CSP
    # Fins de CDD, de mission ou d'apprentissage, à terme ou anticipées
    "031": "fin_cdd",  # fin de CDD ou fin d'accueil occasionnel
    "032": "fin_cdd",  # fin de mission d'intérim
    "033": "fin_cdd",  # rupture anticipée pour inaptitude
    "036": "fin_cdd",  # rupture anticipée à l'initiative de l'employeur
    "037": "fin_cdd",  # rupture anticipée à l'initiative du salarié
    "081": "fin_cdd",  # fin de contrat d'apprentissage
    "084": "fin_cdd",  # rupture d'un commun accord du CDD, de l'apprentissage, de la mission
    "094": "fin_cdd",  # rupture anticipée pour arrêt de tournage
    "095": "fin_cdd",  # rupture anticipée pour faute grave
    "096": "fin_cdd",  # rupture anticipée pour faute lourde
    "097": "fin_cdd",  # rupture anticipée suite à fermeture de l'établissement
    # Périodes d'essai
    "034": "fin_periode_essai",  # à l'initiative de l'employeur
    "035": "fin_periode_essai",  # à l'initiative du salarié
    # Retraite
    "038": "depart_retraite",  # mise à la retraite par l'employeur
    "039": "depart_retraite",  # départ à la retraite à l'initiative du salarié
    # Ruptures d'un commun accord
    "043": "rupture_conventionnelle",
    "110": "rupture_conventionnelle",  # rupture conventionnelle collective
    "111": "rupture_conventionnelle",  # congé de mobilité
    "114": "rupture_conventionnelle",  # entrée en PAP
    # À l'initiative du salarié
    "058": "demission",  # prise d'acte de la rupture
    "059": "demission",
    # Sans rupture du contrat
    "100": "transfert",  # mutation au sein du groupe
    "998": "transfert",  # transfert vers un autre établissement
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
