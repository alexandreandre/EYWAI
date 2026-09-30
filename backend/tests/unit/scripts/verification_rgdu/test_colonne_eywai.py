"""Ce que calcule EYWAI : heures et SMIC de référence du mois, ligne de réduction."""
import json

import pytest

from scripts.verification_rgdu.colonne_eywai import depuis_le_filet

pytestmark = pytest.mark.unit


def test_les_heures_du_mois_sont_la_difference_des_cumuls(tmp_path):
    def entree(h, rg):
        return {"payslip_data": {"structure_cotisations": {"bloc_allegements": [
            {"coti_id": "reduction_generale", "montant_patronal": rg}]}}, "cumuls": {"cumuls": {"heures_remunerees": h}}}
    f = tmp_path / "reference.json"
    f.write_text(json.dumps({"e1/2026-01": entree(159.13, -582.24), "e1/2026-02": entree(331.63, -600.0)}))
    d = depuis_le_filet(f)
    assert d[("e1", 1)].heures_reduction == 159.13
    assert d[("e1", 2)].heures_reduction == 172.5 and d[("e1", 2)].smic == round(172.5 * 12.02, 2)
    assert d[("e1", 2)].reduction_ligne == 600.0
