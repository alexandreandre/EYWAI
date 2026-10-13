"""Comptabilité de la réduction générale : ventilée comme la DSN.

La DSN partage la réduction entre l'Urssaf (code 018) et la retraite
complémentaire (code 106, 6,01 / T de la réduction, soit 15,1 % en 2026 : prouvé
au centime sur les DSN de Quadra de Colorplast). La comptabilité rangeait toute
la réduction à l'Urssaf. Décision du 12/10/2026 : l'OD, les charges par caisse et
le paiement des organismes la ventilent comme la DSN, avec la même fonction.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import (
    part_retraite_complementaire_de_la_reduction,
)
from app.modules.exports.domain.accounting_plan import (
    ORGANISME_RETRAITE,
    ORGANISME_URSSAF,
    resolve_organisme_from_coti_id,
)
from app.modules.exports.infrastructure.export_charges_sociales import _aggregate_charges
from app.modules.exports.infrastructure.export_ecritures_comptables import ligne_od_du_bulletin

pytestmark = pytest.mark.unit

FNAL_MOINS_50 = {"coti_id": "fnal", "libelle": "FNAL", "base": 3000.0, "taux_patronal": 0.001, "montant_patronal": 3.0}


def _bulletin(reduction: float) -> dict:
    return {
        "salaire_brut": 3000.0,
        "net_a_payer": 2400.0,
        "structure_cotisations": {
            "total_salarial": 600.0,
            "total_patronal": 3.0 + reduction,
            "bloc_principales": [
                {"coti_id": "securite_sociale_maladie", "libelle": "Maladie", "montant_salarial": 600.0},
                FNAL_MOINS_50,
            ],
            "bloc_allegements": [
                {
                    "coti_id": "reduction_generale",
                    "libelle": "Réduction générale de cotisations patronales",
                    "base": 3000.0,
                    "montant_patronal": reduction,
                }
            ],
        },
    }


def test_la_part_retraite_est_celle_de_la_dsn():
    # Septembre de Colorplast : réduction de 1 704,85 €, dont 257,38 € à la retraite.
    assert part_retraite_complementaire_de_la_reduction(-1704.85, [FNAL_MOINS_50]) == -257.38


def test_la_ligne_comptable_de_la_reduction_est_ventilee():
    ligne = ligne_od_du_bulletin(
        payslip_id="ps-1",
        employee={"id": "emp-1"},
        payslip_data=_bulletin(-1000.0),
        saisies_du_salarie=[],
        compte_de_saisie=lambda _t: "",
    )
    reductions = {
        c["coti_id"]: c["montant_patronal"]
        for c in ligne["cotisations_detail"]
        if str(c.get("coti_id")).startswith("reduction_generale")
    }
    assert reductions == {"reduction_generale": -849.03, "reduction_generale_retraite": -150.97}
    # Le total des charges ne bouge pas.
    assert round(sum(float(c.get("montant_patronal") or 0) for c in ligne["cotisations_detail"]), 2) == -997.0


def test_la_part_retraite_se_range_a_la_retraite_complementaire():
    assert resolve_organisme_from_coti_id("reduction_generale_retraite") == ORGANISME_RETRAITE
    assert resolve_organisme_from_coti_id("reduction_generale") == ORGANISME_URSSAF


def test_les_charges_par_caisse_portent_la_ventilation():
    ligne = ligne_od_du_bulletin(
        payslip_id="ps-1",
        employee={"id": "emp-1"},
        payslip_data=_bulletin(-1000.0),
        saisies_du_salarie=[],
        compte_de_saisie=lambda _t: "",
    )
    _, resume, _ = _aggregate_charges([ligne])
    par_caisse = {r["Organisme"]: r["Part patronale"] for r in resume}
    assert par_caisse[ORGANISME_RETRAITE] == -150.97
    assert par_caisse[ORGANISME_URSSAF] == round(3.0 - 849.03, 2)
