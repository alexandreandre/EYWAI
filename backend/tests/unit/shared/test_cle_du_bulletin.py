"""Deux bulletins le même mois : une lecture du mois rend celui du contrat demandé (D3)."""

from app.shared.cle_du_bulletin import CONFLIT_BULLETIN, du_contrat
from tests.unit.base_en_memoire import BaseEnMemoire

RANGE = "periode-ancien-contrat"


def _base() -> BaseEnMemoire:
    return BaseEnMemoire(
        {
            "payslips": [
                {"id": "nouveau", "employee_id": "e1", "year": 2026, "month": 11},
                {
                    "id": "ancien",
                    "employee_id": "e1",
                    "year": 2026,
                    "month": 11,
                    "contract_period_id": RANGE,
                },
            ]
        }
    )


def _du_mois(base: BaseEnMemoire, contrat):
    requete = base.table("payslips").select("id").match(
        {"employee_id": "e1", "year": 2026, "month": 11}
    )
    return [l["id"] for l in du_contrat(requete, contrat).execute().data]


def test_sans_contrat_le_bulletin_du_contrat_de_la_fiche():
    assert _du_mois(_base(), None) == ["nouveau"]


def test_avec_un_contrat_range_son_seul_bulletin():
    assert _du_mois(_base(), RANGE) == ["ancien"]


def test_le_conflit_d_ecriture_porte_le_contrat():
    assert CONFLIT_BULLETIN.split(",") == [
        "company_id",
        "employee_id",
        "year",
        "month",
        "contract_period_id",
    ]
