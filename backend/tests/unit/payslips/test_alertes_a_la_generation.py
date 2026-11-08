"""La revue tourne à la génération : le bulletin écrit est relu tout de suite [R-171]."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.application import commands as mod

pytestmark = pytest.mark.unit


def _client(donnees):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
        MagicMock(data={"payslip_data": donnees})
    )
    return client


def test_un_ecart_critique_remonte_a_la_generation():
    donnees = {
        "salaire_brut": 2100.0,
        "calcul_du_brut": [{"libelle": "Salaire de base", "gain": 2000.0, "perte": None}],
    }
    with patch.object(mod, "supabase", _client(donnees)):
        alertes = mod._alertes_de_coherence("ps-1")
    assert [a["code"] for a in alertes] == ["revue_B02"]
    assert "salaire brut" in alertes[0]["message"].lower()


def test_un_bulletin_coherent_ne_remonte_rien():
    donnees = {
        "salaire_brut": 2000.0,
        "calcul_du_brut": [{"libelle": "Salaire de base", "gain": 2000.0, "perte": None}],
    }
    with patch.object(mod, "supabase", _client(donnees)):
        assert mod._alertes_de_coherence("ps-1") == []


def test_une_lecture_impossible_n_echoue_pas_la_generation():
    client = MagicMock()
    client.table.side_effect = RuntimeError("base indisponible")
    with patch.object(mod, "supabase", client):
        assert mod._alertes_de_coherence("ps-1") == []
