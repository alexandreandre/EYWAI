"""R-654 : une sonde qui lit la base, et l'exploitation prévenue d'une génération en échec."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core import settings
from app.main import app
from app.modules.payslips.api import router as route_bulletins
from app.shared.infrastructure.email import alerte_exploitation as alerte


@pytest.fixture(autouse=True)
def _memoire_vide():
    alerte._derniers_envois.clear()
    yield
    alerte._derniers_envois.clear()


def test_la_sonde_repond_prete_quand_la_base_repond():
    with patch("app.main.supabase") as sb:
        rep = TestClient(app).get("/health/ready")
    assert rep.status_code == 200
    assert rep.json()["base"] == "ok"
    sb.table.return_value.select.return_value.limit.return_value.execute.assert_called_once()


def test_la_sonde_repond_503_quand_la_base_ne_repond_pas():
    with patch("app.main.supabase") as sb:
        sb.table.side_effect = RuntimeError("base injoignable")
        rep = TestClient(app, raise_server_exceptions=False).get("/health/ready")
    assert rep.status_code == 503
    assert rep.json()["base"] == "injoignable"


def test_health_reste_sans_base():
    with patch("app.main.supabase") as sb:
        assert TestClient(app).get("/health").status_code == 200
    sb.table.assert_not_called()


def test_rien_ne_part_sans_adresse(monkeypatch):
    monkeypatch.setattr(settings, "ALERTE_EXPLOITATION_EMAIL", None)
    with patch.object(alerte, "get_smtp_mail_sender") as fabrique:
        alerte.prevenir_exploitation("cle", "sujet", "détail")
    fabrique.assert_not_called()


def test_l_adresse_posee_recoit_l_alerte_sans_nom_de_salarie(monkeypatch):
    monkeypatch.setattr(settings, "ALERTE_EXPLOITATION_EMAIL", "exploit@example.com")
    with patch.object(alerte, "get_smtp_mail_sender") as fabrique:
        fabrique.return_value.send_multipart_email.return_value = (True, None)
        alerte.prevenir_exploitation("cle", "Génération en échec", "société co-1, 10/2026")
    envoi = fabrique.return_value.send_multipart_email.call_args.kwargs
    assert envoi["to_email"] == "exploit@example.com"
    assert "Génération en échec" in envoi["subject"]
    assert "société co-1" in envoi["text_content"]


def test_une_rafale_ne_part_qu_une_fois(monkeypatch):
    monkeypatch.setattr(settings, "ALERTE_EXPLOITATION_EMAIL", "exploit@example.com")
    with patch.object(alerte, "get_smtp_mail_sender") as fabrique:
        fabrique.return_value.send_multipart_email.return_value = (True, None)
        for _ in range(5):
            alerte.prevenir_exploitation("meme-cle", "s", "d")
        alerte.prevenir_exploitation("autre-cle", "s", "d")
    assert fabrique.return_value.send_multipart_email.call_count == 2


def test_une_panne_d_envoi_ne_casse_pas_la_reponse(monkeypatch):
    monkeypatch.setattr(settings, "ALERTE_EXPLOITATION_EMAIL", "exploit@example.com")
    with patch.object(alerte, "get_smtp_mail_sender", side_effect=RuntimeError("smtp")):
        alerte.prevenir_exploitation("cle", "s", "d")


def test_la_generation_en_echec_previent_sans_message_d_exception():
    requete = MagicMock(
        employee_id="emp-1", year=2026, month=10, force_calendrier_incomplet=False,
        regenerer_bulletin_valide=False, partir_de_cumuls_a_zero=False, contract_period_id=None,
    )
    utilisateur = MagicMock(id="u-1", first_name="A", last_name="B", is_platform_admin=False)
    with (
        patch.object(route_bulletins, "_require_rh_company_context", return_value="co-1"),
        patch.object(route_bulletins, "access_control_service"),
        patch.object(route_bulletins, "generate_payslip", side_effect=ValueError("Fiche illisible du salarié Fictif")),
        patch.object(route_bulletins, "prevenir_exploitation") as prevenir,
        pytest.raises(route_bulletins.HTTPException) as refus,
    ):
        route_bulletins.generate_payslip_route(requete, utilisateur)
    assert refus.value.status_code == 500
    detail = prevenir.call_args.args[2]
    assert "co-1" in detail and "10/2026" in detail and "ValueError" in detail
    assert "Fictif" not in detail
