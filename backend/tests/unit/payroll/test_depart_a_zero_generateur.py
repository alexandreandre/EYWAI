"""[B12] « Générer quand même, en partant de cumuls à zéro », au générateur.

Sans la sortie, le premier bulletin d'un collaborateur payé avant Martine, sans
bascule ni solde d'ouverture, est refusé (422, code `reprise_non_posee`, que
l'écran sait lire). Avec elle, il se calcule sur des cumuls à zéro, porte une
alerte et garde la trace du choix (qui, quand) dans `payslip_data`. Les autres
cumuls manquants (chaîne rompue, solde d'ouverture absent après une bascule)
restent refusés, sortie ou pas.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from app.modules.payroll.application import empreinte_entrees_service
from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents import payslip_run_heures
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
from app.shared.reprise_paie import RepriseNonPosee
from tests.unit.payroll.test_filet_heures_sur_arret import (  # noqa: F401 — fixture `moteur`
    EMP,
    _Base,
    moteur,
)

pytestmark = pytest.mark.unit

TRACE = {"par": "RH Essai", "par_id": "user-rh-1", "le": "2026-10-12T18:05:00+00:00"}
REPRISE = RepriseNonPosee("La paie de cette société se faisait avant Martine (…).")


def _preparer(monkeypatch, raison) -> dict:
    """Base sans cumul d'août ; la garde rend `raison` ; le calcul s'arrête juste
    avant l'enregistrement, avec ce qu'il allait écrire."""
    vu: dict = {}

    def run_espion(employee_path, *_a, **_k):
        vu["cumuls"] = json.loads((employee_path / "cumuls" / "08.json").read_text(encoding="utf-8"))
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    def avant_enregistrement(payslip_data, **_k):
        vu["payslip_data"] = payslip_data
        raise RuntimeError("arrêt du test avant l'enregistrement")

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run_espion)
    monkeypatch.setattr(
        empreinte_entrees_service,
        "poser_empreinte_complementaire_depuis_lectures",
        avant_enregistrement,
    )
    monkeypatch.setattr(pg, "supabase", _Base([], compensation=False))
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: []})
    monkeypatch.setattr(pg, "raison_de_cumul_manquant", lambda *_a, **_k: raison)
    return vu


def test_sans_la_sortie_la_reprise_non_posee_est_refusee_avec_son_code(monkeypatch, moteur):  # noqa: F811
    vu = _preparer(monkeypatch, REPRISE)
    with pytest.raises(HTTPException) as refus:
        pg.process_payslip_generation(EMP, 2026, 9)
    assert refus.value.status_code == 422
    assert refus.value.detail == {"code": "reprise_non_posee", "message": str(REPRISE)}
    assert "cumuls" not in vu


def test_avec_la_sortie_le_bulletin_part_de_zero_avec_alerte_et_trace(monkeypatch, moteur):  # noqa: F811
    vu = _preparer(monkeypatch, REPRISE)
    with pytest.raises(HTTPException):
        pg.process_payslip_generation(EMP, 2026, 9, depart_a_zero=TRACE)

    assert vu["cumuls"]["cumuls"]["brut_total"] == 0.0
    donnees = vu["payslip_data"]
    assert donnees["depart_a_zero_force"] == TRACE
    codes = [a.get("code") for a in donnees.get("alertes_baremes") or []]
    assert codes.count("cumuls_partis_de_zero") == 1


def test_une_chaine_rompue_reste_refusee_meme_avec_la_sortie(monkeypatch, moteur):  # noqa: F811
    vu = _preparer(monkeypatch, "La chaîne des cumuls est rompue.")
    with pytest.raises(HTTPException) as refus:
        pg.process_payslip_generation(EMP, 2026, 9, depart_a_zero=TRACE)
    assert refus.value.status_code == 422
    assert refus.value.detail == "La chaîne des cumuls est rompue."
    assert "cumuls" not in vu


def test_le_generateur_forfait_offre_la_meme_sortie():
    """Même règle au forfait jours : même refus structuré, même alerte, même trace."""
    import inspect

    from app.modules.payroll.documents import payslip_generator_forfait as pgf

    signature = inspect.signature(pgf.process_payslip_generation_forfait)
    assert "depart_a_zero" in signature.parameters
    source = inspect.getsource(pgf.process_payslip_generation_forfait)
    assert "detail_du_refus(raison)" in source
    assert "alerte_depart_a_zero(depart_a_zero)" in source
    assert '"depart_a_zero_force"' in source
