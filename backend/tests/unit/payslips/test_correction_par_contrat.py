"""Corriger le bulletin de l'ancien contrat d'un mois partagé : ses variables
portent sa clé, et c'est lui qui est recalculé (D3)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.application import corrections
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

PERIODE = {"employee_id": "emp-1", "company_id": "co-1", "year": 2026, "month": 11}
RANGE = "periode-1"


def test_les_heures_declarees_portent_la_cle_et_ne_touchent_que_leur_bulletin(monkeypatch):
    base = BaseEnMemoire(
        {
            "monthly_inputs": [
                {**PERIODE, "id": "hs-nouveau", "name": corrections.LIBELLE_HS_DECLAREES},
            ]
        }
    )
    base.brancher(monkeypatch)
    corrections._declarer_heures_sup(PERIODE, 2.0, 0.0, RANGE)
    lignes = base.lignes("monthly_inputs", employee_id="emp-1")
    assert {l["id"] for l in lignes if not l.get("contract_period_id")} == {"hs-nouveau"}
    assert all(l["contract_period_id"] == RANGE for l in lignes if l["id"] != "hs-nouveau")
    assert len(lignes) == 3


def test_le_recalcul_vise_le_bulletin_de_la_cle():
    bulletin = {"id": "ancien", **PERIODE, "contract_period_id": RANGE}
    cmd = MagicMock(modifier_bulletin_remis=False, current_user_id="u", current_user_name="RH")
    with patch.object(corrections, "generate_payslip", return_value=MagicMock(status="success")) as gen:
        corrections._recalculer(bulletin, cmd, "motif")
    assert gen.call_args[0][0].contract_period_id == RANGE


def test_le_bulletin_corrige_est_lu_avec_sa_cle():
    assert "contract_period_id" in corrections._COLONNES


def test_la_saisie_du_mois_montre_les_variables_du_contrat_de_la_fiche(monkeypatch):
    from app.modules.monthly_inputs.infrastructure.repository import SupabaseMonthlyInputsRepository

    BaseEnMemoire(
        {
            "monthly_inputs": [
                {**PERIODE, "id": "prime-ancien", "contract_period_id": RANGE},
                {**PERIODE, "id": "prime-nouveau"},
            ]
        }
    ).brancher(monkeypatch)
    depot = SupabaseMonthlyInputsRepository()
    assert [l["id"] for l in depot.list_by_employee_period("emp-1", 2026, 11, "co-1")] == ["prime-nouveau"]
    assert [l["id"] for l in depot.list_by_period(2026, 11, "co-1")] == ["prime-nouveau"]
