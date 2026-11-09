"""R-327 : un état du bulletin illisible ne valide pas sans le filet.

`_etat_actuel_du_bulletin` rendait None sur une lecture ratée, et la validation
passait sans le contrôle de l'empreinte. La lecture est relue, puis la
validation est refusée avec une phrase qui dit quoi faire.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payslips.application import comparison_service as cs
from app.modules.payslips.application.dto import PayslipBadRequestError

pytestmark = pytest.mark.unit

_ETAT = "app.modules.payroll.application.empreinte_entrees_service.etat_dans_la_chaine"
DETAIL = {"employee_id": "e1", "year": 2026, "month": 10}


def test_lecture_ratee_refuse_la_validation():
    with patch(_ETAT, side_effect=RuntimeError("coupure")):
        with pytest.raises(PayslipBadRequestError) as exc:
            cs._etat_actuel_du_bulletin(DETAIL)
    assert "n'a pas été validé" in str(exc.value)
    assert "réessayez" in str(exc.value)


def test_lecture_reussie_rend_l_etat():
    with patch(_ETAT, return_value="etat") as etat:
        assert cs._etat_actuel_du_bulletin(DETAIL) == "etat"
    etat.assert_called_once_with("e1", 2026, 10)
