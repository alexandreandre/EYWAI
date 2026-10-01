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


def avertissement_virement_ecarte(nom_salarie: str, net_a_payer: float) -> str:
    """Pourquoi un salarié à net ≤ 0 sort de la remise de virements, et quoi faire."""
    if net_a_payer < 0:
        return f"{nom_salarie} : {MOTIF_EXPORT_NET_NEGATIF}"
    return f"{nom_salarie} : net à payer nul : rien à virer ce mois-ci"


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


def statut_qui_verrouille(statuts: Iterable[str]) -> Optional[str]:
    """Un bulletin validé verrouille, même s'il est listé après un brouillon."""
    valeurs = [str(s or "") for s in statuts]
    if "valide" in valeurs:
        return "valide"
    return next((s for s in valeurs if s), None)


def article_de(mot: str) -> str:
    """« de octobre 2026 » → « d’octobre 2026 »."""
    return f"d’{mot}" if mot and mot[0].lower() in "aeiouyéèâîôûh" else f"de {mot}"


def message_verrou_report(
    verrou: str, annee_suivante: int, mois_suivant_: int, *, supprimer: bool
) -> str:
    suivant = mois_en_lettres(annee_suivante, mois_suivant_)
    geste = (
        "impossible d’en retirer le report"
        if supprimer
        else "impossible d’y reporter la somme"
    )
    if verrou == "bulletin_valide":
        return f"Le bulletin {article_de(suivant)} est déjà validé : {geste}."
    return f"La paie {article_de(suivant)} est clôturée : {geste}."


def message_retenue_autre_nom(montant: float, annee_suivante: int, mois_suivant_: int) -> str:
    return (
        f"Une retenue sur le net de {euros(abs(montant))} € existe déjà en "
        f"{mois_en_lettres(annee_suivante, mois_suivant_)}, sous un autre nom. "
        "Ouvrez les saisies avant d’ajouter le report."
    )


def _joindre_montants_euros(montants: Iterable[float]) -> str:
    textes = [f"{euros(abs(float(m)))} €" for m in montants]
    if not textes:
        return ""
    if len(textes) == 1:
        return textes[0]
    return f"{', '.join(textes[:-1])} et {textes[-1]}"


def message_reports_multiples(
    montants: Iterable[float], annee_suivante: int, mois_suivant_: int
) -> str:
    return (
        f"Plusieurs reports existent déjà en {mois_en_lettres(annee_suivante, mois_suivant_)} : "
        f"{_joindre_montants_euros(montants)}. "
        "Chacun est déduit du net tant que la ligne existe. "
        "Ouvrez les saisies pour n’en garder qu’un."
    )


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
