"""Commandes CRUD types de poste planning.

Un type de poste appartient soit à une société (`company_id`), soit à une
convention planning (partagé par toutes les sociétés qui l'ont choisie). Toute
écriture depuis une société porte sur un type de la société : modifier ou
désactiver un type de convention crée une copie propre à la société
(`replaces_shift_type_id`), jamais une écriture sur le type partagé.
"""

from __future__ import annotations

from typing import Any

from app.modules.planning.infrastructure.repository import planning_repository

_COULEUR_PAR_DEFAUT = "#6366f1"

# Colonnes d'un type partagé qui ne passent pas dans sa copie.
_NON_COPIEES = {"id", "created_at", "collective_agreement_id", "company_id"}

_HORS_DE_LA_SOCIETE = (
    "Ce type de poste n'est ni à la société ni à sa convention du planning : "
    "il ne se modifie pas d'ici."
)


def list_shift_types_for_company(company_id: str) -> list[dict[str, Any]]:
    from app.modules.planning.application import queries as app_queries

    return app_queries.get_shift_types_for_company(company_id)


def _cc_planning(company_id: str) -> str | None:
    settings = planning_repository.get_company_planning_settings(company_id)
    cc_id = (settings or {}).get("collective_agreement_id")
    return str(cc_id) if cc_id else None


def _verifier_code_libre(
    company_id: str, code: str, sauf_id: str | None = None
) -> None:
    code_norm = (code or "").strip().upper()
    for t in planning_repository.get_shift_types_by_company(company_id):
        if str(t.get("id")) == str(sauf_id or ""):
            continue
        if str(t.get("code") or "").strip().upper() == code_norm:
            raise ValueError(
                f"Le code « {code_norm} » est déjà pris par un type de poste de la "
                "société : choisissez un autre code."
            )


def create_shift_type(
    company_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    _verifier_code_libre(company_id, str(data.get("code") or ""))
    payload = {
        **data,
        "company_id": company_id,
        "collective_agreement_id": None,
        "is_custom": True,
        "is_active": data.get("is_active", True),
        # `color` est NOT NULL en base ; l'API l'accepte absente.
        "color": data.get("color") or _COULEUR_PAR_DEFAUT,
    }
    return planning_repository.create_shift_type(payload)


def _copie_de_la_societe(
    company_id: str, partage: dict[str, Any], data: dict[str, Any]
) -> dict[str, Any]:
    """Écrit `data` sur la copie de la société du type partagé (créée au besoin)."""
    for t in planning_repository.get_shift_types_by_company(company_id):
        if str(t.get("replaces_shift_type_id") or "") == str(partage.get("id")):
            if "code" in data:
                _verifier_code_libre(company_id, str(data["code"]), sauf_id=t.get("id"))
            return planning_repository.update_shift_type(str(t["id"]), data)
    copie = {k: v for k, v in partage.items() if k not in _NON_COPIEES}
    copie.update(data)
    _verifier_code_libre(company_id, str(copie.get("code") or ""))
    copie.update(
        {
            "company_id": company_id,
            "collective_agreement_id": None,
            "is_custom": True,
            "replaces_shift_type_id": str(partage["id"]),
        }
    )
    return planning_repository.create_shift_type(copie)


def _type_ecrivable(company_id: str, shift_type_id: str) -> tuple[dict[str, Any], bool]:
    """(type, est_a_la_societe). PermissionError si la société ne le voit pas."""
    existing = planning_repository.get_shift_type_by_id(shift_type_id)
    if not existing:
        raise LookupError("Type de poste introuvable.")
    proprietaire = existing.get("company_id")
    if proprietaire:
        if str(proprietaire) != str(company_id):
            raise PermissionError(_HORS_DE_LA_SOCIETE)
        return existing, True
    cc_id = _cc_planning(company_id)
    # Sans convention planning, aucun type partagé n'est visible de la société.
    if not cc_id or str(existing.get("collective_agreement_id")) != cc_id:
        raise PermissionError(_HORS_DE_LA_SOCIETE)
    return existing, False


def update_shift_type(
    company_id: str,
    shift_type_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    existing, a_la_societe = _type_ecrivable(company_id, shift_type_id)
    if not a_la_societe:
        return _copie_de_la_societe(company_id, existing, data)
    if "code" in data:
        _verifier_code_libre(company_id, str(data["code"]), sauf_id=shift_type_id)
    return planning_repository.update_shift_type(shift_type_id, data)


def delete_shift_type(company_id: str, shift_type_id: str) -> None:
    existing, a_la_societe = _type_ecrivable(company_id, shift_type_id)
    if not a_la_societe:
        # Le type partagé reste actif pour les autres sociétés : la société en
        # garde une copie désactivée, qui le masque pour elle seule.
        _copie_de_la_societe(company_id, existing, {"is_active": False})
        return
    planning_repository.deactivate_shift_type(shift_type_id)
