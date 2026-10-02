"""
Jamais d'écriture de taux dans l'ancienne base de production.

Le lot de taux n'écrit que la base de test, tant que le moteur recetté de la
démo n'est pas devenu celui de la production. Si ce code arrivait sur un
serveur branché sur l'ancienne production, le lot doit refuser de partir
avant tout scraping.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.rates.application.sync import (
    reset_sync_registry_for_tests,
    start_rates_sync,
)
from app.modules.rates.domain.rules import base_interdite_pour_les_taux

_PROD = "https://slleauhyjnmiawosvlcg.supabase.co"
_TEST = "https://tlvkjwleahkmuzcegrde.supabase.co"


def test_l_ancienne_production_est_interdite():
    assert base_interdite_pour_les_taux(_PROD) is True
    assert base_interdite_pour_les_taux(_PROD + "/") is True


def test_la_base_de_test_est_autorisee():
    assert base_interdite_pour_les_taux(_TEST) is False
    assert base_interdite_pour_les_taux("") is False


@patch("app.modules.rates.application.sync.execute_scraper")
@patch("app.modules.rates.application.sync.ScrapingRepository")
def test_le_lot_refuse_de_partir_sur_l_ancienne_production(mock_repo_cls, mock_execute):
    reset_sync_registry_for_tests()
    with patch("app.modules.rates.application.sync.supabase_url", _PROD):
        with pytest.raises(ValueError, match="production"):
            start_rates_sync(triggered_by="u", background_task_fn=MagicMock())
    mock_repo_cls.assert_not_called()
    mock_execute.assert_not_called()
    reset_sync_registry_for_tests()
