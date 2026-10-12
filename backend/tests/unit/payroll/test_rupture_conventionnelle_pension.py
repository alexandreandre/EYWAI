"""Rupture conventionnelle d'un salarié qui peut liquider une pension de retraite.

BOSS, « Indemnités de rupture » (mis à jour le 26/06/2026, ouvert le 11/10/2026) :
- § 940 : « Lorsque le salarié est en droit de bénéficier d'une pension de
  retraite d'un régime légalement obligatoire, l'indemnité de rupture
  conventionnelle individuelle est soumise à l'impôt sur le revenu dès le
  premier euro. »
- § 890 : la loi de financement rectificative de la sécurité sociale pour 2023
  « a harmonisé le régime social des indemnités de rupture conventionnelle
  individuelle et la distinction du régime social applicable en fonction du
  droit de bénéficier ou non d'une pension de retraite d'un régime légalement
  obligatoire a été supprimée. »
- § 60 : est exclue de l'assiette des cotisations, dans la limite de 2 PASS,
  « concernant les agents et les salariés en droit de bénéficier d'une pension
  de retraite d'un régime légalement obligatoire, y compris lorsqu'elles sont
  soumises à l'impôt sur le revenu, la fraction des indemnités de rupture
  conventionnelle individuelle qui n'excède pas l'un des montants prévus aux a)
  et b) du 6° de l'article 80 duodecies du code général des impôts. »

Donc : imposable dès le premier euro ; cotisations, CSG/CRDS et contribution
patronale de 40 % inchangées. (La consigne disait « soumise dès le premier
euro » : la source ne le dit que de l'impôt sur le revenu.)

Âge légal de départ par génération : Code de la sécurité sociale, art.
L161-17-2 (Légifrance, rédaction issue de la loi n° 2025-1403 du 30/12/2025,
art. 105, ouvert le 11/10/2026) ; service-public.gouv.fr F14043 (vérifié le
14/08/2026, ouvert le 11/10/2026) : 62 ans et 9 mois pour les assurés nés entre
le 1er janvier 1963 et le 31 mars 1965, 63 ans d'avril à décembre 1965, 63 ans
et 3 mois en 1966, 63 ans et 6 mois en 1967, 63 ans et 9 mois en 1968, 64 ans à
partir de 1969 ; 62 ans et 3 mois de septembre à décembre 1961, 62 ans et 6
mois en 1962.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application import commands
from app.modules.employee_exits.schemas.requests import EmployeeExitCreate, EmployeeExitUpdate
from app.modules.payroll.engine.age_retraite import age_legal_de_depart, a_atteint_l_age_legal
from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from app.modules.payroll.engine.regime_indemnites_rupture import ventiler_indemnite_de_rupture
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

PASS_2026 = 48060.0
_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"


@pytest.mark.parametrize(
    "naissance,annees,mois",
    [
        ("1961-10-15", 62, 3),
        ("1962-04-01", 62, 6),
        ("1963-05-10", 62, 9),
        ("1965-03-31", 62, 9),
        ("1965-04-01", 63, 0),
        ("1966-07-01", 63, 3),
        ("1967-07-01", 63, 6),
        ("1968-07-01", 63, 9),
        ("1969-01-01", 64, 0),
        ("1985-06-30", 64, 0),
    ],
)
def test_l_age_legal_suit_la_generation(naissance, annees, mois):
    age = age_legal_de_depart(date.fromisoformat(naissance))
    assert (age.annees, age.mois) == (annees, mois)


def test_l_age_legal_atteint_se_compte_au_jour_pres():
    naissance = date(1963, 5, 10)
    assert not a_atteint_l_age_legal(naissance, date(2026, 2, 9))
    assert a_atteint_l_age_legal(naissance, date(2026, 2, 10))


def test_pension_liquidable_imposable_des_le_premier_euro_regime_social_inchange():
    sans = ventiler_indemnite_de_rupture(
        "rupture_conventionnelle", 30000.0, minimum=8000.0, remuneration_annuelle_n_1=30000.0,
        pass_annuel=PASS_2026,
    )
    avec = ventiler_indemnite_de_rupture(
        "rupture_conventionnelle", 30000.0, minimum=8000.0, remuneration_annuelle_n_1=30000.0,
        pass_annuel=PASS_2026, pension_de_retraite=True,
    )
    assert sans.imposable == 0.0
    assert avec.imposable == 30000.0
    assert avec.exoneree_impot == 0.0
    for champ in (
        "exoneree_cotisations",
        "soumise_cotisations",
        "exoneree_csg",
        "assiette_csg_seule",
        "contribution_patronale",
    ):
        assert getattr(avec, champ) == getattr(sans, champ), champ
    assert avec.contribution_patronale == 12000.0
    assert "imposable dès le premier euro" in avec.mention()


def _salarie(naissance: str | None) -> dict:
    return {
        "id": "emp-1",
        "hire_date": "2010-01-01",
        "date_naissance": naissance,
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 2500.0},
        "baremes": {"pss": {"annuel": PASS_2026, "mensuel": 4005.0}},
    }


def _rupture(**notes) -> dict:
    return {
        "id": "exit-1",
        "exit_type": "rupture_conventionnelle",
        "exit_request_date": "2026-09-15",
        "last_working_day": "2026-10-31",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        "montant_negocie": 30000.0,
        "exit_notes": notes,
    }


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_le_dossier_alerte_quand_le_salarie_a_l_age_legal(_iccp):
    dossier = calculer_indemnites_sortie(_salarie("1962-03-15"), _rupture(), BaseEnMemoire({}))
    alertes = dossier["indemnite_rupture_conventionnelle"]["alertes"]
    assert any("62 ans et 6 mois" in a and "imposable dès le premier euro" in a for a in alertes)

    dossier = calculer_indemnites_sortie(_salarie("1980-03-15"), _rupture(), BaseEnMemoire({}))
    alertes = dossier["indemnite_rupture_conventionnelle"]["alertes"]
    assert not any("âge légal" in a for a in alertes)


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_la_case_cochee_rend_l_indemnite_imposable(_iccp):
    dossier = calculer_indemnites_sortie(
        _salarie("1962-03-15"), _rupture(pension_liquidable=True), BaseEnMemoire({})
    )
    rc = dossier["indemnite_rupture_conventionnelle"]
    assert rc["regime_social"]["pension_de_retraite"] is True
    assert rc["regime_social"]["imposable"] == 30000.0
    assert not any("cochez" in a for a in rc["alertes"])


def test_la_case_se_saisit_a_la_creation_et_dans_l_onglet():
    depart = EmployeeExitCreate(
        employee_id="emp-1",
        exit_type="rupture_conventionnelle",
        exit_request_date="2026-09-15",
        last_working_day="2026-10-31",
        pension_liquidable=True,
    )
    assert depart.pension_liquidable is True
    assert EmployeeExitUpdate(pension_liquidable=False).pension_liquidable is False
    assert commands.notes_du_dossier_a_la_creation("rupture_conventionnelle", depart.model_dump()) == {
        "pension_liquidable": True
    }
    assert commands.notes_du_dossier_a_la_creation("demission", {"pension_liquidable": True}) is None

    existant = {
        "id": "exit-1",
        "employee_id": "emp-1",
        "exit_type": "rupture_conventionnelle",
        "status": "rupture_en_negociation",
        "exit_notes": {},
    }
    with patch.object(commands, "EmployeeExitRepository") as depot, patch.object(
        commands, "get_employee_full", return_value={"id": "emp-1"}
    ), patch.object(commands, "get_indemnity_calculator") as calculateur:
        depot.return_value.get_by_id.return_value = existant
        depot.return_value.update.side_effect = lambda _id, _co, maj: {**existant, **maj}
        calculateur.return_value.calculate.return_value = {"indemnite_conges": {"jours_restants": 0}}
        maj = commands.update_employee_exit(
            "exit-1", "co", {"pension_liquidable": True}, supabase_client=MagicMock()
        )
    assert maj["exit_notes"] == {"pension_liquidable": True}
    assert "calculated_indemnities" in maj
