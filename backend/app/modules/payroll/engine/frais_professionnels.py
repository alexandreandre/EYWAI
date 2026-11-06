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

#: Réglage de société : garder ses frais dans le montant net social, comme
#: l'ancien logiciel le fait dans cette société (spécificité S27) : les notes de
#: frais du module, et ses saisies de frais classées comme avant le 04/11/2026
#: (`est_une_saisie_de_frais`). Ne se retire qu'avec l'accord d'Alexandre.
REGLAGE_NOTES_DANS_MNS = "notes_de_frais_dans_mns"

#: Libellés d'une saisie non soumise qui rembourse des frais (repas, déplacement,
#: notes de frais).
_LIBELLES_FRAIS = (
    "panier",
    "indemnité forfaitaire",
    "indemnite forfaitaire",
    "déplacement",
    "deplacement",
    "rbst note de frais",
    "note de frais",
)
#: Notes de frais au pluriel, trajet domicile-travail et indemnités
#: kilométriques : des frais aussi (BOSS, Montant net social, II.A.1 : « trajet
#: domicile-travail »), restés dans le MNS jusqu'au 04/11/2026 (audit, verdict
#: D 1c).
_LIBELLES_FRAIS_AJOUTES = ("notes de frais", "transport", "kilom", " kms")


def notes_de_frais_dans_le_mns(company_data: Mapping[str, Any] | None) -> bool:
    reglages = (company_data or {}).get("settings") or {}
    return reglages.get(REGLAGE_NOTES_DANS_MNS) is True


def est_un_frais_professionnel(ligne: Mapping[str, Any]) -> bool:
    return bool(ligne.get(CLE_FRAIS_PROFESSIONNELS))


def est_une_saisie_de_frais(row: Mapping[str, Any], *, frais_dans_mns: bool = False) -> bool:
    """Une saisie du mois qui rembourse des frais professionnels : non soumise,
    positive, au libellé de frais (panier, note de frais, déplacement, trajet).

    Versée au net à payer, jamais dans le montant net social (BOSS, II.A.1 et
    question 26) : paniers non soumis compris, quelle que soit la convention
    (audit du 03/11/2026, verdict D 1c ; le réglage de société qui les y
    remettait n'est plus lu).

    `frais_dans_mns` : la société garde ses frais dans le MNS (réglage
    `notes_de_frais_dans_mns`, S27). Son classement d'avant ne bouge pas : ses
    « Remboursement de notes de frais » et ses indemnités de trajet restent des
    éléments du MNS, comme dans l'ancien logiciel.
    """
    if float(row.get("amount") or 0) <= 0:
        return False
    if row.get("is_socially_taxed", True):
        return False
    libelle = " ".join(str(row.get(cle) or "") for cle in ("name", "description")).lower()
    if frais_dans_mns:
        if "remboursement de note" in libelle:
            return False
        return any(terme in libelle for terme in _LIBELLES_FRAIS)
    return any(terme in libelle for terme in _LIBELLES_FRAIS + _LIBELLES_FRAIS_AJOUTES)


def libelle_de_note_de_frais(type_de_frais: Any, jour: Any) -> str:
    """« Note de frais : restaurant du 07/10/2026 », « Note de frais : indemnités
    kilométriques du 08/10/2026 » : une seule famille de libellés. Les indemnités
    kilométriques avaient leur propre forme (« Indemnités kilométriques du … »),
    à côté de « Note de frais : … » sur le même bulletin (rejeu G.5)."""
    texte = str(jour or "")[:10]
    annee, mois, j = (texte.split("-") + ["", "", ""])[:3]
    date_fr = f"{j}/{mois}/{annee}" if annee and mois and j else texte
    nature = str(type_de_frais or "").strip()
    if not nature or nature.lower() == "autre":
        return f"Note de frais du {date_fr}"
    return f"Note de frais : {nature.lower()} du {date_fr}"


def entree_de_note_de_frais(
    expense: Mapping[str, Any], *, dans_le_mns: bool
) -> dict[str, Any]:
    """Une note de frais validée du module, telle que le générateur la passe au moteur."""
    entree: dict[str, Any] = {
        "prime_id": f"remb_{str(expense['type']).lower().replace(' ', '_')}_{expense['date']}",
        "libelle": libelle_de_note_de_frais(expense.get("type"), expense.get("date")),
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
