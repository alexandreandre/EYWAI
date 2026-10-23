"""IJSS déduites du maintien sans subrogation : clés et textes du bulletin.

Sans subrogation, la CPAM verse les IJSS au salarié. Quand la société les
déduit du maintien (réglage « Verser le complément, IJSS déduites »), le moteur
pose sur le maintien le montant déduit et sa source : estimées par Martine, ou
part du montant validé dans le suivi IJSS. Ces clés n'existent que si une
déduction a joué : les autres bulletins gardent leur forme.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

CLE_IJSS_DEDUITES = "ijss_deduites"
CLE_SOURCE = "ijss_deduites_source"
SOURCE_ESTIMEES = "estimees"
SOURCE_VALIDEES = "validees"

ALERTE_IJSS_AU_SALARIE = "IJSS versées directement au salarié"

_SOURCE_LONGUE = {
    SOURCE_ESTIMEES: "estimées par Martine",
    SOURCE_VALIDEES: "montant validé dans le suivi IJSS",
}
_SOURCE_COURTE = {SOURCE_ESTIMEES: "estimées", SOURCE_VALIDEES: "validées"}


def _euros(valeur: float) -> str:
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _nombre(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


def montant_deduit(maintien: Optional[Mapping[str, Any]]) -> float:
    """Les IJSS déduites du maintien, 0 s'il n'y en a pas."""
    if not isinstance(maintien, Mapping):
        return 0.0
    return round(_nombre(maintien.get(CLE_IJSS_DEDUITES)), 2)


def _source(maintien: Mapping[str, Any]) -> str:
    source = maintien.get(CLE_SOURCE)
    return source if source in _SOURCE_LONGUE else SOURCE_ESTIMEES


def alerte_ijss_au_salarie(maintien: Optional[Mapping[str, Any]]) -> str:
    """L'alerte d'un arrêt sans subrogation ; elle dit la déduction quand elle joue."""
    deduites = montant_deduit(maintien)
    if deduites <= 0 or not isinstance(maintien, Mapping):
        return ALERTE_IJSS_AU_SALARIE
    return (
        f"{ALERTE_IJSS_AU_SALARIE} : {_euros(deduites)} déduites du maintien "
        f"({_SOURCE_LONGUE[_source(maintien)]})"
    )


def est_alerte_ijss_au_salarie(message: str) -> bool:
    texte = str(message or "").strip()
    return texte == ALERTE_IJSS_AU_SALARIE or texte.startswith(f"{ALERTE_IJSS_AU_SALARIE} :")


def explication_ijss_deduites(maintien: Optional[Mapping[str, Any]]) -> Optional[str]:
    """« D'où viennent ces lignes » : le garanti, moins les IJSS déduites."""
    deduites = montant_deduit(maintien)
    if deduites <= 0 or not isinstance(maintien, Mapping):
        return None
    garanti = round(_nombre(maintien.get("maintien_cible")), 2)
    return (
        f"Complément employeur : salaire garanti {_euros(garanti)} moins "
        f"{_euros(deduites)} d'IJSS versées par la CPAM au salarié "
        f"({_SOURCE_LONGUE[_source(maintien)]})"
    )


def mention_ijss_deduites(maintien: Optional[Mapping[str, Any]]) -> Optional[str]:
    """La note du PDF sous la ligne de maintien."""
    deduites = montant_deduit(maintien)
    if deduites <= 0 or not isinstance(maintien, Mapping):
        return None
    return f"dont IJSS déduites : {_euros(deduites)} ({_SOURCE_COURTE[_source(maintien)]})"
