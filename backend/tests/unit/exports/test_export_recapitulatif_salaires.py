"""« Récapitulatif des salaires du mois » (ex-« Attestations & annexes », 05/11/2026).

Ce tableau n'est pas une attestation : les lettres se génèrent depuis la fiche
du salarié. Il portait le début de l'identifiant interne en guise de matricule
et un « Statut » toujours « Généré ».
"""
from __future__ import annotations

import io

import pytest
from openpyxl import load_workbook

from app.modules.exports.infrastructure import export_attestations as module

pytestmark = pytest.mark.unit

BULLETINS = [
    {
        "id": "ps-1",
        "employee_id": "0f3c2a9e-1111-2222-3333-444455556666",
        "payslip_data": {
            "salaire_brut": 2200.0,
            "net_a_payer": 1650.0,
            "synthese_net": {"net_imposable": 1790.0},
        },
        "employees": {
            "id": "0f3c2a9e-1111-2222-3333-444455556666",
            "first_name": "Jeanne",
            "last_name": "Essai",
            "matricule": "00042",
            "company_id": "soc-1",
        },
    }
]


class _Requete:
    def __getattr__(self, _nom):
        return lambda *a, **k: self

    def execute(self):
        return type("R", (), {"data": BULLETINS})()


class _Base:
    def table(self, _nom):
        return _Requete()


@pytest.fixture(autouse=True)
def _base(monkeypatch):
    monkeypatch.setattr(module, "supabase", _Base())


def test_les_colonnes_du_recapitulatif():
    assert module.HEADERS == ["Matricule", "Employé", "Période", "Brut", "Net imposable", "Net à payer"]


def test_le_vrai_matricule_et_pas_de_statut():
    lignes = module.preview_attestations("soc-1", "2026-10")["details"]["lines"]
    assert lignes == [
        {
            "Matricule": "00042",
            "Employé": "Jeanne Essai",
            "Période": lignes[0]["Période"],
            "Brut": 2200.0,
            "Net imposable": 1790.0,
            "Net à payer": 1650.0,
        }
    ]


def test_le_fichier_excel():
    contenu = module.generate_attestations_export("soc-1", "2026-10", file_format="xlsx")
    feuille = load_workbook(io.BytesIO(contenu)).active
    assert feuille.title == "Récapitulatif"
    assert [c.value for c in feuille[1]] == module.HEADERS
    assert feuille["A2"].value == "00042"
