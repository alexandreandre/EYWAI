"""Le calcul d'un mois incomplet reçoit le planning du mois et de ses deux voisins.

L'horaire d'une entrée le 28 se lit sur le mois suivant (le jeudi et le
vendredi de la semaine d'embauche n'existent qu'en octobre), celui d'une
sortie le 2 sur le mois précédent : le générateur pose donc le planning des
trois mois qu'il lit déjà en base dans le dossier de travail, et le calcul du
bulletin les relit datés.
"""

from __future__ import annotations

import json

import pytest

from app.modules.payroll.documents import payslip_run_heures
from app.modules.payroll.documents.payslip_run_heures import jours_prevus_autour_du_mois
from tests.unit.payroll.test_filet_heures_sur_arret import (  # noqa: F401 — fixture `moteur`
    _generer,
    moteur,
)

pytestmark = pytest.mark.unit


def _poser(dossier, mois, jours):
    (dossier / "calendriers").mkdir(parents=True, exist_ok=True)
    (dossier / "calendriers" / f"{mois:02d}.json").write_text(
        json.dumps({"calendrier_prevu": jours}), encoding="utf-8"
    )


def test_trois_mois_dates(tmp_path):
    _poser(tmp_path, 8, [{"jour": 31, "type": "travail", "heures_prevues": 8.5}])
    _poser(tmp_path, 9, [{"jour": 1, "type": "travail", "heures_prevues": 8.5}])
    _poser(tmp_path, 10, [{"jour": 1, "type": "travail", "heures_prevues": 8.5}])
    jours = jours_prevus_autour_du_mois(tmp_path, 2026, 9)
    assert [(j["annee"], j["mois"], j["jour"]) for j in jours] == [
        (2026, 8, 31), (2026, 9, 1), (2026, 10, 1)
    ]


def test_janvier_lit_decembre_de_l_annee_precedente(tmp_path):
    _poser(tmp_path, 12, [{"jour": 31, "type": "travail", "heures_prevues": 7.0}])
    _poser(tmp_path, 1, [{"jour": 2, "type": "travail", "heures_prevues": 7.0}])
    jours = jours_prevus_autour_du_mois(tmp_path, 2026, 1)
    assert [(j["annee"], j["mois"], j["jour"]) for j in jours] == [
        (2025, 12, 31), (2026, 1, 2)
    ]


def test_mois_voisin_absent_ou_illisible(tmp_path):
    _poser(tmp_path, 9, [{"jour": 1, "type": "travail", "heures_prevues": 8.5}])
    (tmp_path / "calendriers" / "10.json").write_text("{pas du json", encoding="utf-8")
    jours = jours_prevus_autour_du_mois(tmp_path, 2026, 9)
    assert [(j["mois"], j["jour"]) for j in jours] == [(9, 1)]


def test_le_generateur_pose_le_planning_des_mois_voisins(monkeypatch, moteur):  # noqa: F811 — fixture importée
    recu: dict = {}

    def run_espion(employee_path, year, month, *_a, **_k):
        recu["jours"] = jours_prevus_autour_du_mois(employee_path, year, month)
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run_espion)
    _generer(monkeypatch, compensation=False)

    mois = sorted({(j["annee"], j["mois"]) for j in recu["jours"]})
    assert mois == [(2026, 8), (2026, 9), (2026, 10)]
    # Le jeudi 1er octobre porte l'horaire du planning d'octobre (8 h).
    premier_octobre = next(
        j for j in recu["jours"] if (j["mois"], j["jour"]) == (10, 1)
    )
    assert (premier_octobre["type"], premier_octobre["heures_prevues"]) == ("travail", 8.0)
