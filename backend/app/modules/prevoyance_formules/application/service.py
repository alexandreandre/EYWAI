"""Formules de prévoyance de la société : lire, créer, modifier, appliquer (02/11/2026)."""

from __future__ import annotations

from typing import Any

from app.modules.prevoyance_formules.domain.rules import (
    appliquer_formule,
    fiche_a_mettre_a_jour,
)
from app.modules.prevoyance_formules.schemas import FormuleCreate, FormuleUpdate

INTROUVABLE = "Formule de prévoyance introuvable dans cette société."


class FormuleErreur(Exception):
    """Erreur métier, traduite en réponse HTTP par le routeur."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _depot():
    from app.modules.prevoyance_formules.infrastructure.repository import (
        depot_formules_prevoyance,
    )

    return depot_formules_prevoyance


def _ecrire_prevoyance(employee_id: str, prevoyance: dict[str, Any]) -> None:
    """Le chemin de l'enregistrement d'une fiche (fusion de `specificites_paie`)."""
    from app.modules.employees.application.commands import update_employee

    update_employee(employee_id, {"specificites_paie": {"prevoyance": prevoyance}})


def _formule(formule_id: str, company_id: str) -> dict[str, Any]:
    formule = _depot().lire(formule_id, company_id)
    if not formule:
        raise FormuleErreur(404, INTROUVABLE)
    return formule


def _fiches_a_mettre_a_jour(formule: dict[str, Any], company_id: str) -> list[dict[str, Any]]:
    return [
        fiche
        for fiche in _depot().fiches_de_la_societe(company_id)
        if fiche_a_mettre_a_jour(fiche.get("specificites_paie"), formule)
    ]


def lister_formules(company_id: str) -> list[dict[str, Any]]:
    return _depot().lister(company_id)


def creer_formule(company_id: str, user_id: str, donnees: FormuleCreate) -> dict[str, Any]:
    return _depot().creer(
        {
            "company_id": company_id,
            "created_by": user_id,
            "libelle": donnees.libelle.strip(),
            "statut_categoriel": donnees.statut_categoriel,
            "lignes": [ligne.en_ligne() for ligne in donnees.lignes],
        }
    )


def modifier_formule(formule_id: str, company_id: str, donnees: FormuleUpdate) -> dict[str, Any]:
    """La formule modifiée, et le nombre de fiches qui ont encore ses anciennes lignes."""
    _formule(formule_id, company_id)
    patch: dict[str, Any] = {}
    if donnees.libelle is not None:
        patch["libelle"] = donnees.libelle.strip()
    if donnees.statut_categoriel is not None:
        patch["statut_categoriel"] = donnees.statut_categoriel
    if donnees.lignes is not None:
        patch["lignes"] = [ligne.en_ligne() for ligne in donnees.lignes]
    formule = _depot().modifier(formule_id, company_id, patch) if patch else _formule(formule_id, company_id)
    return {"formule": formule, "fiches_a_mettre_a_jour": len(_fiches_a_mettre_a_jour(formule, company_id))}


def retirer_formule(formule_id: str, company_id: str) -> dict[str, Any]:
    """Désactive la formule ; les fiches gardent leurs lignes."""
    _formule(formule_id, company_id)
    return _depot().modifier(formule_id, company_id, {"is_active": False})


def appliquer_formule_aux_fiches(formule_id: str, company_id: str) -> int:
    """Recopie les lignes de la formule sur les fiches qui la portent et divergent."""
    formule = _formule(formule_id, company_id)
    fiches = _fiches_a_mettre_a_jour(formule, company_id)
    for fiche in fiches:
        prevoyance = (fiche.get("specificites_paie") or {}).get("prevoyance") or {}
        _ecrire_prevoyance(str(fiche["id"]), appliquer_formule(prevoyance, formule))
    return len(fiches)
