"""Robin Baran — collaborateur RH sur Zone 404 avec les droits d'un directeur de site.

« Directeur » n'est pas un rôle dans cette plateforme : c'est un jeu de permissions posé
sur un rôle. Robin garde donc son espace salarié (vue collaborateur), gagne la vue RH via
`collaborateur_rh`, et les validations via `director_mod_validations` — qui ne sont jamais
implicites, même pour un rôle de niveau RH.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.users.application.access_provisioning import (
    AccessProvisioner,
    InMemoryProvisioningGateway,
    build_access_summaries,
    load_manifest,
)

pytestmark = pytest.mark.unit

MANIFEST_PATH = Path("app/modules/users/data/access_manifest.json")
ROBIN_USER = "u-robin"
ZONE = "c-z404"


def _manifest() -> dict:
    return load_manifest(MANIFEST_PATH)


def _manifest_robin_seul() -> dict:
    """Le manifeste réel, réduit à Robin : les autres personnes n'existent pas dans le
    gateway de test et produiraient des conflits sans rapport."""
    manifest = _manifest()
    manifest["people"] = [_robin(manifest)]
    return manifest


def _robin(manifest: dict) -> dict:
    return next(p for p in manifest["people"] if p["key"] == "robin")


def _gateway(role_actuel: str) -> InMemoryProvisioningGateway:
    return InMemoryProvisioningGateway(
        companies=[{"id": ZONE, "company_name": "Zone 404 Mars"}],
        profiles=[
            {
                "id": ROBIN_USER,
                "first_name": "Robin",
                "last_name": "Baran",
                "role": role_actuel,
                "username": "robin.baran",
                "email": "robin.baran@zone404.fr",
            }
        ],
        accesses=[
            {
                "id": "a-robin",
                "user_id": ROBIN_USER,
                "company_id": ZONE,
                "role": role_actuel,
                "is_active": True,
            }
        ],
        employees=[
            {
                "id": "e-robin",
                "user_id": ROBIN_USER,
                "first_name": "Robin",
                "last_name": "BARAN",
                "company_id": ZONE,
                "email": "robin.baran@zone404.fr",
            }
        ],
        permissions={
            code: f"p-{i}"
            for i, code in enumerate(
                load_manifest(MANIFEST_PATH)["permission_sets"]["director_mod_validations"]
            )
        },
    )


def test_le_manifeste_declare_robin_collaborateur_rh_directeur() -> None:
    acces = _robin(_manifest())["accesses"]

    assert len(acces) == 1
    assert acces[0]["company"] == "zone_404"
    assert acces[0]["role"] == "collaborateur_rh"
    assert acces[0]["permission_set"] == "director_mod_validations"
    assert acces[0]["scope_mode"] == "company"


def test_le_plan_fait_monter_le_role_et_pose_les_permissions() -> None:
    plan = AccessProvisioner(_manifest_robin_seul(), _gateway("collaborateur")).plan()

    assert not plan.has_conflicts, [
        i.details for i in plan.items if i.action == "resolve_identity"
    ]
    robin = [i for i in plan.items if "robin" in i.subject]
    actions = {i.action for i in robin}
    assert "update_access_role" in actions, actions
    montee = next(i for i in robin if i.action == "update_access_role")
    assert montee.details["previous_role"] == "collaborateur"
    assert montee.details["role"] == "collaborateur_rh"


def test_les_validations_directeur_sont_bien_accordees() -> None:
    plan = AccessProvisioner(_manifest_robin_seul(), _gateway("collaborateur")).plan()

    grants = [
        i for i in plan.items if "robin" in i.subject and i.action == "replace_grants"
    ]
    assert grants, "le jeu de permissions directeur doit produire des grants"
    lignes = grants[0].details["grants"]
    codes = {g["permission_code"] for g in lignes}
    assert "payslips.validate" in codes
    assert "expenses.approve" in codes
    assert "analytics.view_all" in codes
    assert all(g["scope_mode"] == "company" for g in lignes), "périmètre = toute l'entreprise"


def test_second_passage_sans_effet() -> None:
    """Idempotence : une fois provisionné, plus rien à faire."""
    plan = AccessProvisioner(_manifest_robin_seul(), _gateway("collaborateur_rh")).plan()

    robin = [i for i in plan.items if "robin" in i.subject]
    assert "update_access_role" not in {i.action for i in robin}


def test_le_classeur_decrit_ses_droits_en_clair() -> None:
    """Le résumé Excel ne détaillait les permissions que pour le rôle `custom`."""
    resume = build_access_summaries(_manifest())["robin"]

    assert "Zone 404 Mars" in resume
    assert "Collaborateur RH" in resume, resume
    assert "Valider bulletins" in resume, resume
    assert "Périmètre toute l’entreprise" in resume, resume
