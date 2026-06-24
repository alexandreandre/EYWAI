"""Tests allocation identifiant collaborateur (unicité en base)."""

from unittest.mock import patch

import pytest

from app.modules.employees.infrastructure.queries import allocate_collaborator_username


pytestmark = pytest.mark.unit


@patch("app.modules.employees.infrastructure.queries.fetch_taken_usernames")
def test_allocate_uses_prenom_nom(mock_fetch):
    mock_fetch.return_value = {"marie.martin"}
    username = allocate_collaborator_username("Jean", "Dupont")
    assert username == "jean.dupont"


@patch("app.modules.employees.infrastructure.queries.fetch_taken_usernames")
def test_allocate_suffix_on_collision(mock_fetch):
    mock_fetch.return_value = {"jean.dupont"}
    username = allocate_collaborator_username("Jean", "Dupont")
    assert username == "jean.dupont2"


@patch("app.modules.employees.infrastructure.queries.fetch_taken_usernames")
def test_allocate_replaces_import_style_existing(mock_fetch):
    mock_fetch.return_value = set()
    username = allocate_collaborator_username(
        "Samir",
        "Boufrida",
        exclude_employee_id="emp-1",
        existing="import.samir.boufrida.353238",
    )
    assert username == "samir.boufrida"


@patch("app.modules.employees.infrastructure.queries.fetch_taken_usernames")
def test_allocate_keeps_valid_existing(mock_fetch):
    mock_fetch.return_value = {"marie.martin"}
    username = allocate_collaborator_username(
        "Jean",
        "Dupont",
        exclude_employee_id="emp-1",
        existing="jean.dupont",
    )
    assert username == "jean.dupont"
