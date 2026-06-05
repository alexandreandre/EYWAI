"""Tests de la base de connaissances produit du copilot."""

import pytest

from app.modules.copilot.infrastructure.app_knowledge import APP_FEATURE_GUIDE

pytestmark = pytest.mark.unit


def test_guide_covers_employee_credentials():
    """Le guide doit documenter où trouver les identifiants de connexion."""
    assert "Identifiants de connexion" in APP_FEATURE_GUIDE
    assert "Collaborateurs" in APP_FEATURE_GUIDE
    assert "Documents" in APP_FEATURE_GUIDE
    assert "mot de passe temporaire" in APP_FEATURE_GUIDE.lower()


def test_guide_distinguishes_rh_users_from_collaborators():
    """Le guide distingue les comptes RH (Gestion des Utilisateurs) des salariés."""
    assert "Gestion des Utilisateurs" in APP_FEATURE_GUIDE
    assert "pas les comptes collaborateurs" in APP_FEATURE_GUIDE
