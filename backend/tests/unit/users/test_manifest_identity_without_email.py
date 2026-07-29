"""Le manifeste ne doit plus dépendre d'une adresse fabriquée pour identifier quelqu'un.

`identity.email` sert de clé de recherche du compte Auth. Pour Vanessa, cette clé était
son adresse `…@…dsn-import.local`. Dès qu'on réaligne son compte sur son adresse réelle,
la clé ne correspond plus. Un compte marqué `canonical_employee_account` doit donc être
retrouvable par sa fiche salarié, qui est le lien stable.
"""

from __future__ import annotations

import pytest

from app.modules.users.application.access_provisioning import (
    AccessProvisioner,
    InMemoryProvisioningGateway,
)

pytestmark = pytest.mark.unit

MANIFEST = {
    "version": 1,
    "companies": {"maji": ["MAJI"]},
    "permission_sets": {"bank_only": ["bank_dispatch.send"]},
    "people": [
        {
            "key": "vanessa",
            "identity": {"name": "Vanessa Amate"},
            "account": "existing_only",
            "canonical_employee_account": True,
            "accesses": [
                {
                    "company": "maji",
                    "role": "admin",
                    "scope_mode": "company",
                    "permission_set": "bank_only",
                }
            ],
        }
    ],
}

PROFILS_HOMONYMES = [
    {
        "id": "u-fiche",
        "first_name": "Vanessa",
        "last_name": "Amate",
        "role": "admin",
        "email": "amatevanessa@yahoo.fr",
    },
    {
        "id": "u-doublon",
        "first_name": "Vanessa",
        "last_name": "Amate",
        "role": "admin",
        "email": "vamate@maji-invest.fr",
    },
]


def _gateway(**kwargs) -> InMemoryProvisioningGateway:
    return InMemoryProvisioningGateway(
        companies=[{"id": "c-maji", "company_name": "MAJI"}],
        permissions={"bank_dispatch.send": "p-bank"},
        **kwargs,
    )


def test_la_fiche_salarie_departage_deux_homonymes() -> None:
    """Sans adresse au manifeste, deux profils homonymes seraient ambigus."""
    gw = _gateway(
        profiles=PROFILS_HOMONYMES,
        employees=[
            {
                "id": "emp-van",
                "user_id": "u-fiche",
                "first_name": "Vanessa",
                "last_name": "AMATE",
                "company_id": "c-maji",
                "email": "amatevanessa@yahoo.fr",
            }
        ],
    )

    plan = AccessProvisioner(MANIFEST, gw).plan()

    assert not plan.has_conflicts, [i.details for i in plan.items if i.action == "resolve_identity"]
    cibles = {i.details.get("user_id") for i in plan.items if i.details}
    assert "u-doublon" not in cibles


def test_sans_fiche_l_ambiguite_reste_signalee() -> None:
    """Le repli ne doit pas inventer une résolution : fail-closed conservé."""
    gw = _gateway(profiles=PROFILS_HOMONYMES, employees=[])

    plan = AccessProvisioner(MANIFEST, gw).plan()

    assert plan.has_conflicts


def test_le_manifeste_ne_contient_plus_aucune_adresse_fabriquee() -> None:
    from pathlib import Path

    from app.modules.employees.domain.rules import is_dsn_import_placeholder_email
    from app.modules.users.application.access_provisioning import load_manifest

    manifest = load_manifest(Path("app/modules/users/data/access_manifest.json"))
    for person in manifest.get("people") or []:
        email = (person.get("identity") or {}).get("email")
        assert not is_dsn_import_placeholder_email(email), (
            f"{person['key']} identifié par une adresse fabriquée : {email}"
        )
