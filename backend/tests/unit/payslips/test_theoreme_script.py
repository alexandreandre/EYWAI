"""Le test du théorème ne passe jamais pour vert sans avoir rien joué (R-178, R-179)."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
EMPLOYE = {"id": "e1", "hire_date": "2020-01-01", "contract_end_date": None}


class FauxSupabase:
    """Les lectures du script, par table ; aucune écriture possible."""

    def __init__(self, **tables):
        self.tables = tables
        self.lues = []

    def table(self, nom):
        self.lues.append(nom)
        lignes = self.tables.get(nom, [])
        requete = types.SimpleNamespace()
        for methode in ("select", "eq", "match", "in_"):
            setattr(requete, methode, lambda *a, **k: requete)
        requete.single = lambda: types.SimpleNamespace(
            execute=lambda: types.SimpleNamespace(data=lignes[0] if lignes else None)
        )
        requete.execute = lambda: types.SimpleNamespace(data=lignes)
        return requete


@pytest.fixture
def script(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    monkeypatch.setitem(sys.modules, "piege", types.SimpleNamespace(poser_le_piege=lambda: None))
    spec = importlib.util.spec_from_file_location("theoreme_a_tester", SCRIPTS / "theoreme_correction_a_la_main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "lecture_seule", contextlib.nullcontext)
    monkeypatch.setattr(module, "raison_de_blocage_avant_bascule", lambda *a, **k: None, raising=False)
    # L'application remplace builtins.print par le journal : on lit ici ce que le script dit.
    module.sorties = []
    monkeypatch.setattr(module, "print", lambda *a, **k: module.sorties.append(" ".join(map(str, a))), raising=False)
    return module


def _jouer(module, monkeypatch, tmp_path, employes, un_salarie=None, payslips=()):
    joues = []

    def _defaut(company_id, employee_id, year, month, rapport):
        joues.append(employee_id)
        rapport.append({"salarie": employee_id, "ok": True, "cas": "joué"})

    monkeypatch.setattr(module, "supabase", FauxSupabase(companies=[{"id": "c1"}], employees=employes, payslips=list(payslips)))
    monkeypatch.setattr(module, "_un_salarie", un_salarie or _defaut)
    sortie = tmp_path / "s.json"
    code = module.main("Société", 2026, 10, str(sortie), "regularisations")
    return code, joues, sortie


def test_une_societe_sans_salarie_est_rouge(script, monkeypatch, tmp_path):
    code, joues, _ = _jouer(script, monkeypatch, tmp_path, [])
    assert code != 0
    assert joues == []
    assert "0 cas" in " ".join(script.sorties)


def test_les_salaries_sont_lus_sur_la_fiche_pas_sur_les_bulletins(script, monkeypatch, tmp_path):
    code, joues, _ = _jouer(script, monkeypatch, tmp_path, [EMPLOYE, {**EMPLOYE, "id": "e2"}], payslips=[])
    assert code == 0
    assert joues == ["e1", "e2"]


def test_un_salarie_absent_du_mois_n_est_pas_joue(script, monkeypatch, tmp_path):
    parti = {**EMPLOYE, "id": "e2", "contract_end_date": "2026-03-31"}
    pas_arrive = {**EMPLOYE, "id": "e3", "hire_date": "2026-12-01"}
    code, joues, _ = _jouer(script, monkeypatch, tmp_path, [EMPLOYE, parti, pas_arrive])
    assert code == 0
    assert joues == ["e1"]


def test_que_des_salaries_sautes_est_rouge(script, monkeypatch, tmp_path):
    def tous_sautes(company_id, employee_id, year, month, rapport):
        rapport.append({"salarie": employee_id, "ok": True, "cas": "bulletin de départ refusé", "saute": True})

    code, _, sortie = _jouer(script, monkeypatch, tmp_path, [EMPLOYE], tous_sautes)
    assert code != 0
    sorties = " ".join(script.sorties)
    assert "0 cas joué" in sorties and "1 sauté" in sorties
    assert json.loads(sortie.read_text())[0]["saute"] is True


def test_un_cas_en_echec_est_rouge(script, monkeypatch, tmp_path):
    def echec(company_id, employee_id, year, month, rapport):
        rapport.append({"salarie": employee_id, "ok": False, "cas": "x"})

    code, _, _ = _jouer(script, monkeypatch, tmp_path, [EMPLOYE], echec)
    assert code == 1


def test_un_mois_avant_la_bascule_est_refuse_sans_rien_jouer(script, monkeypatch, tmp_path):
    monkeypatch.setattr(script, "raison_de_blocage_avant_bascule", lambda *a, **k: "Le mois a été payé par le logiciel précédent.")
    code, joues, _ = _jouer(script, monkeypatch, tmp_path, [EMPLOYE])
    assert code == 2
    assert joues == []
    assert "logiciel précédent" in " ".join(script.sorties)


def test_le_bulletin_enregistre_reste_lu_pour_les_doublons(script, monkeypatch, tmp_path):
    vus = {}

    def directes(company_id, employee_id, year, month, rapport, enregistre=None):
        vus[employee_id] = enregistre
        rapport.append({"salarie": employee_id, "ok": True, "cas": "joué"})

    monkeypatch.setattr(script, "supabase", FauxSupabase(
        companies=[{"id": "c1"}], employees=[EMPLOYE], payslips=[{"employee_id": "e1", "payslip_data": {"a": 1}}]
    ))
    monkeypatch.setattr(script, "_corrections_directes", directes)
    code = script.main("Société", 2026, 10, str(tmp_path / "s.json"), "directes")
    assert code == 0
    assert vus == {"e1": {"a": 1}}
