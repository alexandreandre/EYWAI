"""Un mois de l'ancien contrat garde son indemnité de congés après « Nouveau contrat ».

Tournage H.5 du 20/10/2026 : Nicolas, CDD du 01/07/2026 au 15/10/2026 à
1 950 €, embauché en CDI au 01/11/2026. Régénérer son bulletin d'octobre (le
dernier du CDD) perdait « Indemnité compensatrice de congés payés (CDD) » :
brut 1 673,98 € au lieu de 2 483,98 €. Le bulletin se calcule bien sur la fiche
rangée du CDD (`fiche_du_mois`), mais les compteurs de congés partaient de la
date d'embauche ACTUELLE de la fiche, celle du CDI (01/11) : 0 jour acquis en
octobre, donc 0 € d'indemnité.

Les compteurs d'un mois partent du début du contrat de ce mois et s'arrêtent à
sa fin. Les lectures en base sont doublées ; le calcul des congés, des
périodes et du brut est le vrai.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.modules.absences.application import queries as q
from app.modules.employees.application.contrat_du_mois import lecteur_contrats
from app.modules.payroll.documents import payslip_run_forfait, payslip_run_heures
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

EMP = "emp-nicolas"
#: Le CDD rangé par « Nouveau contrat », avec la fiche qu'il avait.
CDD_RANGE = {
    "id": "periode-cdd",
    "employee_id": EMP,
    "contract_type": "CDD",
    "date_debut": "2026-07-01",
    "date_fin": "2026-10-15",
    "fiche": {
        "hire_date": "2026-07-01",
        "contract_type": "CDD",
        "contract_end_date": "2026-10-15",
        "duree_hebdomadaire": 35,
    },
}


@pytest.fixture
def fiche_en_cdi(monkeypatch):
    """La fiche porte le CDI du 01/11/2026, sans fin ni départ en cours ; le
    CDD est rangé dans les contrats passés."""
    monkeypatch.setattr(q, "get_employee_hire_date", lambda _id: "2026-11-01")
    monkeypatch.setattr(q, "_date_de_sortie", lambda _id: None)
    monkeypatch.setattr(q, "_reprise_posterieure_au_bulletin", lambda *_a: False)
    monkeypatch.setattr(q.absence_repository, "list_validated_for_employees", lambda _ids: [])
    monkeypatch.setattr(q, "get_repos_credits_by_employee_year", lambda *_a: {})
    monkeypatch.setattr(q, "_leave_context", lambda *_a: (None, None, 0, None))
    monkeypatch.setattr(q, "_cp_balance_extras", lambda *_a: {})
    monkeypatch.setattr(q, "_hours_per_rest_day_for_employee", lambda _id: 7.0)
    monkeypatch.setattr(q, "_get_employee_company_id", lambda _id: None)
    monkeypatch.setattr(
        lecteur_contrats,
        "contrat_passe_du_mois",
        lambda employee_id, year, month: CDD_RANGE if (year, month) <= (2026, 10) else None,
    )


def _contexte_du_cdd():
    """La fiche du mois : celle du CDD rangé (ce que rend `fiche_du_mois`)."""
    return build_test_contexte(
        salaire_base=1950.0,
        type_contrat="CDD",
        date_entree="2026-07-01",
        date_fin_contrat="2026-10-15",
        cumuls={"brut_total": 5850.0},
    )


def _planning_d_octobre():
    jours, d = [], date(2026, 10, 1)
    while d.month == 10:
        ouvre = d.weekday() < 5
        jours.append(
            {
                "annee": 2026,
                "mois": 10,
                "jour": d.day,
                "type": "travail" if ouvre else "weekend",
                "heures_prevues": 7.0 if ouvre else 0.0,
            }
        )
        d += timedelta(days=1)
    return jours


def test_les_compteurs_d_octobre_partent_du_debut_du_cdd_range(fiche_en_cdi):
    compteurs = q.get_absence_balances_for_payslip(EMP, 2026, 10)
    assert compteurs is not None
    # Du 01/07 au 15/10 : 3,5 mois à 2,5 jours, arrondis à 9 ; rien après la fin du CDD.
    assert compteurs["conges_payes"]["acquis"] == pytest.approx(9.0)
    assert compteurs["conges_payes"]["solde"] == pytest.approx(9.0)
    assert compteurs["date_reference"] == "15/10/2026"


def test_le_mois_du_nouveau_contrat_part_de_sa_propre_date_d_entree(fiche_en_cdi):
    compteurs = q.get_absence_balances_for_payslip(EMP, 2026, 11)
    # Garde : un mois du CDI ne lit pas le contrat rangé (2,5 jours, arrondis à 3).
    assert compteurs["conges_payes"]["acquis"] == pytest.approx(3.0)
    assert compteurs["date_reference"] == "30/11/2026"


def test_h5_le_bulletin_d_octobre_garde_son_indemnite_de_conges(fiche_en_cdi):
    ctx = _contexte_du_cdd()
    ctx.cp_fin_de_contrat = payslip_run_heures.cp_fin_de_contrat(ctx, EMP, 2026, 10)
    res = calculer_salaire_brut(
        ctx, [], date(2026, 10, 1), date(2026, 10, 31), [], jours_prevus=_planning_d_octobre()
    )
    gains = {l["libelle"]: l["gain"] for l in res["lignes_composants_brut"] if l.get("gain")}
    assert gains["Salaire de base"] == pytest.approx(989.98, abs=0.005)
    assert gains["Prime de précarité (CDD)"] == pytest.approx(684.00, abs=0.005)
    assert gains["Indemnité compensatrice de congés payés (CDD)"] == pytest.approx(810.00, abs=0.005)
    assert ctx.detail_iccp_fin_contrat["periodes"][0]["methode"] == "maintien"
    assert sum(gains.values()) == pytest.approx(2483.98, abs=0.005)


def test_au_forfait_le_depart_du_mois_lit_aussi_les_compteurs_du_cdd_range(fiche_en_cdi):
    ctx = _contexte_du_cdd()
    with patch.object(payslip_run_heures, "resolve_exit_state_for_payslip", return_value=(None, False)):
        payslip_run_forfait.poser_le_depart_du_forfait(ctx, EMP, 2026, 10)
    assert ctx.cp_fin_de_contrat["periode_en_cours"]["restants"] == pytest.approx(9.0)
    assert ctx.cp_fin_de_contrat["periode_en_cours"]["droits"] == pytest.approx(9.0)
