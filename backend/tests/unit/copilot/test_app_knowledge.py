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


def test_guide_covers_employee_loans():
    """Le guide documente le module Prêts employeur (workflow paie et espace collaborateur)."""
    assert "Prêts employeur" in APP_FEATURE_GUIDE
    assert "⑩ Prêts employeur" in APP_FEATURE_GUIDE


def test_guide_covers_salary_advances_and_acomptes():
    """Le guide utilise le libellé sidebar « Avances & acomptes » et distingue les types."""
    assert "Avances & acomptes" in APP_FEATURE_GUIDE
    assert "acompte_salaire" not in APP_FEATURE_GUIDE  # pas de détail technique BDD
    assert "acompte sur prime" in APP_FEATURE_GUIDE.lower()


def test_guide_workflow_paie_ten_steps():
    """Le parcours paie couvre les 10 étapes numérotées avant Lancer la paie."""
    for step in ("①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"):
        assert step in APP_FEATURE_GUIDE
    assert "⑪" not in APP_FEATURE_GUIDE
    assert "Lancer la paie" in APP_FEATURE_GUIDE


def test_guide_covers_suivi_cet():
    """Le guide documente Suivi CET dans le workflow paie (étape ⑤)."""
    assert "Suivi CET" in APP_FEATURE_GUIDE
    assert "⑤ Suivi CET" in APP_FEATURE_GUIDE


def test_guide_covers_badgeuse_accounting():
    """Le guide mentionne la comptabilisation paramétrable de la badgeuse."""
    assert "Comptabilisation paramétrable" in APP_FEATURE_GUIDE or "comptabilisation paramétrable" in APP_FEATURE_GUIDE.lower()


def test_guide_covers_ijss_contingent_hs_and_cet():
    """Le guide documente Suivi IJSS, Temps de travail & HS et Suivi CET."""
    assert "Suivi IJSS / CPAM" in APP_FEATURE_GUIDE
    assert "Temps de travail & HS" in APP_FEATURE_GUIDE
    assert "plafond annuel" in APP_FEATURE_GUIDE
    assert "compte d'heures" in APP_FEATURE_GUIDE
    assert "Suivi CET" in APP_FEATURE_GUIDE


def test_guide_covers_participation():
    """Le guide documente participation côté RH et collaborateur."""
    assert "Participation & Intéressement" in APP_FEATURE_GUIDE
    assert "Participation" in APP_FEATURE_GUIDE


def test_guide_covers_work_medals():
    """Le guide mentionne les médailles du travail (Mon Entreprise et fiche salarié)."""
    assert "médailles du travail" in APP_FEATURE_GUIDE.lower()


def test_guide_covers_manager_validation_menus():
    """Le guide documente les menus manager (congés et CET à valider)."""
    assert "Congés à valider" in APP_FEATURE_GUIDE
    assert "CET à valider" in APP_FEATURE_GUIDE
    assert "Validations" in APP_FEATURE_GUIDE


def test_guide_covers_salary_advance_net_cap_override():
    """Le guide documente la dérogation RH au plafond 50 % du net."""
    assert "50 %" in APP_FEATURE_GUIDE
    assert "Hors plafond" in APP_FEATURE_GUIDE or "dérogation" in APP_FEATURE_GUIDE.lower()


def test_guide_covers_salary_payment_method():
    """Le guide mentionne le mode de paiement du salaire (virement/chèque/espèces)."""
    assert "Mode de paiement du salaire" in APP_FEATURE_GUIDE or "virement" in APP_FEATURE_GUIDE
    assert "chèque" in APP_FEATURE_GUIDE.lower() or "cheque" in APP_FEATURE_GUIDE.lower()


def test_guide_covers_cse_status_in_mon_entreprise():
    """Le guide documente le statut CSE dans Mon Entreprise."""
    assert "Statut CSE" in APP_FEATURE_GUIDE
    assert "carence" in APP_FEATURE_GUIDE.lower()
