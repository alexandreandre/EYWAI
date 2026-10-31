"""OD de paie d'un mois à deux contrats : une ligne par bulletin, les saisies
au bulletin de leur contrat, un seul salarié compté (D3)."""

from __future__ import annotations

import pytest

from app.modules.exports.infrastructure import export_ecritures_comptables as od
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

SAL, SOC = "emp-1", "co-1"
SALARIE = {"id": SAL, "first_name": "Camille", "last_name": "Exemple", "company_id": SOC, "companies": {"company_name": "Soc"}}


def _bulletin(id_, contrat=None):
    return {
        "id": id_, "company_id": SOC, "employee_id": SAL, "year": 2026, "month": 11,
        "contract_period_id": contrat, "payslip_data": {"salaire_brut": 1000.0, "net_a_payer": 800.0},
        "employees": SALARIE,
    }


def test_les_saisies_vont_au_bulletin_de_leur_contrat(monkeypatch):
    BaseEnMemoire(
        {
            "payslips": [_bulletin("ancien", "periode-1"), _bulletin("nouveau")],
            "monthly_inputs": [
                {"company_id": SOC, "employee_id": SAL, "year": 2026, "month": 11, "name": "Indemnité",
                 "amount": 50, "is_socially_taxed": False, "contract_period_id": "periode-1"},
            ],
        }
    ).brancher(monkeypatch)
    vues: dict = {}

    def ligne(*, payslip_id, saisies_du_salarie, **_k):
        vues[payslip_id] = [s["amount"] for s in saisies_du_salarie]
        return {"brut": 1000.0, "net_a_payer": 800.0, "cotisations_salariales": 0.0,
                "cotisations_patronales": 0.0, "pas": 0.0}

    monkeypatch.setattr(od, "ligne_od_du_bulletin", ligne)
    lignes, totaux = od.get_payslip_data_for_od(SOC, "2026-11")
    assert vues == {"ancien": [50], "nouveau": []}
    assert len(lignes) == 2
    assert totaux["employees_count"] == 1
    assert totaux["total_brut"] == 2000.0


def test_la_provision_somme_les_deux_bulletins_du_mois(monkeypatch):
    from app.modules.exports.infrastructure import export_provision_cp as provision

    BaseEnMemoire(
        {"payslips": [{**_bulletin("ancien", "periode-1")}, {**_bulletin("nouveau")}]}
    ).brancher(monkeypatch)
    assert provision._lire_bulletins(SOC, [(2026, 11)])[SAL][(2026, 11)] == (2000.0, 0.0)


@pytest.mark.parametrize(
    "module_path",
    ["app.modules.exports.infrastructure.export_journal_paie", "app.modules.payroll.exports.journal_paie"],
)
def test_le_journal_compte_un_salarie(module_path, monkeypatch):
    import importlib

    module = importlib.import_module(module_path)
    BaseEnMemoire({"payslips": [_bulletin("ancien", "periode-1"), _bulletin("nouveau")]}).brancher(monkeypatch)
    lignes, totaux = module.get_journal_paie_data(SOC, "2026-11")
    assert len(lignes) == 2
    assert totaux["employees_count"] == 1


def test_la_dsn_d_un_mois_a_deux_contrats_est_refusee_nommement():
    """La forme de cette DSN (deux contrats, D3.2) n'est pas encore faite :
    refus nommé plutôt qu'une DSN qui perdrait un bulletin."""
    from app.modules.exports.infrastructure.export_dsn import check_dsn_data

    emp = {"id": SAL, "first_name": "Camille", "last_name": "Exemple", "nir": "1850575123456", "contract_type": "CDI"}
    anomalies, _ = check_dsn_data(
        SOC,
        "2026-11",
        [{"employee": emp, "brut": 900.0, "net_imposable": 700.0, "deux_contrats": True}],
        {"siret": "73282932000074", "code_naf": "2229A"},
        essai=True,
    )
    assert {
        "type": "error",
        "message": (
            "Novembre 2026 : Camille Exemple a deux contrats dans le mois. "
            "La DSN de ce cas n'est pas encore faite par Martine."
        ),
        "severity": "blocking",
        "employee_id": SAL,
        "employee_name": "Camille Exemple",
    } in anomalies


def test_la_dsn_garde_le_bulletin_du_contrat_de_la_fiche_et_signale_l_autre(monkeypatch):
    from app.modules.exports.infrastructure.export_dsn import _bulletins_par_salarie

    par_salarie, deux_contrats = _bulletins_par_salarie([_bulletin("ancien", "periode-1"), _bulletin("nouveau")])
    assert par_salarie[SAL]["id"] == "nouveau"
    assert deux_contrats == {SAL}
