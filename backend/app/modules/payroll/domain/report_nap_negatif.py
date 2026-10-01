"""Report d'un net à payer négatif sur le mois suivant.

Le moteur ne met pas de plancher au net : un mois d'arrêt complet peut laisser des
cotisations (mutuelle, prévoyance…) supérieures au brut. Rien n'est viré ce
mois-là, et la somme est reprise le mois suivant par une saisie « sur le net »
nommée « Report NAP négatif MM/AAAA » (mois du bulletin négatif).

Sans I/O : partagé par le moteur, l'aperçu du bulletin, les exports et l'API.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

CODE_ALERTE = "net_a_payer_negatif"
CATALOG_PRIME_ID = "report_nap_negatif"
LIBELLE = "Report NAP négatif"
CLE_BULLETIN = "reports_nap_negatif"

MOTIF_EXPORT_NET_NEGATIF = (
    "net à payer négatif : rien à virer ce mois-ci ; "
    "le report sur le mois suivant se propose depuis son bulletin"
)

_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
_NOM = re.compile(r"report\s+nap\s+n[ée]gatif\s+(\d{1,2})/(\d{4})", re.IGNORECASE)


def nom_du_report(annee: int, mois: int) -> str:
    return f"{LIBELLE} {mois:02d}/{annee}"


def mois_suivant(annee: int, mois: int) -> Tuple[int, int]:
    return (annee + 1, 1) if mois == 12 else (annee, mois + 1)


def mois_en_lettres(annee: int, mois: int) -> str:
    return f"{_MOIS[mois - 1]} {annee}"


def euros(montant: float) -> str:
    """115.43 → « 115,43 », −1594.6 → « −1 594,60 » (signe moins typographique)."""
    texte = f"{abs(montant):,.2f}".replace(",", " ").replace(".", ",")
    return f"−{texte}" if montant < 0 else texte


def est_un_report(saisie: Mapping[str, Any]) -> bool:
    """Saisie de report : marquée par le catalogue, ou nommée selon la convention."""
    if str(saisie.get("catalog_prime_id") or "") == CATALOG_PRIME_ID:
        return True
    return bool(_NOM.search(str(saisie.get("name") or "")))


def reports_du_mois(saisies_sur_le_net: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Reports parmi les saisies « sur le net », en retenue positive, pour le bulletin."""
    return [
        {"libelle": str(s.get("name") or LIBELLE), "montant": round(-float(s.get("amount") or 0.0), 2)}
        for s in saisies_sur_le_net
        if est_un_report(s)
    ]


def reports_du_mois(saisies_sur_le_net: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Reports parmi les saisies « sur le net », en retenue positive, pour le bulletin."""
    return [
        {"libelle": str(s.get("name") or LIBELLE), "montant": round(-float(s.get("amount") or 0.0), 2)}
        for s in saisies_sur_le_net
        if est_un_report(s)
    ]


def mois_reporte(nom: str) -> Optional[Tuple[int, int]]:
    """« Report NAP négatif 09/2026 » → (2026, 9)."""
    trouve = _NOM.search(nom or "")
    if not trouve:
        return None
    mois, annee = int(trouve.group(1)), int(trouve.group(2))
    return (annee, mois) if 1 <= mois <= 12 else None


def message_net_negatif(net_a_payer: float, annee: Optional[int], mois: Optional[int]) -> str:
    if annee and mois and 1 <= int(mois) <= 12:
        annee_s, mois_s = mois_suivant(int(annee), int(mois))
        ce_mois = f"en {mois_en_lettres(int(annee), int(mois))}"
        le_suivant = f"en {mois_en_lettres(annee_s, mois_s)}"
    else:
        ce_mois, le_suivant = "ce mois-ci", "le mois suivant"
    return (
        f"Net à payer négatif : {euros(net_a_payer)} €. Rien ne sera viré {ce_mois}. "
        f"Reprenez cette somme {le_suivant}."
    )
