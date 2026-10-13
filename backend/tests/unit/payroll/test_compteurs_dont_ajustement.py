"""Compteurs de congés imprimés : « dont ajustement » quand acquis − pris ≠ solde.

Après une reprise de soldes ou un recalage, le solde ne se retrouve plus par
« acquis − pris » (bulletin de septembre de Colorplast : acquis 25, pris 12,
solde 28). Décision du 12/10/2026 : les bulletins à venir disent de combien le
solde est ajusté, sans changer aucun solde ; les bulletins déjà remis ne sont
pas réimprimés autrement (une réimpression garde leurs compteurs).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.absences.domain.rules import poser_les_ajustements_des_compteurs
from app.modules.payroll.documents import payslip_editor
from app.modules.payroll.documents.bulletin_view import construire_compteurs
from app.modules.payroll.engine import bulletin as module_bulletin

pytestmark = pytest.mark.unit


def test_l_ajustement_est_l_ecart_entre_le_solde_et_acquis_moins_pris():
    soldes = poser_les_ajustements_des_compteurs(
        {
            "conges_payes": {"acquis": 4.16, "pris": 0.0, "solde": 2.63},
            "conges_payes_periode_precedente": {"acquis": 25.0, "pris": 12.0, "solde": 28.0},
        }
    )
    assert soldes["conges_payes"]["ajustement"] == -1.53
    assert soldes["conges_payes_periode_precedente"]["ajustement"] == 15.0
    # Aucun solde ne change.
    assert soldes["conges_payes"]["solde"] == 2.63
    assert soldes["conges_payes_periode_precedente"]["solde"] == 28.0


def test_pas_d_ajustement_quand_le_compte_tombe_juste():
    soldes = poser_les_ajustements_des_compteurs(
        {"conges_payes": {"acquis": 4.16, "pris": 1.0, "solde": 3.16}}
    )
    assert "ajustement" not in soldes["conges_payes"]


def test_un_depassement_n_est_pas_un_ajustement():
    # 7 j pris pour 5 acquis : solde imprimé 0, négatif de 2 (congé au-delà du solde).
    soldes = poser_les_ajustements_des_compteurs(
        {"conges_payes": {"acquis": 5.0, "pris": 7.0, "solde": 0.0, "depassement": 2.0}}
    )
    assert "ajustement" not in soldes["conges_payes"]


def test_le_bulletin_imprime_la_mention():
    compteurs = construire_compteurs(
        {
            "pied_de_page": {
                "solde_conges": {
                    "conges_payes": {"acquis": 4.16, "pris": 0, "solde": 2.63, "ajustement": -1.53},
                    "conges_payes_periode_precedente": {
                        "acquis": 25,
                        "pris": 12,
                        "solde": 28,
                        "ajustement": 15.0,
                    },
                }
            }
        }
    )
    assert "CP N-1 : solde dont ajustement de +15,00 j (reprise ou recalage)" in compteurs["notes"]
    assert "CP N : solde dont ajustement de −1,53 j (reprise ou recalage)" in compteurs["notes"]


def test_un_bulletin_d_avant_n_a_pas_la_mention():
    compteurs = construire_compteurs(
        {"pied_de_page": {"solde_conges": {"conges_payes": {"acquis": 25, "pris": 12, "solde": 28}}}}
    )
    assert not any("ajustement" in note for note in compteurs["notes"])


def test_une_reimpression_garde_les_compteurs_du_bulletin(monkeypatch, tmp_path):
    rendus: list[str] = []

    class _Html:
        def __init__(self, string: str):
            rendus.append(string)

        def write_pdf(self, chemin):
            Path(chemin).write_bytes(b"%PDF")

    class _Base:
        def table(self, *_a, **_k):
            return self

        def select(self, *_a, **_k):
            return self

        def match(self, *_a, **_k):
            return self

        def maybe_single(self):
            return self

        def execute(self):
            return type("R", (), {"data": None})()

    def _compteurs_du_jour(*_a, **_k):
        raise AssertionError("une réimpression ne recalcule pas les compteurs du bulletin")

    monkeypatch.setattr(payslip_editor, "HTML", _Html)
    monkeypatch.setattr(payslip_editor, "supabase", _Base())
    monkeypatch.setattr(payslip_editor, "payroll_engine_employee_bulletins", lambda _d: tmp_path)
    monkeypatch.setattr(module_bulletin, "build_solde_conges_pied_de_page", _compteurs_du_jour)

    payslip_editor.regenerate_pdf_from_data(
        payslip_data={
            "en_tete": {},
            "pied_de_page": {
                "solde_conges": {"conges_payes": {"acquis": 2.08, "pris": 0, "solde": 2.08}}
            },
        },
        employee_id="emp-1",
        employee_folder_name="Salarie_Filet",
        company_id="co-1",
        month=9,
        year=2026,
    )
    assert rendus and "2.08" in rendus[0]
