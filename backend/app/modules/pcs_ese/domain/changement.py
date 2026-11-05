"""L'ancien code PCS-ESE et la date du changement, gardés sur la fiche pour la DSN.

Cahier technique DSN 2026.1.2, p. 215 : les rubriques du bloc « Changements Contrat »
(S21.G00.41) « sont à renseigner en cas de modification d'une caractéristique du contrat » et
« doivent être renseignées avec la valeur avant changement ». Guide OETH de l'Urssaf (v2.5,
p. 46) : la correction d'un code PCS-ESE passe par ce bloc, avec l'ancien code
(S21.G00.41.019).

Le changement est rangé dans la classification : `pcs_changement = {"ancien", "date"}`. Seul le
serveur le pose ; ce que le client renvoie est ignoré.
"""

from __future__ import annotations

from datetime import date
from typing import AbstractSet, Any, Dict, Optional

from app.modules.pcs_ese.domain.referentiel import code_valide

CLE = "pcs_changement"


def valide(changement: Any) -> bool:
    return isinstance(changement, dict) and bool(changement.get("ancien")) and bool(changement.get("date"))


def mois_du(changement: Dict[str, Any]) -> str:
    return str(changement["date"])[:7]


def en_attente(changement: Any, periodes_declarees: AbstractSet[str]) -> bool:
    """Le changement n'est pas encore parti : aucune DSN partie pour son mois ou après."""
    if not valide(changement):
        return False
    mois = mois_du(changement)
    return not any(p >= mois for p in periodes_declarees)


def _code(classification: Dict[str, Any]) -> str:
    return str(classification.get("pcs") or "").strip()


def appliquer_changement_pcs(
    avant: Optional[Dict[str, Any]],
    apres: Optional[Dict[str, Any]],
    *,
    aujourd_hui: date,
    depuis_import: bool,
    periodes_declarees: AbstractSet[str],
    debut_contrat: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """La classification à écrire, avec le changement de code posé, gardé ou retiré.

    Rien n'est noté pour un contrat commencé ce mois-ci (jamais déclaré avec l'ancien code) ni
    pour un ancien code hors de la table DSN (S21.G00.41.019 le ferait refuser, CRE-11)."""
    if not isinstance(apres, dict):
        return apres
    avant = avant if isinstance(avant, dict) else {}
    resultat = {k: v for k, v in apres.items() if k != CLE}
    existant = avant.get(CLE) if isinstance(avant.get(CLE), dict) else None
    ancien = _code(avant)
    nouveau = _code(resultat)

    def garder() -> Dict[str, Any]:
        if existant:
            resultat[CLE] = existant
        return resultat

    if depuis_import:
        # Le cabinet a déjà déclaré ce qu'il envoie : rien de neuf à déclarer. Et « 9999 »
        # (profession non connue) ne remplace jamais un vrai code trouvé depuis.
        if ancien and ancien != "9999" and nouveau == "9999":
            resultat["pcs"] = ancien
        return garder()
    if not nouveau or nouveau == ancien or not ancien:
        return garder()
    if en_attente(existant, periodes_declarees):
        premier = str(existant["ancien"])
        if premier == nouveau:
            return resultat
        resultat[CLE] = {"ancien": premier, "date": aujourd_hui.isoformat()}
    else:
        debut_du_mois = f"{aujourd_hui:%Y-%m}-01"
        if not code_valide(ancien) or (debut_contrat and str(debut_contrat)[:10] >= debut_du_mois):
            return resultat
        resultat[CLE] = {"ancien": ancien, "date": aujourd_hui.isoformat()}
    return resultat
