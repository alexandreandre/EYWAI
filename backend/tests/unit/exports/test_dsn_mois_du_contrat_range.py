"""La DSN d'un mois qui appartient tout entier à un contrat rangé le déclare sur
la fiche de ce contrat [D4].

Rejeu de H.5 sur le site de test (01/11/2026) : une apprentie finit le 31/10, un
CDD commence le 01/11 (« Nouveau contrat » fait le 01/11). Son bulletin
d'octobre se calcule sur la fiche rangée de l'apprentissage, mais la DSN
d'octobre, faite ensuite, déclarait le CDD : début 01/11, sans motif de recours,
périodes d'octobre hors du contrat (DSN-VAL : 40.001 CCH-13 et SIG-14, 51.002,
78.003, 62.006…), et un cumul d'heures de la réduction parti du 01/11.
"""

from __future__ import annotations

import pytest

from app.modules.employees.application import contrat_du_mois
from app.modules.exports.infrastructure import export_dsn
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

SAL, SOC, RANGE = "emp-1", "co-1", "periode-1"
AFFILIATIONS = [{"id_affiliation": "1", "id_contrat": "1", "option": "E", "population": "841"}]
FICHE_CDD = {
    "id": SAL,
    "company_id": SOC,
    "first_name": "Camille",
    "last_name": "Exemple",
    "nir": "2850575123456",
    "contract_type": "CDD",
    "hire_date": "2026-11-01",
    "contract_end_date": "2027-04-30",
    "statut": "Non-Cadre",
    "classification_conventionnelle": {"numero_contrat_dsn": "00001", "motif_recours": "02"},
    "specificites_paie": {"affiliations_psc": AFFILIATIONS},
}
FICHE_APPRENTISSAGE = {
    "contract_type": "Apprentissage",
    "hire_date": "2026-09-01",
    "contract_end_date": "2026-10-31",
    "classification_conventionnelle": {"numero_contrat_dsn": "00000"},
    "specificites_paie": {"affiliations_psc": AFFILIATIONS},
}


def _tables() -> dict:
    return {
        "employees": [dict(FICHE_CDD)],
        "payslips": [
            {
                "id": "octobre",
                "company_id": SOC,
                "employee_id": SAL,
                "year": 2026,
                "month": 10,
                "contract_period_id": None,
                "payslip_data": {"salaire_brut": 1353.85, "synthese_net": {"net_imposable": 1246.91}},
            }
        ],
        "employee_contract_periods": [
            {
                "id": RANGE,
                "employee_id": SAL,
                "date_debut": "2026-09-01",
                "date_fin": "2026-10-31",
                "contract_type": "Apprentissage",
                "fiche": FICHE_APPRENTISSAGE,
            }
        ],
        "employee_exits": [
            {"employee_id": SAL, "company_id": SOC, "status": "archivee", "exit_type": "fin_cdd",
             "last_working_day": "2026-10-31"}
        ],
    }


def _brancher(monkeypatch, tables: dict) -> None:
    BaseEnMemoire(tables).brancher(monkeypatch)
    # Le conftest coupe cette lecture ; ici, elle lit la base en mémoire.
    lecteur = contrat_du_mois.lecteur_contrats
    monkeypatch.setattr(
        lecteur, "contrat_passe_du_mois",
        lambda *a: contrat_du_mois.LecteurContrats.contrat_passe_du_mois(lecteur, *a),
    )


def test_octobre_se_declare_sur_la_fiche_de_l_apprentissage(monkeypatch):
    _brancher(monkeypatch, _tables())
    lignes, totaux = export_dsn.get_dsn_employees_data(SOC, "2026-10")

    assert len(lignes) == 1
    fiche = lignes[0]["employee"]
    assert fiche["hire_date"] == "2026-09-01"
    assert fiche["contract_type"] == "Apprentissage"
    assert fiche["classification_conventionnelle"]["numero_contrat_dsn"] == "00000"
    assert totaux["nombre_contrats"] == 1


def test_le_mois_du_nouveau_contrat_garde_la_fiche_du_jour(monkeypatch):
    tables = _tables()
    tables["payslips"][0].update({"id": "novembre", "month": 11})
    _brancher(monkeypatch, tables)
    lignes, _ = export_dsn.get_dsn_employees_data(SOC, "2026-11")

    assert lignes[0]["employee"]["hire_date"] == "2026-11-01"
    assert lignes[0]["employee"]["contract_type"] == "CDD"
