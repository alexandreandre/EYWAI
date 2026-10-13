"""« DSN déposée hors de Martine » : l'étape du mois se marque faite à la main, tracée.

Tant que la DSN se dépose depuis l'ancien logiciel, l'étape « DSN et export
comptable faits » de la liste de contrôle ne passait jamais à « fait ». Décision
du 12/10/2026 : la gestionnaire la marque faite à la main ; l'historique des
exports garde qui, quand, et pour quel mois.
"""

from __future__ import annotations

from typing import get_args
from unittest.mock import patch

import pytest

from app.modules.exports.application import service
from app.modules.exports.application.scheduled_exports import EXPORT_TYPE_LABELS
from app.modules.exports.schemas.requests import ExportType

pytestmark = pytest.mark.unit


def test_le_type_existe_et_se_lit_en_clair():
    assert "dsn_hors_martine" in get_args(ExportType)
    assert EXPORT_TYPE_LABELS["dsn_hors_martine"] == "DSN déposée hors de Martine"


def test_le_marquage_s_inscrit_a_l_historique_au_nom_de_la_gestionnaire():
    with patch.object(service.commands, "record_export_history", return_value="exp-1") as ecrire:
        resultat = service.marquer_dsn_hors_martine("co-1", "user-1", "2026-10", "DSN déposée dans Quadra")
    (record,), _ = ecrire.call_args
    assert record["company_id"] == "co-1"
    assert record["export_type"] == "dsn_hors_martine"
    assert record["period"] == "2026-10"
    assert record["status"] == "generated"
    assert record["generated_by"] == "user-1"
    assert record["file_paths"] == []
    assert record["parameters"] == {"note": "DSN déposée dans Quadra"}
    assert resultat == {"export_id": "exp-1", "period": "2026-10"}


def test_une_periode_mal_formee_est_refusee():
    with patch.object(service.commands, "record_export_history") as ecrire:
        with pytest.raises(ValueError, match="mois"):
            service.marquer_dsn_hors_martine("co-1", "user-1", "octobre", None)
    ecrire.assert_not_called()
