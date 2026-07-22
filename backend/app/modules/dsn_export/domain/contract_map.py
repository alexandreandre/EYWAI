"""Mapping contrat / identité EYWAI → codes DSN P26."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from app.modules.dsn_import.domain.rubriques import CONTRACT_NATURE_MAP, STATUT_CADRE_CODES

# Inverse nature contrat
_NATURE_FROM_EYWAI: Dict[str, str] = {}
for code, label in CONTRACT_NATURE_MAP.items():
    _NATURE_FROM_EYWAI.setdefault(label.lower(), code)
_NATURE_FROM_EYWAI.update(
    {
        "cdi": "01",
        "cdd": "02",
        "apprentissage": "29",
        "professionnalisation": "32",
        "contrat de professionnalisation": "32",
        "stage": "50",
        "alternance": "29",
    }
)


def iso_to_dsn_date(value: Any) -> str:
    """Convertit YYYY-MM-DD / date / datetime → JJMMAAAA."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d%m%Y")
    if isinstance(value, date):
        return value.strftime("%d%m%Y")
    text = str(value).strip()
    if not text:
        return ""
    clean = text.replace("/", "-")
    if len(clean) == 8 and clean.isdigit():
        # déjà JJMMAAAA ou AAAAMMJJ
        if int(clean[4:8]) > 1900:
            return clean  # JJMMAAAA
        return f"{clean[6:8]}{clean[4:6]}{clean[0:4]}"
    if len(clean) >= 10 and clean[4] == "-" and clean[7] == "-":
        y, m, d = clean[:10].split("-")
        return f"{d}{m}{y}"
    return ""


def period_to_mois_principal(period: str) -> str:
    """YYYY-MM → 01mmaaaa."""
    year, month = period.split("-")
    return f"01{month}{year}"


def period_bounds(period: str) -> tuple[str, str]:
    """Retourne (début, fin) JJMMAAAA du mois civil."""
    year_s, month_s = period.split("-")
    year, month = int(year_s), int(month_s)
    start = f"01{month:02d}{year}"
    if month == 12:
        next_y, next_m = year + 1, 1
    else:
        next_y, next_m = year, month + 1
    # dernier jour = jour 0 du mois suivant
    last = date(next_y, next_m, 1).fromordinal(
        date(next_y, next_m, 1).toordinal() - 1
    )
    end = last.strftime("%d%m%Y")
    return start, end


def map_contract_nature_to_dsn(contract_type: Optional[str]) -> str:
    if not contract_type:
        return "01"
    key = str(contract_type).strip().lower()
    if key.isdigit():
        return key.zfill(2)
    return _NATURE_FROM_EYWAI.get(key, "01")


def map_statut_to_dsn(statut: Optional[str], *, is_cadre: Optional[bool] = None) -> str:
    """Code statut conventionnel DSN (S21.G00.40.002)."""
    if is_cadre is True:
        return "04"
    if is_cadre is False:
        return "06"
    text = (statut or "").strip().lower()
    if text in {"cadre", "cadres"}:
        return "04"
    if any(c in text for c in STATUT_CADRE_CODES):
        return text.zfill(2) if text.isdigit() else "04"
    return "06"


def map_sexe_to_dsn(sexe: Optional[str]) -> str:
    text = (sexe or "").strip().lower()
    if text in {"1", "01", "m", "h", "homme", "masculin"}:
        return "01"
    if text in {"2", "02", "f", "femme", "feminin", "féminin"}:
        return "02"
    return "01"


def map_modalite_temps(
    *,
    is_temps_partiel: bool = False,
    duree_hebdo: Optional[float] = None,
) -> tuple[str, str, str, str]:
    """Retourne (unité, quotité_ref, quotité, modalité)."""
    # Unité 10 = heures ; quotité mensuelle 151.67 ≈ 35h
    ref = "151.67"
    if is_temps_partiel and duree_hebdo and duree_hebdo > 0:
        q = round(duree_hebdo * 52 / 12, 2)
        return "10", ref, f"{q:.2f}", "20"
    return "10", ref, ref, "10"
