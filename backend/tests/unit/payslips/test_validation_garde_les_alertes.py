"""[J3] La validation garde en trace les alertes du moteur au lieu de les effacer.

Avant : `mark_payslip_validated` retirait `alertes_baremes` et
`synthese_net.alertes_maintien` du bulletin validé, et le journal d'audit ne
gardait que l'identifiant du salarié. Rien ne disait plus qu'un bulletin avait
été validé malgré une alerte (salaire sous le minimum conventionnel…). La
validation n'est pas bloquée pour autant : c'est une décision d'Alexandre.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.infrastructure import comparison_queries as cq

pytestmark = pytest.mark.unit

ALERTE_MINIMUM = {
    "code": "salaire_sous_minimum_conventionnel",
    "critique": True,
    "message": "Salaire de base sous le minimum conventionnel.",
}


class _Table:
    def __init__(self, etat: dict[str, Any]) -> None:
        self.etat = etat
        self.payload: dict[str, Any] | None = None

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def maybe_single(self):
        return self

    def update(self, payload):
        self.payload = payload
        self.etat["updates"].append(payload)
        return self

    def execute(self):
        if self.payload is not None:
            if "payslip_data" in self.payload:
                self.etat["payslip_data"] = self.payload["payslip_data"]
            return MagicMock(data=[{"id": "p-1", **self.payload}])
        return MagicMock(data={"payslip_data": dict(self.etat["payslip_data"])})


def _valider(payslip_data: dict[str, Any]) -> dict[str, Any]:
    etat: dict[str, Any] = {"payslip_data": payslip_data, "updates": []}
    base = MagicMock()
    base.table.side_effect = lambda _nom: _Table(etat)
    with patch.object(cq, "supabase", base):
        cq.mark_payslip_validated("p-1", "rh-1")
    return etat


def test_les_alertes_du_moteur_restent_en_trace_sur_le_bulletin_valide():
    etat = _valider(
        {
            "net_a_payer": 1500.0,
            "alertes_baremes": [ALERTE_MINIMUM],
            "synthese_net": {"net": 1500.0, "alertes_maintien": ["Maintien non calculé"]},
        }
    )

    final = etat["payslip_data"]
    # Le bandeau « action requise » ne s'affiche plus sur un bulletin validé…
    assert "alertes_baremes" not in final
    assert "alertes_maintien" not in final["synthese_net"]
    # … mais la trace dit ce que la RH a validé, quand et qui.
    trace = final["alertes_a_la_validation"]
    assert trace["alertes_baremes"] == [ALERTE_MINIMUM]
    assert trace["alertes_maintien"] == ["Maintien non calculé"]
    assert trace["par"] == "rh-1"
    assert trace["le"] == etat["updates"][0]["validated_at"]
    assert etat["updates"][0]["status"] == "valide"


def test_sans_alerte_aucune_trace_n_est_ajoutee():
    etat = _valider({"net_a_payer": 1500.0, "synthese_net": {"net": 1500.0}})
    assert "payslip_data" not in etat["updates"][0]
    assert "alertes_a_la_validation" not in etat["payslip_data"]
