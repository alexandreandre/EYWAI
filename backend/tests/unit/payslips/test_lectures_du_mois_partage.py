"""Novembre a deux bulletins : chaque lecture « du bulletin du mois » rend celui
du contrat de la fiche, sauf le bulletin de sortie, qui rend celui du contrat
sorti (D3, spécification 2026-10-31-deux-contrats-meme-mois-design.md).

Le CDD finit le 10/11 (bulletin rangé, `contract_period_id` rempli), le nouveau
contrat commence le 17/11 (clé nulle).
"""

from __future__ import annotations

import pytest

from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

SAL, SOC, RANGE = "emp-1", "co-1", "periode-1"


def _bulletin(id_: str, entree: str, brut: float, contrat: str | None = None, mois: int = 11) -> dict:
    return {
        "id": id_,
        "company_id": SOC,
        "employee_id": SAL,
        "year": 2026,
        "month": mois,
        "status": "valide",
        "contract_period_id": contrat,
        "pdf_storage_path": f"chemin/{id_}.pdf",
        "payslip_data": {
            "salaire_brut": brut,
            "en_tete": {"salarie": {"date_entree": entree}},
            "cumuls": {"brut_total": brut},
        },
    }


@pytest.fixture
def base(monkeypatch):
    b = BaseEnMemoire(
        {
            "payslips": [
                _bulletin("ancien", "2026-07-01", 700.0, RANGE),
                _bulletin("nouveau", "2026-11-17", 900.0),
            ],
            "employee_schedules": [
                {"id": "planning-11", "employee_id": SAL, "year": 2026, "month": 11, "cumuls": {"brut_total": 900.0}}
            ],
        }
    )
    b.brancher(monkeypatch)
    return b


def test_le_bulletin_du_mois_est_celui_du_contrat_de_la_fiche(base):
    from app.modules.payslips.infrastructure.queries import get_payslip_data_du_mois

    assert get_payslip_data_du_mois(SAL, 2026, 11)["salaire_brut"] == 900.0


def test_le_mois_suivant_repart_du_contrat_de_la_fiche(base):
    from app.modules.payslips.application.suite_du_bulletin import _lire_bulletin_du_mois

    assert _lire_bulletin_du_mois(SAL, 2026, 11)["payslip_data"]["salaire_brut"] == 900.0


def test_l_empreinte_lit_le_bulletin_du_contrat_de_la_fiche(base):
    from app.modules.payroll.infrastructure.empreinte_entrees_queries import lire_bulletin_enregistre

    assert lire_bulletin_enregistre(SAL, 2026, 11)["id"] == "nouveau"


def test_le_bulletin_de_sortie_est_celui_du_contrat_sorti(base):
    from app.core import database
    from app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie import (
        bulletin_du_mois_de_sortie,
    )

    donnees = bulletin_du_mois_de_sortie(SAL, {"last_working_day": "2026-11-10"}, database.supabase)
    assert donnees["salaire_brut"] == 700.0


def test_le_bulletin_de_sortie_avant_le_nouveau_contrat(monkeypatch):
    """Avant « Nouveau contrat », le seul bulletin du mois est celui de la sortie."""
    from app.core import database
    from app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie import (
        bulletin_du_mois_de_sortie,
    )

    BaseEnMemoire({"payslips": [_bulletin("ancien", "2026-07-01", 700.0)]}).brancher(monkeypatch)
    donnees = bulletin_du_mois_de_sortie(SAL, {"last_working_day": "2026-11-10"}, database.supabase)
    assert donnees["salaire_brut"] == 700.0


def test_supprimer_le_bulletin_du_contrat_range_garde_les_cumuls_du_mois(base):
    from app.modules.payslips.infrastructure.repository import PayslipRepository

    PayslipRepository().delete("ancien")
    assert base.ligne("employee_schedules", id="planning-11")["cumuls"] == {"brut_total": 900.0}


def test_supprimer_le_bulletin_du_contrat_de_la_fiche_vide_les_cumuls_du_mois(base):
    from app.modules.payslips.infrastructure.repository import PayslipRepository

    PayslipRepository().delete("nouveau")
    assert base.ligne("employee_schedules", id="planning-11")["cumuls"] is None


def test_le_repos_compensateur_lit_un_bulletin_par_mois(base):
    from app.modules.repos_compensateur.infrastructure.providers import (
        get_bulletins_par_mois_par_employe,
    )

    assert get_bulletins_par_mois_par_employe(SOC, 2026, [SAL])[SAL][11]["salaire_brut"] == 900.0
