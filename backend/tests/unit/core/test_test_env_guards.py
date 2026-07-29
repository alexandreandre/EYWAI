"""Blocage des sorties vers le monde réel en environnement de test."""

import pytest

from app.core import settings


def test_yousign_refuse_en_environnement_de_test(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    from app.services.yousign_service import YousignService

    with pytest.raises(RuntimeError, match="environnement de test"):
        YousignService().create_signature_request(
            document_content=b"%PDF",
            document_name="doc.pdf",
            signer_email="salarie@exemple.fr",
            signer_first_name="Jean",
            signer_last_name="Dupont",
        )


def test_yousign_ne_bloque_pas_en_production(monkeypatch):
    """En prod, l'absence de clé API reste la seule cause de refus."""
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.delenv("YOUSIGN_API_KEY", raising=False)
    from app.services.yousign_service import YousignService

    with pytest.raises(Exception) as exc:
        YousignService().create_signature_request(
            document_content=b"%PDF",
            document_name="doc.pdf",
            signer_email="salarie@exemple.fr",
            signer_first_name="Jean",
            signer_last_name="Dupont",
        )
    assert "environnement de test" not in str(exc.value)


def test_depot_dsn_refuse_en_environnement_de_test(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    from app.modules.net_entreprises.infrastructure.api_connector import (
        NetEntreprisesApiConnector,
    )

    with pytest.raises(Exception, match="environnement de test"):
        NetEntreprisesApiConnector().submit_dsn({}, b"<xml/>", {})
