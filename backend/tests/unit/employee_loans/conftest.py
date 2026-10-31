"""Le barème de la quotité saisissable, lu en base par l'enrichissement des prêts."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.employee_loans.application import enrichment
from tests.unit.saisies_avances.test_quotite_saisissable_legale import BAREME


@pytest.fixture(autouse=True)
def _bareme_de_la_quotite():
    with patch.object(
        enrichment, "get_bareme_quotite_saisissable", return_value=BAREME, create=True
    ) as bareme:
        yield bareme
