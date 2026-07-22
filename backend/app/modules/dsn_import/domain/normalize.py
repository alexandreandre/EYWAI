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


def nir_match_key(nir: Optional[str]) -> str:
    """Clé de rapprochement d'un NIR entre la base (15 caractères) et la DSN (13).

    Un NIR complet fait 15 caractères = NIR (13) + clé de contrôle (2). La DSN
    émet fréquemment le NIR à 13 caractères (sans la clé). Pour rapprocher les
    deux, on réduit tout NIR de 15 caractères à ses 13 premiers.

    On tronque par nombre de caractères (et non en filtrant les chiffres) afin de
    préserver les NIR corses, dont le département 2A/2B introduit une lettre.
    Un identifiant non standard (NTT, longueur ≠ 13/15) est renvoyé nettoyé, sans
    troncature.
    """
    if not nir:
        return ""
    clean = "".join(str(nir).split()).replace("-", "").replace(".", "").replace("/", "").upper()
    if len(clean) == 15:
        return clean[:13]
    return clean


def map_contract_type(nature_code: str) -> str:
    code = (nature_code or "").strip().zfill(2)
    return CONTRACT_NATURE_MAP.get(code, "CDI")


def map_statut_cadre(statut_code: str) -> str:
    code = (statut_code or "").strip().zfill(2)
    return "Cadre" if code in STATUT_CADRE_CODES else "Non-Cadre"


def map_temps_partiel(modalite: str, quotite: str) -> tuple[bool, float]:
    """Retourne (is_temps_partiel, duree_hebdomadaire) — interprétation simplifiée (quotité en %)."""
    mod = (modalite or "").strip()
    try:
        q = float((quotite or "100").replace(",", "."))
    except ValueError:
        q = 100.0
    # Modalité 10 = temps partiel, 20 = temps complet (simplifié)
    is_tp = mod in ("10", "12", "13", "14", "15") or q < 100
    heures = round(35.0 * q / 100.0, 2) if q else 35.0
    return is_tp, heures


def _to_float(value: str) -> float:
    try:
        return float((value or "").replace(",", ".").strip())
    except (ValueError, AttributeError):
        return 0.0


def map_temps_partiel_dsn(
    modalite: str,
    unite_quotite: str,
    quotite: str,
    quotite_reference: str,
) -> tuple[bool, float]:
    """Détermine (is_temps_partiel, duree_hebdomadaire) depuis les rubriques contrat P26.

    - Modalité S21.G00.40.014 : 10 = temps plein, 20/21 = temps partiel.
    - Quotité contrat .013 vs quotité de référence entreprise .012 : si la quotité
      du contrat est inférieure à la référence, c'est un temps partiel.
    - Unité .011 : 10 = heures (mensualisées), 12 = forfait jours.
    Les quotités horaires DSN sont mensuelles (ex. 151,67) ; on les convertit en
    durée hebdomadaire (× 12 / 52). Sans information exploitable, on retombe sur le
    temps plein 35 h pour rester cohérent avec le comportement historique.
    """
    mod = (modalite or "").strip()
    unite = (unite_quotite or "").strip()
    q_contrat = _to_float(quotite)
    q_ref = _to_float(quotite_reference)

    if mod == "20" or mod == "21":
        is_tp = True
    elif mod == "10":
        is_tp = False
    elif q_contrat > 0 and q_ref > 0:
        is_tp = q_contrat < q_ref - 0.01
    else:
        is_tp = False

    # Conversion en heures hebdomadaires (seulement si quotité exprimée en heures)
    heures = 35.0
    if unite in ("", "10", "21") and q_contrat > 0:
        # Quotité mensuelle (> 60 h) -> hebdo ; sinon déjà hebdomadaire
        heures = round(q_contrat * 12.0 / 52.0, 2) if q_contrat > 60 else round(q_contrat, 2)
    elif unite in ("", "10", "21") and q_ref > 0 and not is_tp:
        heures = round(q_ref * 12.0 / 52.0, 2) if q_ref > 60 else round(q_ref, 2)

    if heures <= 0:
        heures = 35.0

    # Modalité TP sans quotité exploitable : conserver le flag mais tenter la ref.
    if is_tp and heures >= 35.0 - 0.01 and q_contrat > 0:
        heures = round(q_contrat * 12.0 / 52.0, 2) if q_contrat > 60 else round(q_contrat, 2)
    elif is_tp and heures >= 35.0 - 0.01 and q_ref > 0 and q_contrat > 0:
        heures = round(q_contrat * 12.0 / 52.0, 2) if q_contrat > 60 else round(q_contrat, 2)

    from app.modules.employees.domain.rules import normalize_temps_travail_fields

    return normalize_temps_travail_fields(is_tp, heures)


def map_sexe(code: str) -> Optional[str]:
    """Code sexe DSN (S21.G00.30.005) -> 'M' / 'F'. 01 = masculin, 02 = féminin."""
    c = (code or "").strip().upper()
    if c in ("01", "1", "M", "H"):
        return "M"
    if c in ("02", "2", "F"):
        return "F"
    return None


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
