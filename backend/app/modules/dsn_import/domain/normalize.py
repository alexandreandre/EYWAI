"""Normalisation des valeurs DSN vers le modèle EYWAI."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from app.modules.dsn_import.domain.rubriques import CONTRACT_NATURE_MAP, STATUT_CADRE_CODES


def normalize_date_dsn(value: str) -> Optional[str]:
    """Convertit une date DSN (JJMMAAAA ou AAAA-MM-JJ) en ISO YYYY-MM-DD."""
    if not value:
        return None
    clean = value.strip().replace("-", "").replace("/", "")
    if len(clean) == 8 and clean.isdigit():
        # JJMMAAAA
        if int(clean[4:8]) > 1900:
            return f"{clean[4:8]}-{clean[2:4]}-{clean[0:2]}"
        # AAAAMMJJ
        return f"{clean[0:4]}-{clean[4:6]}-{clean[6:8]}"
    try:
        datetime.fromisoformat(value[:10])
        return value[:10]
    except ValueError:
        return None


def map_contract_type(nature_code: str) -> str:
    code = (nature_code or "").strip().zfill(2)
    return CONTRACT_NATURE_MAP.get(code, "CDI")


def map_statut_cadre(statut_code: str) -> str:
    code = (statut_code or "").strip().zfill(2)
    return "Cadre" if code in STATUT_CADRE_CODES else "Non-Cadre"


def map_temps_partiel(modalite: str, quotite: str) -> tuple[bool, float]:
    """Retourne (is_temps_partiel, duree_hebdomadaire)."""
    mod = (modalite or "").strip()
    try:
        q = float((quotite or "100").replace(",", "."))
    except ValueError:
        q = 100.0
    # Modalité 10 = temps partiel, 20 = temps complet (simplifié)
    is_tp = mod in ("10", "12", "13", "14", "15") or q < 100
    heures = round(35.0 * q / 100.0, 2) if q else 35.0
    return is_tp, heures


def build_address_dict(rue: str, cp: str, ville: str) -> Dict[str, Any]:
    return {
        "rue": (rue or "").strip(),
        "code_postal": (cp or "").strip(),
        "ville": (ville or "").strip(),
    }


def flatten_company_address(address: Dict[str, Any]) -> Dict[str, Any]:
    """Remplit aussi les champs à plat utilisés par l'UI RH."""
    return {
        "address": address,
        "adresse_rue": address.get("rue"),
        "adresse_code_postal": address.get("code_postal"),
        "adresse_ville": address.get("ville"),
    }
