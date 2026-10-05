"""Tests de la base de connaissances produit du copilot."""

import json
from pathlib import Path

import pytest

from app.modules.copilot.infrastructure.app_knowledge import APP_FEATURE_GUIDE

pytestmark = pytest.mark.unit

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MANUEL_ECRAN = (
    REPOSITORY_ROOT / "frontend" / "src" / "features" / "payroll" / "utils"
    / "manuelOperateur.json"
)
MANUEL_ASSISTANT = (
    REPOSITORY_ROOT / "backend" / "app" / "modules" / "copilot" / "infrastructure"
    / "manuel_paie.json"
)


def test_l_assistant_lit_le_manuel_de_l_ecran():
    """Une seule source : la copie du backend est celle du frontend, octet pour octet."""
    assert MANUEL_ASSISTANT.read_bytes() == MANUEL_ECRAN.read_bytes(), (
        "Le manuel de la paie a changé côté écran : recopier "
        "frontend/src/features/payroll/utils/manuelOperateur.json vers "
        "backend/app/modules/copilot/infrastructure/manuel_paie.json."
    )


def test_guide_contient_le_manuel_de_la_paie_mot_pour_mot():
    manuel = json.loads(MANUEL_ECRAN.read_text(encoding="utf-8"))
    textes = [s["titre"] for s in manuel["sections"]]
    for etape in manuel["etapes"]:
        textes += [etape["titre"], *etape["paragraphes"]]
    for piege in manuel["pieges"]:
        textes += [piege["titre"], piege["quoiFaire"]]
    absents = [t for t in textes if t not in APP_FEATURE_GUIDE]
    assert absents == []


def test_guide_renvoie_au_manuel_pour_la_paie_du_mois():
    """Le guide du 01/08 faisait de « Lancer la paie » la fin du parcours."""
    assert "le bouton « Lancer la paie » génère les bulletins" not in APP_FEATURE_GUIDE
    assert "Manuel de la paie" in APP_FEATURE_GUIDE
    assert "« Bulletins de paie »" in APP_FEATURE_GUIDE
    assert "« Envois »" in APP_FEATURE_GUIDE
    assert "pas encore déposable" in APP_FEATURE_GUIDE


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


def test_guide_covers_mutuelle_self_service():
    """Le guide documente le paramétrage mutuelle et le choix salarié optionnel."""
    assert "Mon Entreprise" in APP_FEATURE_GUIDE
    assert "Mutuelle" in APP_FEATURE_GUIDE
    assert "choix salarié" in APP_FEATURE_GUIDE.lower()


def test_guide_covers_dsn_import_payroll_context():
    """Le guide mentionne l'import DSN comme source de reprise paie/RH."""
    assert "Import DSN" in APP_FEATURE_GUIDE or "imports DSN" in APP_FEATURE_GUIDE
    assert "agrégats de paie" in APP_FEATURE_GUIDE


def test_guide_covers_leave_notification_settings():
    """Le guide documente les rappels/notifications congés côté entreprise."""
    assert "rappels de congés" in APP_FEATURE_GUIDE.lower() or "rappels congés" in APP_FEATURE_GUIDE.lower()


def test_guide_covers_permission_scopes():
    """Le guide documente les périmètres de permission (équipes / exceptions)."""
    assert "Périmètre par permission" in APP_FEATURE_GUIDE
    assert "Toute l'entreprise" in APP_FEATURE_GUIDE
    assert "Équipes" in APP_FEATURE_GUIDE
    assert "Exceptions uniquement" in APP_FEATURE_GUIDE


def test_guide_covers_forfait_jours_field():
    """Le guide distingue la case Forfait jours du statut Cadre/Non-Cadre."""
    assert "Forfait jours" in APP_FEATURE_GUIDE
    assert "indépendante" in APP_FEATURE_GUIDE.lower() or "indépendant" in APP_FEATURE_GUIDE.lower()


def test_guide_covers_calendar_plans_and_pauses():
    """Le guide documente les plans de calendriers et les pauses planning."""
    assert "Calendriers horaires 2026" in APP_FEATURE_GUIDE
    assert "Planning & primes équipe" in APP_FEATURE_GUIDE
    assert "Pauses payées" in APP_FEATURE_GUIDE


def test_guide_covers_accounting_integration():
    """Le guide documente l'intégration comptable Cegid Loop dans Exports."""
    assert "Paie & Comptabilité" in APP_FEATURE_GUIDE
    assert "Intégration comptable" in APP_FEATURE_GUIDE
    assert "Cegid Loop" in APP_FEATURE_GUIDE


def test_guide_covers_word_contract_export():
    """Le guide documente le téléchargement Word des contrats/avenants."""
    assert "Word (.docx) — à retravailler" in APP_FEATURE_GUIDE


def test_guide_covers_rh_collaborator_view_switch():
    """Le guide documente la bascule Vue RH / Vue Collaborateur."""
    assert "Vue RH" in APP_FEATURE_GUIDE
    assert "Vue Collaborateur" in APP_FEATURE_GUIDE


def test_guide_covers_forced_password_change():
    """Le guide documente le changement de MDP obligatoire au premier login."""
    assert "premier login" in APP_FEATURE_GUIDE.lower() or "première connexion" in APP_FEATURE_GUIDE.lower()
    assert "mot de passe" in APP_FEATURE_GUIDE.lower()
