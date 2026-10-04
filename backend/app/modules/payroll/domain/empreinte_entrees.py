"""Empreinte stable des données d'entrée d'un bulletin.

À la génération, le bulletin enregistre `payslip_data.parametres.empreinte_entrees`.
Plus tard, on recalcule la même empreinte sur les lectures actuelles : si elle
diffère, le calendrier, les absences, les saisies ou la fiche ont changé depuis
le calcul.

Les cumuls, l'empreinte elle-même et les sorties du calcul (montants, alertes,
PDF) n'y figurent pas : une empreinte qui se contiendrait changerait à chaque
génération, et `employee_schedules.cumuls` est réécrit par le moteur.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Any, Mapping

CLE_EMPREINTE = "empreinte_entrees"

MESSAGE_A_RECALCULER = (
    "Le calendrier ou les absences ont changé depuis le calcul : "
    "recalculez avant de valider"
)

_CLES_IGNOREES = frozenset(
    {
        "cumuls",
        CLE_EMPREINTE,
        "salaire_brut",
        "net_a_payer",
        "alertes_baremes",
        "pdf_storage_path",
        "payroll_events",
        "annee",
        "mois",
        "created_at",
        "updated_at",
        "id",
        "employee_id",
        "company_id",
    }
)

def _jsonable(valeur: Any) -> Any:
    if isinstance(valeur, Decimal):
        return float(valeur)
    if hasattr(valeur, "isoformat") and callable(valeur.isoformat):
        try:
            return valeur.isoformat()
        except (TypeError, ValueError):
            return str(valeur)
    return valeur


def _sans_volatils(valeur: Any) -> Any:
    if isinstance(valeur, Mapping):
        return {
            str(cle): _sans_volatils(sous)
            for cle, sous in valeur.items()
            if str(cle) not in _CLES_IGNOREES
        }
    if isinstance(valeur, list):
        return [_sans_volatils(sous) for sous in valeur]
    return _jsonable(valeur)


def _cle_de_tri(valeur: Any) -> str:
    return json.dumps(valeur, sort_keys=True, ensure_ascii=False, default=str)


def _liste_stable(valeur: Any) -> list[Any]:
    if not isinstance(valeur, list):
        return []
    return sorted((_sans_volatils(item) for item in valeur), key=_cle_de_tri)


def mois_de_la_fenetre(year: int, month: int) -> tuple[tuple[int, int], ...]:
    """M-1, M, M+1 — même fenêtre que le générateur (`payslip_generator.py`)."""
    out: list[tuple[int, int]] = []
    for i in (-1, 0, 1):
        ancre = date(year, month, 15)
        m_offset, y_offset = ancre.month + i, ancre.year
        if m_offset == 0:
            m_offset, y_offset = 12, y_offset - 1
        elif m_offset == 13:
            m_offset, y_offset = 1, y_offset + 1
        out.append((y_offset, m_offset))
    return tuple(out)


def construire_entrees(brut: Mapping[str, Any] | None) -> dict[str, Any]:
    """Dictionnaire canonique : mêmes clés, listes triées, hors champs volatils."""
    source = _sans_volatils(brut or {})
    if not isinstance(source, dict):
        source = {}
    return {
        "calendriers": source.get("calendriers") or {},
        "absences": _liste_stable(source.get("absences")),
        "saisies": _liste_stable(source.get("saisies")),
        "fiche": source.get("fiche") or {},
        "notes_de_frais": _liste_stable(source.get("notes_de_frais")),
        "parametres_societe": source.get("parametres_societe") or {},
        "fenetre_variables": source.get("fenetre_variables") or {},
    }


def empreinte(entrees: dict) -> str:
    """sha256 hex du JSON trié, après canonisation (cumuls et sorties exclus)."""
    texte = json.dumps(
        construire_entrees(entrees),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def etat_a_recalculer(stockee: str | None, actuelle: str | None) -> bool | None:
    """true = périmé, false = à jour, None = inconnu (pas d'empreinte, ou lecture impossible)."""
    if not stockee or not actuelle:
        return None
    return stockee != actuelle


def empreinte_stockee(payslip_data: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payslip_data, Mapping):
        return None
    parametres = payslip_data.get("parametres")
    if not isinstance(parametres, Mapping):
        return None
    valeur = parametres.get(CLE_EMPREINTE)
    if isinstance(valeur, str) and valeur:
        return valeur
    return None


def poser_empreinte(payslip_data: Mapping[str, Any] | None, valeur: str) -> dict[str, Any]:
    """Copie du bulletin avec l'empreinte dans `parametres`, sans muter l'original."""
    return _poser(payslip_data, CLE_EMPREINTE, valeur)


def _poser(payslip_data: Mapping[str, Any] | None, cle: str, valeur: str) -> dict[str, Any]:
    data = dict(payslip_data or {})
    parametres = dict(data.get("parametres") or {}) if isinstance(data.get("parametres"), Mapping) else {}
    parametres[cle] = valeur
    data["parametres"] = parametres
    return data


# --- Cumuls du mois précédent ---------------------------------------------------
#
# Le bulletin de M part des cumuls de M-1 (`employee_schedules.cumuls`) : brut et
# heures de l'année pour la réduction générale régularisée, tranches Agirc-Arrco,
# plafond des heures sup, brut de référence du dixième. Régénérer M-1 réécrit ces
# cumuls, et M — calculé sur les anciens — devient faux sans qu'aucune de ses
# entrées ait bougé. Ils restent hors de l'empreinte d'entrée (le moteur réécrit
# ceux du mois qu'il calcule) ; une empreinte à part, posée à la génération, dit
# si M-1 a changé depuis. Un bulletin d'avant cette empreinte n'en a pas : rien
# n'est dit pour lui.

CLE_EMPREINTE_CUMULS = "empreinte_cumuls_precedents"


def empreinte_cumuls(cumuls: Any) -> str:
    """sha256 des cumuls du mois précédent, tels que lus en base ; absents = vides."""
    texte = json.dumps(
        _jsonable_profond(cumuls or {}),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _jsonable_profond(valeur: Any) -> Any:
    if isinstance(valeur, Mapping):
        return {str(cle): _jsonable_profond(sous) for cle, sous in valeur.items()}
    if isinstance(valeur, list):
        return [_jsonable_profond(sous) for sous in valeur]
    return _jsonable(valeur)


def empreinte_cumuls_stockee(payslip_data: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payslip_data, Mapping):
        return None
    parametres = payslip_data.get("parametres")
    if not isinstance(parametres, Mapping):
        return None
    valeur = parametres.get(CLE_EMPREINTE_CUMULS)
    if isinstance(valeur, str) and valeur:
        return valeur
    return None


def poser_empreinte_cumuls(payslip_data: Mapping[str, Any] | None, valeur: str) -> dict[str, Any]:
    """Copie du bulletin avec l'empreinte des cumuls d'avant, sans muter l'original."""
    return _poser(payslip_data, CLE_EMPREINTE_CUMULS, valeur)


def a_recalculer(entrees: bool | None, cumuls_precedents: bool | None) -> bool | None:
    """Périmé dès que ses entrées ou les cumuls du mois d'avant ont changé.

    Sinon l'état des entrées : false = à jour, None = inconnu (bulletin d'avant
    l'empreinte).
    """
    if entrees is True or cumuls_precedents is True:
        return True
    return entrees
