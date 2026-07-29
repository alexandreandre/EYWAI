"""Plan de reprise des adresses fabriquées — la partie qui décide quoi toucher.

Le script est en lecture seule par défaut ; ce qui doit être verrouillé par des tests,
c'est le tri : quelle fiche est vidée, quel compte est réaligné, et surtout ce qui doit
rester intact.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "cleanup_placeholder_emails.py"
_spec = importlib.util.spec_from_file_location("cleanup_placeholder_emails", _SCRIPT)
cleanup = importlib.util.module_from_spec(_spec)
sys.modules["cleanup_placeholder_emails"] = cleanup
_spec.loader.exec_module(cleanup)


def _client(employees: list[dict], auth_emails: dict[str, str]) -> MagicMock:
    client = MagicMock()

    def table(name: str):
        chain = MagicMock()
        data = [{"id": "c-1", "company_name": "MAJI"}] if name == "companies" else employees
        chain.select.return_value.execute.return_value = MagicMock(data=data)
        return chain

    client.table.side_effect = table
    users = [MagicMock(id=uid, email=mail) for uid, mail in auth_emails.items()]
    client.auth.admin.list_users.return_value = users
    return client


PLACEHOLDER = "import.jean.martin.123456@534386495.dsn-import.local"


def test_fiche_fabriquee_est_videe() -> None:
    plan = cleanup.build_plan(
        _client(
            [{"id": "e1", "company_id": "c-1", "first_name": "Jean", "last_name": "MARTIN",
              "email": PLACEHOLDER, "user_id": "u1", "employment_status": "actif"}],
            {"u1": PLACEHOLDER},
        )
    )

    assert plan["resume"] == {"fiches_a_vider": 1, "logins_a_realigner": 0}
    assert plan["clear_fiches"][0]["adresse_retiree"] == PLACEHOLDER


def test_login_fabrique_avec_fiche_reelle_est_realigne() -> None:
    plan = cleanup.build_plan(
        _client(
            [{"id": "e1", "company_id": "c-1", "first_name": "Jean", "last_name": "MARTIN",
              "email": "Jean.Martin@exemple.fr", "user_id": "u1", "employment_status": "actif"}],
            {"u1": PLACEHOLDER},
        )
    )

    assert plan["resume"] == {"fiches_a_vider": 0, "logins_a_realigner": 1}
    assert plan["realign_logins"][0]["login_cible"] == "jean.martin@exemple.fr"


def test_fiche_et_login_reels_ne_bougent_pas() -> None:
    plan = cleanup.build_plan(
        _client(
            [{"id": "e1", "company_id": "c-1", "first_name": "Jean", "last_name": "MARTIN",
              "email": "jean.martin@exemple.fr", "user_id": "u1", "employment_status": "actif"}],
            {"u1": "jean.martin@exemple.fr"},
        )
    )

    assert plan["resume"] == {"fiches_a_vider": 0, "logins_a_realigner": 0}


def test_salarie_sans_compte_n_est_jamais_realigne() -> None:
    plan = cleanup.build_plan(
        _client(
            [{"id": "e1", "company_id": "c-1", "first_name": "Jean", "last_name": "MARTIN",
              "email": "jean.martin@exemple.fr", "user_id": None, "employment_status": "actif"}],
            {},
        )
    )

    assert plan["realign_logins"] == []


def test_fiche_vide_ne_produit_aucune_action() -> None:
    """Une fiche déjà nettoyée ne doit pas revenir dans le plan : idempotence."""
    plan = cleanup.build_plan(
        _client(
            [{"id": "e1", "company_id": "c-1", "first_name": "Jean", "last_name": "MARTIN",
              "email": None, "user_id": "u1", "employment_status": "actif"}],
            {"u1": PLACEHOLDER},
        )
    )

    assert plan["resume"] == {"fiches_a_vider": 0, "logins_a_realigner": 0}


def test_apply_refuse_sans_operation_demandee() -> None:
    client = _client([], {})
    plan = cleanup.build_plan(client)

    done = cleanup.apply_plan(client, plan, clear_fiches=False, realign_logins=False)

    assert done == {"fiches_videes": 0, "logins_realignes": 0, "echecs": 0}


def test_un_echec_n_interrompt_pas_les_autres() -> None:
    client = _client(
        [
            {"id": "e1", "company_id": "c-1", "first_name": "A", "last_name": "A",
             "email": "a@exemple.fr", "user_id": "u1", "employment_status": "actif"},
            {"id": "e2", "company_id": "c-1", "first_name": "B", "last_name": "B",
             "email": "b@exemple.fr", "user_id": "u2", "employment_status": "actif"},
        ],
        {"u1": PLACEHOLDER, "u2": PLACEHOLDER},
    )
    plan = cleanup.build_plan(client)
    client.auth.admin.update_user_by_id.side_effect = [
        RuntimeError("email already registered"),
        None,
    ]

    done = cleanup.apply_plan(client, plan, clear_fiches=False, realign_logins=True)

    assert done["logins_realignes"] == 1
    assert done["echecs"] == 1
