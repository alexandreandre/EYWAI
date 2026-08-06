"""Dépôt d'un fichier de taux : aperçu d'abord, écriture ensuite.

Aucune écriture n'a lieu au dépôt. Les RH voient d'abord ce que le fichier
changerait, salarié par salarié, et confirment. L'opération est rejouable :
redéposer le même fichier ne produit ni doublon ni régression.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.pas_rates.domain import extraction, rapprochement
from app.modules.pas_rates.domain.model import Apercu, periode_valide
from app.modules.pas_rates.infrastructure import repository as repo

logger = get_logger("modules.pas_rates.ingest")

SOURCES = ("dsn", "crm")


class FichierInvalide(ValueError):
    """Le fichier ne peut pas être exploité ; rien n'est écrit."""


def _siren_societe(company_id: str) -> str:
    resp = (
        get_supabase_admin_client()
        .table("companies")
        .select("siren")
        .eq("id", company_id)
        .limit(1)
        .execute()
    )
    return str((resp.data or [{}])[0].get("siren") or "")


def preparer_apercu(
    company_id: str,
    content: bytes,
    file_name: str,
    source: str = "dsn",
) -> Apercu:
    if source not in SOURCES:
        raise FichierInvalide(f"Source inconnue : {source}.")
    if not content:
        raise FichierInvalide("Fichier vide.")

    try:
        dsn_file = extraction.lire_fichier(content, file_name)
    except Exception as exc:  # noqa: BLE001 — on rend l'erreur lisible aux RH
        raise FichierInvalide(f"Fichier illisible : {exc}") from exc

    periode = extraction.periode_du_fichier(dsn_file)
    if not periode_valide(periode):
        raise FichierInvalide(
            "Impossible de dater ce fichier : aucune période exploitable "
            "(bloc déclaration ou versement)."
        )

    siren_fichier = extraction.siren_du_fichier(dsn_file) or ""
    siren_attendu = _siren_societe(company_id)
    if siren_attendu and siren_fichier and siren_fichier != siren_attendu:
        raise FichierInvalide(
            f"Ce fichier concerne le SIREN {siren_fichier}, "
            f"la société sélectionnée est le {siren_attendu}."
        )

    lignes = extraction.extraire_taux(dsn_file)
    if not lignes:
        raise FichierInvalide(
            "Aucun taux de prélèvement à la source dans ce fichier "
            "(bloc versement S21.G00.50 absent ou sans taux)."
        )

    # Les salariés partis sont chargés eux aussi : ils figurent encore dans le
    # fichier du mois qu'ils ont travaillé, et mieux vaut les reconnaître et les
    # écarter que les afficher comme des inconnus.
    salaries = repo.lister_salaries(company_id, inclure_partis=True)
    apercu = rapprochement.construire_apercu(
        lignes,
        salaries,
        periode=periode or "",
        siren=siren_fichier or siren_attendu,
        fichier=file_name,
        source=source,
    )
    for avertissement in dsn_file.parse_warnings:
        if "erreur" in avertissement.lower():
            apercu.avertissements.append(avertissement)
    return apercu


def appliquer(
    company_id: str,
    apercu: Apercu,
    applied_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Écrit l'historique puis rafraîchit le taux courant de chaque salarié."""
    lignes = rapprochement.lignes_a_ecrire(apercu)
    if not lignes:
        return {"appliques": 0, "echecs": [], "historique": 0}

    entrees: List[Dict[str, Any]] = [
        {
            "company_id": company_id,
            "employee_id": ligne.employee_id,
            "periode": apercu.periode,
            "taux": round(float(ligne.taux_fichier or 0.0), 2),
            "type_taux": ligne.type_fichier,
            "identifiant_taux": ligne.identifiant_fichier,
            "source": apercu.source,
            "source_fichier": apercu.fichier,
            "applied_by": applied_by,
        }
        for ligne in lignes
    ]
    historique = repo.enregistrer_taux(entrees)

    appliques = 0
    echecs: List[Dict[str, str]] = []
    for ligne in lignes:
        try:
            repo.maj_taux_courant(
                str(ligne.employee_id),
                float(ligne.taux_fichier or 0.0),
                ligne.type_fichier,
                ligne.identifiant_fichier,
                apercu.periode,
            )
            appliques += 1
        except Exception as exc:  # noqa: BLE001 — une ligne en échec n'annule pas les autres
            logger.warning(
                "Taux PAS non appliqué pour %s : %s", ligne.employee_id, exc
            )
            echecs.append(
                {
                    "employee_id": str(ligne.employee_id),
                    "salarie": f"{ligne.nom} {ligne.prenom}".strip(),
                    "erreur": str(exc),
                }
            )

    logger.info(
        "Taux PAS : %s appliqué(s), %s échec(s), période %s, fichier %s",
        appliques,
        len(echecs),
        apercu.periode,
        apercu.fichier,
    )
    return {"appliques": appliques, "echecs": echecs, "historique": historique}


def apercu_to_dict(apercu: Apercu) -> Dict[str, Any]:
    data = asdict(apercu)
    data["compteurs"] = apercu.compteurs()
    for ligne, brut in zip(apercu.lignes, data["lignes"]):
        brut["type_fichier_libelle"] = ligne.type_fichier_libelle
    return data
