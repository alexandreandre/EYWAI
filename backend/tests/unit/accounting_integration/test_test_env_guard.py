"""Garde-fou : aucune écriture n'est transmise depuis l'environnement de test.

L'environnement de test tourne sur une copie des données réelles. Une
transmission partirait vers la comptabilité réelle du client, au même titre
qu'un dépôt de DSN ou une signature électronique — déjà verrouillés.
"""

from unittest.mock import patch

import pytest

from app.modules.accounting_integration.application import service

pytestmark = pytest.mark.unit


class TestTransmissionBloqueeEnTest:
    def _config_automatique(self):
        return {
            "provider": "cegid_quadra",
            "mode": "api_quadra",
            "enabled": True,
            "force_manual": False,
        }

    def test_environnement_de_test_retombe_en_manuel(self):
        with patch.object(
            service.repository, "get_config", return_value=self._config_automatique()
        ), patch.object(
            service.repository, "get_platform_provider", return_value=None
        ), patch.object(
            service.repository, "insert_transmission", return_value="tr-1"
        ), patch.object(
            service.settings, "is_test_environment", return_value=True
        ):
            result = service.transmit_compta_files(
                "co-1",
                [("od_globale_2026_06.csv", b"x")],
                {"period": "2026-06", "channel": "compta"},
            )

        assert result.manual_fallback is True
        assert result.status == "manual"
        assert "test" in result.message.lower()

    def test_production_tente_bien_la_transmission(self):
        """Le garde-fou ne doit pas bloquer la production."""
        with patch.object(
            service.repository, "get_config", return_value=self._config_automatique()
        ), patch.object(
            service.repository, "find_existing_transmission", return_value=None
        ), patch.object(
            service.repository, "get_platform_provider", return_value=None
        ), patch.object(
            service.repository, "insert_transmission", return_value="tr-2"
        ), patch.object(
            service.repository, "update_transmission", return_value=None
        ), patch.object(
            service.settings, "is_test_environment", return_value=False
        ), patch.object(
            service, "resolve_connector"
        ) as connector_mock:
            connector_mock.return_value.submit_files.side_effect = RuntimeError("api muette")
            result = service.transmit_compta_files(
                "co-1",
                [("od_globale_2026_06.csv", b"x")],
                {"period": "2026-06", "channel": "compta"},
            )

        # La transmission a été tentée : le connecteur a bien été sollicité.
        assert connector_mock.called
        assert result.status != "manual" or result.manual_fallback is True
