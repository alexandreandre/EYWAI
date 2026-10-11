"""« Générer le bulletin » (page Simulation) enregistre la simulation sans erreur 500. [D4]

Relevé à l'écran (vidéo G, 11/10/2026) : POST /api/simulation/create-payslip
répondait 500 « Erreur lors de la création de la simulation. » pour tout
personnage et tout scénario. Le calcul passe (rejoué sous piège à écritures) ;
c'est l'enregistrement qui échoue. La table `simulations` porte deux
contraintes (lues sur la base de test le 11/10/2026) :

- `simulations_simulation_type_check` : `simulation_type` vaut
  'reverse_calculation' ou 'payslip_simulation' — le code écrivait 'payslip' ;
- `unique_simulation_name` : UNIQUE (employee_id, company_id, month, year,
  scenario_name) — l'écran envoie toujours « Simulation salarié » : une seconde
  simulation du même salarié pour le même mois échouait à son tour.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.modules.payroll.application import simulation_queries as sq

pytestmark = pytest.mark.unit

#: Les valeurs que la contrainte de la table accepte.
TYPES_ACCEPTES = {"reverse_calculation", "payslip_simulation"}


@pytest.fixture
def enregistrees(monkeypatch):
    lignes: list[dict] = []
    monkeypatch.setattr(sq, "load_company", lambda _cid: {"id": "soc", "name": "Société"})
    monkeypatch.setattr(sq, "load_employee", lambda _eid, _cid: {"id": "emp"})
    monkeypatch.setattr(sq, "load_baremes", lambda: {})
    monkeypatch.setattr(sq, "_apply_cc_minimum_override", lambda scenario, **_k: scenario)
    monkeypatch.setattr(sq, "employee_to_payroll_payload", lambda *_a: {})
    monkeypatch.setattr(sq, "company_to_payroll_payload", lambda *_a: {})
    monkeypatch.setattr(
        sq.simulation_commands,
        "creer_simulation_bulletin",
        lambda **_k: {"payslip_data": {"net_a_payer": 1700.0}},
    )

    def inserer(payload):
        # La contrainte `unique_simulation_name`, telle que PostgREST la renvoie.
        cle = (payload["employee_id"], payload["company_id"], payload["month"], payload["year"], payload["scenario_name"])
        if any(
            (l["employee_id"], l["company_id"], l["month"], l["year"], l["scenario_name"]) == cle for l in lignes
        ):
            raise RuntimeError(
                "{'code': '23505', 'message': 'duplicate key value violates unique constraint "
                "\"unique_simulation_name\"'}"
            )
        lignes.append(payload)
        return f"sim-{len(lignes)}"

    monkeypatch.setattr(sq.simulation_repository, "insert_simulation_row", inserer)
    return lignes


def _creer(nom="Simulation salarié"):
    return sq.create_payslip_simulation_record(
        company_id="soc",
        created_by="rh",
        employee_id="emp",
        month=10,
        year=2026,
        scenario_name=nom,
        scenario_data={"salaire_base_override": 2200},
        prefill_from_real=False,
    )


def test_le_type_ecrit_est_celui_que_la_table_accepte(enregistrees):
    _creer()

    assert enregistrees[0]["simulation_type"] in TYPES_ACCEPTES
    assert enregistrees[0]["simulation_type"] == "payslip_simulation"


def test_deux_simulations_du_meme_mois_ont_deux_noms(enregistrees):
    _creer()
    _creer()

    noms = [ligne["scenario_name"] for ligne in enregistrees]
    assert len(set(noms)) == 2
    assert all(nom.startswith("Simulation salarié") for nom in noms)


def test_le_nom_dit_le_jour_et_l_heure():
    nom = sq.nom_de_simulation("Simulation salarié", datetime(2026, 10, 11, 19, 42, 5, 123456))

    assert nom.startswith("Simulation salarié du 11/10/2026 à 19:42:05")


def test_le_resultat_porte_l_identifiant_et_le_bulletin(enregistrees):
    resultat = _creer()

    assert resultat["simulation_id"] == "sim-1"
    assert resultat["payslip_data"] == {"net_a_payer": 1700.0}
