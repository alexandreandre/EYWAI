"""Congés payés au bulletin : marqueur d'origine et libellé daté."""

import pytest

from app.modules.payroll.documents.payslip_generator import _source_conges_par_date
from app.modules.payroll.engine.calcul_brut import _libelle_dates_conges

pytestmark = pytest.mark.unit


class TestSourceCongesParDate:
    def test_cp_l_emporte_sur_une_recup_le_meme_jour(self):
        rows = [
            {"type": "recuperation_modulation", "selected_days": ["2026-07-13"]},
            {"type": "conge_paye", "selected_days": ["2026-07-13", "2026-07-14"]},
        ]
        assert _source_conges_par_date(rows) == {
            "2026-07-13": "conge_paye",
            "2026-07-14": "conge_paye",
        }

    def test_recup_seule(self):
        rows = [{"type": "recuperation_modulation", "selected_days": ["2026-07-20"]}]
        assert _source_conges_par_date(rows) == {
            "2026-07-20": "recuperation_modulation"
        }


class TestLibelleDatesConges:
    def test_plages_consecutives_compressees(self):
        evs = [
            {"date_complete": "2026-07-13"},
            {"date_complete": "2026-07-15"},
            {"date_complete": "2026-07-16"},
            {"date_complete": "2026-07-17"},
        ]
        assert _libelle_dates_conges(evs) == "13/07, 15/07→17/07"

    def test_demi_journee_marquee_et_hors_plage(self):
        evs = [
            {"date_complete": "2026-07-13"},
            {"date_complete": "2026-07-14", "quotite_absence": 0.5},
            {"date_complete": "2026-07-15"},
        ]
        assert _libelle_dates_conges(evs) == "13/07, 14/07 (½), 15/07"

    def test_liste_longue_repliee_en_bornes(self):
        evs = [{"date_complete": f"2026-07-{j:02d}"} for j in range(1, 30, 2)]
        assert _libelle_dates_conges(evs) == "du 01/07 au 29/07"

    def test_vide_sans_dates(self):
        assert _libelle_dates_conges([{"type": "conges_payes"}]) == ""
