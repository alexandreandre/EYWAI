"""Remboursements de frais professionnels : versés au net, hors montant net social.

BOSS, Montant net social, II, A, 1 (version en vigueur au 01/10/2026) : ne sont
pas pris en compte « Les remboursements de frais professionnels (au réel ou
forfaitaires) dans la limite de chacun de leurs plafonds d'exonération ». Ils
restent versés au salarié : ils s'ajoutent au net à payer.

Le générateur marque la ligne (`frais_professionnels`) ; le moteur la range
dans les éléments non soumis, et le montant net social la laisse de côté.
"""

from __future__ import annotations

from typing import Any, Mapping

#: Marque d'une ligne non soumise qui rembourse des frais professionnels.
CLE_FRAIS_PROFESSIONNELS = "frais_professionnels"

#: Réglage de société : garder les notes de frais du module dans le montant net
#: social, comme Quadra le fait chez Colorplast (spécificité S27).
REGLAGE_NOTES_DANS_MNS = "notes_de_frais_dans_mns"


def notes_de_frais_dans_le_mns(company_data: Mapping[str, Any] | None) -> bool:
    reglages = (company_data or {}).get("settings") or {}
    return reglages.get(REGLAGE_NOTES_DANS_MNS) is True


def est_un_frais_professionnel(ligne: Mapping[str, Any]) -> bool:
    return bool(ligne.get(CLE_FRAIS_PROFESSIONNELS))


def entree_de_note_de_frais(
    expense: Mapping[str, Any], *, dans_le_mns: bool
) -> dict[str, Any]:
    """Une note de frais validée du module, telle que le générateur la passe au moteur."""
    entree: dict[str, Any] = {
        "prime_id": f"remb_{str(expense['type']).lower().replace(' ', '_')}_{expense['date']}",
        "montant": expense["amount"],
        "soumise_a_cotisations": False,
        "soumise_a_impot": False,
    }
    if not dans_le_mns:
        entree[CLE_FRAIS_PROFESSIONNELS] = True
    return entree


def entree_de_frais_professionnels(row: Mapping[str, Any]) -> dict[str, Any]:
    """Une saisie du mois qui rembourse des frais (panier, déplacement forfaitaire,
    « Rbst note de frais »), telle que le générateur la passe au moteur : une
    ligne à son libellé, jamais fondue dans l'acompte."""
    nom = str(row.get("name") or "")
    entree: dict[str, Any] = {
        "prime_id": row.get("catalog_prime_id") or nom.replace(" ", "_").lower(),
        "libelle": f"{nom} ({row['export_code']})" if row.get("export_code") else nom,
        "montant": float(row.get("amount") or 0.0),
        "soumise_a_cotisations": False,
        "soumise_a_impot": False,
        CLE_FRAIS_PROFESSIONNELS: True,
    }
    if row.get("id"):
        entree["saisie_id"] = str(row["id"])
    return entree


def ligne_de_frais_professionnels(saisie: Mapping[str, Any]) -> dict[str, Any] | None:
    """La ligne non soumise d'un remboursement de frais, ou None si ce n'en est pas un.

    Ni plafond ni réintégration ici : la note du module est un frais réel sur
    justificatif, l'indemnité forfaitaire est saisie dans sa limite.
    """
    if not est_un_frais_professionnel(saisie):
        return None
    prime_id = str(saisie.get("prime_id") or "")
    ligne: dict[str, Any] = {
        "libelle": saisie.get("libelle") or prime_id.replace("_", " "),
        "montant": float(saisie.get("montant") or 0.0),
        "prime_id": prime_id,
        CLE_FRAIS_PROFESSIONNELS: True,
    }
    if saisie.get("saisie_id"):
        ligne["saisie_id"] = str(saisie["saisie_id"])
    return ligne
