"""La fin connue d'un contrat (05/11/2026) : une lettre signée ne doit jamais dire
« fait partie de nos effectifs » pour quelqu'un dont le contrat est fini.

Au 05/11 sur le test, 26 fiches non marquées « parti » avaient une fin passée : 3
« en sortie » et 23 contrats temporaires « actifs » (sans aucun bulletin après leur
fin). Le statut de la fiche ne suffit donc pas.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Optional


def lire_date(valeur: Any) -> Optional[date]:
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            return date.fromisoformat(valeur.strip()[:10])
        except ValueError:
            return None
    return None


def terme_du_contrat(employee: Mapping[str, Any]) -> Optional[date]:
    """Le terme écrit sur la fiche. Un CDI n'en a pas : l'écran ne montre pas ce champ
    et le vide à l'enregistrement. Pour un apprenti, l'écran l'écrit dans la reprise DSN."""
    genre = str(employee.get("contract_type") or "").lower()
    if "cdi" in genre:
        return None
    terme = lire_date(employee.get("contract_end_date"))
    if terme or "apprentissage" not in genre:
        return terme
    specificites = employee.get("specificites_paie")
    reprise = specificites.get("dsn_reprise") if isinstance(specificites, Mapping) else None
    return lire_date(reprise.get("date_fin_contrat")) if isinstance(reprise, Mapping) else None


def fin_de_contrat(employee: Mapping[str, Any], dernier_jour: Optional[date]) -> Optional[date]:
    """Le dernier jour d'un départ, sinon le terme du contrat.

    Une date antérieure à l'entrée est périmée : c'est celle d'un ancien contrat,
    pour un salarié revenu depuis.
    """
    entree = lire_date(employee.get("hire_date"))
    for fin in (dernier_jour, terme_du_contrat(employee)):
        if fin and (entree is None or fin >= entree):
            return fin
    return None
