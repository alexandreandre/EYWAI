"""La DSN d'un mois à deux contrats lit les deux bulletins (D3.2).

Le CDD finit le 10/11 (bulletin rangé, `contract_period_id` rempli, sur la
fiche rangée avec son contrat), le nouveau contrat commence le 17/11.
"""

from __future__ import annotations

import pytest

from app.modules.exports.infrastructure import export_dsn
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

SAL, SOC, RANGE = "emp-1", "co-1", "periode-1"
AFFILIATIONS = [{"id_affiliation": "1", "id_contrat": "1", "option": "E", "population": "841"}]
FICHE = {
    "id": SAL,
    "company_id": SOC,
    "first_name": "Camille",
    "last_name": "Exemple",
    "nir": "1850575123456",
    "contract_type": "CDI",
    "hire_date": "2026-11-17",
    "statut": "Non-Cadre",
    "classification_conventionnelle": {"numero_contrat_dsn": "00001"},
    "specificites_paie": {"affiliations_psc": AFFILIATIONS},
}
FICHE_RANGEE = {
    "contract_type": "CDD",
    "hire_date": "2026-07-01",
    "contract_end_date": "2026-11-10",
    "classification_conventionnelle": {"numero_contrat_dsn": "00000"},
    "specificites_paie": {"affiliations_psc": AFFILIATIONS},
}


def _bulletin(id_: str, brut: float, contrat: str | None = None) -> dict:
    return {
        "id": id_,
        "company_id": SOC,
        "employee_id": SAL,
        "year": 2026,
        "month": 11,
        "contract_period_id": contrat,
        "payslip_data": {"salaire_brut": brut, "synthese_net": {"net_imposable": brut * 0.8}},
    }


def _base(payslips: list[dict], fiche_rangee: dict | None = FICHE_RANGEE) -> dict:
    return {
        "employees": [dict(FICHE)],
        "payslips": payslips,
        "employee_contract_periods": [
            {
                "id": RANGE,
                "employee_id": SAL,
                "date_debut": "2026-07-01",
                "date_fin": "2026-11-10",
                "contract_type": "CDD",
                "fiche": fiche_rangee,
            }
        ],
        "employee_exits": [
            {"employee_id": SAL, "company_id": SOC, "status": "archivee", "exit_type": "fin_cdd",
             "last_working_day": "2026-11-10"}
        ],
    }


def _donnees(monkeypatch, tables: dict):
    BaseEnMemoire(tables).brancher(monkeypatch)
    return export_dsn.get_dsn_employees_data(SOC, "2026-11")


def test_la_ligne_porte_les_deux_bulletins(monkeypatch):
    lignes, totaux = _donnees(
        monkeypatch, _base([_bulletin("ancien", 700.0, RANGE), _bulletin("nouveau", 900.0)])
    )
    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne["payslip"]["id"] == "nouveau"
    assert ligne["employee"]["hire_date"] == "2026-11-17"
    precedent = ligne["contrat_precedent"]
    assert precedent["payslip"]["id"] == "ancien"
    assert precedent["employee"]["hire_date"] == "2026-07-01"
    assert precedent["employee"]["classification_conventionnelle"]["numero_contrat_dsn"] == "00000"
    assert (totaux["nombre_salaries"], totaux["nombre_contrats"]) == (1, 2)
    assert totaux["masse_salariale_brute"] == 1600.0


def test_la_sortie_du_10_va_a_l_ancien_contrat(monkeypatch):
    lignes, _ = _donnees(
        monkeypatch, _base([_bulletin("ancien", 700.0, RANGE), _bulletin("nouveau", 900.0)])
    )
    assert lignes[0]["contrat_precedent"]["employee"]["sortie_dsn"]["last_working_day"] == "2026-11-10"
    assert "sortie_dsn" not in lignes[0]["employee"]


def test_l_ancien_contrat_seul_se_declare_sur_sa_fiche_rangee(monkeypatch):
    """Le bulletin du nouveau contrat n'est pas encore généré."""
    lignes, totaux = _donnees(monkeypatch, _base([_bulletin("ancien", 700.0, RANGE)]))
    assert len(lignes) == 1
    assert lignes[0]["payslip"]["id"] == "ancien"
    assert lignes[0]["employee"]["hire_date"] == "2026-07-01"
    assert "contrat_precedent" not in lignes[0]
    assert totaux["nombre_contrats"] == 1


def _anomalies(ligne: dict) -> list[str]:
    anomalies, _ = export_dsn.check_dsn_data(
        SOC, "2026-11", [ligne], {"siret": "73282932000074", "code_naf": "2229A"}, essai=True
    )
    return [a["message"] for a in anomalies if a["severity"] == "blocking"]


def test_le_mois_a_deux_contrats_n_est_plus_refuse(monkeypatch):
    lignes, _ = _donnees(
        monkeypatch, _base([_bulletin("ancien", 700.0, RANGE), _bulletin("nouveau", 900.0)])
    )
    assert not [m for m in _anomalies(lignes[0]) if "deux contrats" in m]


def test_sans_fiche_rangee_le_mois_est_refuse_nommement(monkeypatch):
    lignes, _ = _donnees(
        monkeypatch,
        _base([_bulletin("ancien", 700.0, RANGE), _bulletin("nouveau", 900.0)], fiche_rangee=None),
    )
    assert "contrat_precedent" not in lignes[0]
    assert (
        "Novembre 2026 : Camille Exemple a deux contrats dans le mois, mais la fiche de son "
        "contrat précédent n'a pas été rangée : la DSN ne peut pas déclarer ce contrat."
    ) in _anomalies(lignes[0])


def test_deux_contrats_sous_le_meme_numero_sont_refuses(monkeypatch):
    """CT 40.009 CCH-12 : un contrat rangé avant que « Nouveau contrat » pose
    le numéro suivant."""
    lignes, _ = _donnees(
        monkeypatch,
        _base(
            [_bulletin("ancien", 700.0, RANGE), _bulletin("nouveau", 900.0)],
            fiche_rangee={**FICHE_RANGEE, "classification_conventionnelle": {"numero_contrat_dsn": "00001"}},
        ),
    )
    assert (
        "Novembre 2026 : Camille Exemple a deux contrats dans le mois, sous le même numéro de "
        "contrat DSN (00001) : la DSN ne peut pas les distinguer. Le numéro du nouveau "
        "contrat se change par le support."
    ) in _anomalies(lignes[0])
