"""Les deux générateurs posent l'empreinte complémentaire sur le bulletin enregistré.

Pas en bac à sable : rien n'y est enregistré, l'empreinte n'y servirait à rien,
et ses lectures en plus casseraient le rejeu des photos du filet.
"""

from __future__ import annotations

import inspect

import pytest

from app.modules.payroll.application import empreinte_entrees_service
from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents import payslip_run_heures
from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.payroll.domain.empreinte_entrees import CLE_EMPREINTE_COMPLEMENTAIRE
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
from tests.unit.payroll.test_filet_heures_sur_arret import (  # noqa: F401 — fixture `moteur`
    EMP,
    _Base,
    moteur,
)

pytestmark = pytest.mark.unit


def _ordre(source: str, bac_a_sable: str, pose: str, enregistrement: str) -> list[int]:
    # Le bac à sable rend aussi `"payslip_data": payslip_json_data` : l'enregistrement
    # est la dernière occurrence.
    return [source.index(bac_a_sable), source.index(pose), source.rindex(enregistrement)]


@pytest.mark.parametrize(
    ("module", "fonction"),
    [
        ("payslip_generator", "process_payslip_generation"),
        ("payslip_generator_forfait", "process_payslip_generation_forfait"),
    ],
)
def test_l_empreinte_complementaire_est_posee_apres_le_bac_a_sable_avant_l_enregistrement(module, fonction):
    import importlib

    mod = importlib.import_module(f"app.modules.payroll.documents.{module}")
    source = inspect.getsource(getattr(mod, fonction))
    bac_a_sable, pose, enregistrement = _ordre(
        source,
        "if bac_a_sable is not None:\n            # Bac à sable : rien n'est persisté",
        "poser_empreinte_complementaire_depuis_lectures(",
        '"payslip_data": payslip_json_data',
    )
    assert bac_a_sable < pose < enregistrement


def test_en_bac_a_sable_rien_n_est_lu_ni_pose(monkeypatch, moteur):  # noqa: F811
    def run(*_a, **_k):
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    def interdit(*_a, **_k):
        raise AssertionError("lecture des compléments en bac à sable")

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run)
    monkeypatch.setattr(pg, "supabase", _Base([], compensation=False))
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: []})
    monkeypatch.setattr(empreinte_entrees_service, "lire_complements", interdit)
    resultat = pg.process_payslip_generation(
        EMP, 2026, 9, bac_a_sable=BacASable(cumuls_precedents={"cumuls": {"brut_total": 1.0}})
    )
    assert CLE_EMPREINTE_COMPLEMENTAIRE not in (resultat["payslip_data"].get("parametres") or {})
