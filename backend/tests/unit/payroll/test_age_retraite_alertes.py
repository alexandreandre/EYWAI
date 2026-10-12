"""Âge du salarié au départ ou à la mise à la retraite : des alertes, pas de blocage.

Sources ouvertes le 11/10/2026 :
- BOSS, « Indemnités de rupture » (mis à jour le 26/06/2026), § 1540 : un départ
  volontaire à la retraite n'est possible « au plus tôt [qu']à l'âge auquel il
  est permis au salarié de liquider une telle pension » ; § 1590 : « Le salarié
  ayant atteint l'âge de 70 ans peut faire l'objet d'une mise à la retraite
  d'office » ; § 1600 : avant 70 ans, il faut l'âge du taux plein (1° de
  l'article L. 351-8 du code de la sécurité sociale) et « l'accord exprès du
  salarié » ; § 1610 : sinon, « la rupture du contrat de travail par
  l'employeur constitue un licenciement ».
- Code du travail, art. L1237-5 (en vigueur depuis le 26/10/2025) : avant l'âge
  du taux plein, l'employeur interroge le salarié par écrit ; en cas de refus,
  pas de mise à la retraite dans l'année ; « La même procédure est applicable
  chaque année jusqu'au soixante-neuvième anniversaire du salarié. »
- Code de la sécurité sociale, art. L161-17-2 et service-public F14043 : l'âge
  légal de départ selon la génération.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"
_SANS_ICCP = {"montant": 0.0, "description": "ICCP", "details": {}}


def _salarie(naissance: str | None) -> dict:
    return {
        "id": "emp-1",
        "hire_date": "1996-06-04",
        "date_naissance": naissance,
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 2500.0},
        "baremes": {"pss": {"annuel": 48060.0}},
    }


def _retraite(initiative: str) -> dict:
    return {
        "id": "exit-1",
        "exit_type": "depart_retraite",
        "exit_request_date": "2026-03-01",
        "last_working_day": "2026-06-30",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        "exit_notes": {"retirement_initiator": initiative},
    }


def _alertes(naissance: str | None, initiative: str) -> list[str]:
    dossier = calculer_indemnites_sortie(_salarie(naissance), _retraite(initiative), BaseEnMemoire({}))
    cle = "indemnite_mise_retraite" if initiative == "employer" else "indemnite_depart_retraite"
    return dossier[cle]["alertes"]


@patch(_ICCP, return_value=_SANS_ICCP)
def test_un_depart_volontaire_avant_l_age_legal_est_signale(_iccp):
    alertes = _alertes("1966-07-01", "employee")
    assert any("avant l'âge légal" in a and "63 ans et 3 mois" in a for a in alertes)

    assert not any("âge légal" in a for a in _alertes("1962-01-15", "employee"))


@patch(_ICCP, return_value=_SANS_ICCP)
def test_une_mise_a_la_retraite_avant_67_ans_serait_un_licenciement(_iccp):
    alertes = _alertes("1961-01-01", "employer")
    assert any("65 ans" in a and "67 ans" in a and "licenciement" in a for a in alertes)


@patch(_ICCP, return_value=_SANS_ICCP)
def test_une_mise_a_la_retraite_entre_67_et_70_ans_demande_l_accord_du_salarie(_iccp):
    alertes = _alertes("1958-01-01", "employer")
    assert any("68 ans" in a and "70 ans" in a and "accord" in a and "L1237-5" in a for a in alertes)


@patch(_ICCP, return_value=_SANS_ICCP)
def test_a_70_ans_la_mise_a_la_retraite_n_est_pas_signalee(_iccp):
    assert not any("ans" in a and "accord" in a for a in _alertes("1955-01-01", "employer"))


@patch(_ICCP, return_value=_SANS_ICCP)
def test_sans_date_de_naissance_l_age_n_est_pas_verifie_et_on_le_dit(_iccp):
    for initiative in ("employee", "employer"):
        assert any("Date de naissance" in a for a in _alertes(None, initiative))
