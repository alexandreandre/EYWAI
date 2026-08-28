"""Vue RH des taux de prélèvement à la source."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.pas_rates.domain.model import (
    STATUT_A_JOUR,
    STATUT_A_RAFRAICHIR,
    STATUT_BAREME,
    STATUT_MANQUANT,
    TauxSalarie,
    calculer_statut,
    periode_courante,
    type_label,
)
from app.modules.pas_rates.infrastructure import repository as repo


def _bloc_pas(salarie: Dict[str, Any]) -> Dict[str, Any]:
    specificites = salarie.get("specificites_paie") or {}
    if not isinstance(specificites, dict):
        return {}
    bloc = specificites.get("prelevement_a_la_source") or {}
    return bloc if isinstance(bloc, dict) else {}


def _taux_float(valeur: Any) -> Optional[float]:
    if valeur is None:
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def construire_lignes(
    company_id: str,
    company_name: str = "",
    reference: Optional[str] = None,
) -> List[TauxSalarie]:
    """Une ligne par salarié, avec l'origine et l'ancienneté de son taux."""
    reference = reference or periode_courante()
    salaries = repo.lister_salaries(company_id)
    historique = repo.dernier_taux_par_salarie(company_id)

    lignes: List[TauxSalarie] = []
    for salarie in salaries:
        employee_id = str(salarie.get("id"))
        bloc = _bloc_pas(salarie)
        derniere = historique.get(employee_id) or {}

        taux = _taux_float(bloc.get("taux"))
        type_taux = bloc.get("type_taux") or derniere.get("type_taux") or None
        # La période vient de l'historique quand il existe ; sinon du bloc, qu'on
        # a commencé à dater. Un taux hérité des anciens imports n'en a aucune :
        # on ne sait pas de quel mois il vient, ce que le statut doit dire.
        periode = derniere.get("periode") or bloc.get("periode") or None
        statut = calculer_statut(taux, type_taux, periode, reference)

        lignes.append(
            TauxSalarie(
                employee_id=employee_id,
                nom=str(salarie.get("last_name") or ""),
                prenom=str(salarie.get("first_name") or ""),
                matricule=str(salarie.get("matricule") or ""),
                company_id=company_id,
                company_name=company_name,
                taux=taux,
                type_taux=type_taux,
                identifiant_taux=bloc.get("identifiant_taux") or None,
                periode=periode,
                source=derniere.get("source") or None,
                statut=statut,
            )
        )

    lignes.sort(key=lambda l: (_ordre_statut(l.statut), l.nom, l.prenom))
    return lignes


_ORDRE = {
    STATUT_MANQUANT: 0,
    STATUT_A_RAFRAICHIR: 1,
    STATUT_BAREME: 2,
    STATUT_A_JOUR: 3,
}


def _ordre_statut(statut: str) -> int:
    return _ORDRE.get(statut, 9)


def compteurs(lignes: List[TauxSalarie]) -> Dict[str, int]:
    out = {
        "total": len(lignes),
        STATUT_A_JOUR: 0,
        STATUT_BAREME: 0,
        STATUT_A_RAFRAICHIR: 0,
        STATUT_MANQUANT: 0,
    }
    for ligne in lignes:
        out[ligne.statut] = out.get(ligne.statut, 0) + 1
    return out


def ligne_to_dict(ligne: TauxSalarie) -> Dict[str, Any]:
    return {
        "employee_id": ligne.employee_id,
        "nom": ligne.nom,
        "prenom": ligne.prenom,
        "matricule": ligne.matricule,
        "company_name": ligne.company_name,
        "taux": ligne.taux,
        "type_taux": ligne.type_taux,
        "type_libelle": ligne.type_libelle,
        "identifiant_taux": ligne.identifiant_taux,
        "periode": ligne.periode,
        "source": ligne.source,
        "statut": ligne.statut,
        "statut_libelle": ligne.statut_libelle,
    }


def vue_rh(company_id: str, company_name: str = "") -> Dict[str, Any]:
    lignes = construire_lignes(company_id, company_name)
    return {
        "reference": periode_courante(),
        "compteurs": compteurs(lignes),
        "lignes": [ligne_to_dict(l) for l in lignes],
    }


def historique(employee_id: str) -> List[Dict[str, Any]]:
    rows = repo.historique_salarie(employee_id)
    return [
        {
            "periode": row.get("periode"),
            "taux": _taux_float(row.get("taux")),
            "type_taux": row.get("type_taux"),
            "type_libelle": type_label(row.get("type_taux")),
            "source": row.get("source"),
            "source_fichier": row.get("source_fichier"),
            "applied_at": row.get("applied_at"),
        }
        for row in rows
    ]


def definir_taux_manuel(
    company_id: str,
    employee_id: str,
    taux: float,
    applied_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Écrit un taux saisi à la main par la RH : historique + taux courant.

    La période est le mois courant : un taux manuel vaut à partir d'aujourd'hui
    et sera remplacé par le prochain retour DGFiP plus récent.
    """
    from datetime import datetime

    taux_arrondi = round(float(taux), 2)
    if not 0 <= taux_arrondi <= 100:
        raise ValueError("Le taux doit être compris entre 0 et 100.")
    periode = datetime.now().strftime("%Y-%m")
    repo.enregistrer_taux(
        [
            {
                "company_id": company_id,
                "employee_id": employee_id,
                "periode": periode,
                "taux": taux_arrondi,
                "type_taux": "01",
                "identifiant_taux": None,
                "source": "manuel",
                "source_fichier": None,
                "applied_by": applied_by,
            }
        ]
    )
    repo.maj_taux_courant(employee_id, taux_arrondi, "01", None, periode)
    return {"taux": taux_arrondi, "periode": periode}
