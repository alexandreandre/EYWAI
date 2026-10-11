"""[H2] Départ volontaire et mise à la retraite : l'indemnité légale.

Le dossier ne calculait aucune indemnité pour un départ à la retraite, et la
mise à la retraite par l'employeur n'était pas atteignable (DSN 038 jamais
émise). Rejeu d'un départ réel de juin 2026 (plus de 30 ans d'ancienneté) :
0 € dans Martine, quand le minimum légal est de deux mois de salaire.

Sources ouvertes le 11/10/2026 :
- Code du travail, art. L1237-9 (Légifrance, en vigueur depuis le 26/10/2025) :
  « Tout salarié quittant volontairement l'entreprise pour bénéficier d'une
  pension de vieillesse a droit à une indemnité de départ à la retraite. »
- Code du travail, art. D1237-1 : « au moins égal à : 1° Un demi-mois de
  salaire après dix ans d'ancienneté ; 2° Un mois de salaire après quinze ans
  d'ancienneté ; 3° Un mois et demi de salaire après vingt ans d'ancienneté ;
  4° Deux mois de salaire après trente ans d'ancienneté. »
- service-public.gouv.fr F13965 (vérifié le 01/01/2026) : salaire de référence
  le plus avantageux du 12e des 12 derniers mois ou du tiers des 3 derniers ;
  « L'indemnité de départ volontaire à la retraite est soumise à cotisations
  (de Sécurité sociale, à CSG et CRDS) […] Elle est imposable sur le revenu. »
- BOSS, « Indemnités de rupture » (mis à jour le 26/06/2026), § 1560 : « soumise
  aux cotisations de sécurité sociale ainsi qu'à la CSG et à la CRDS, pour
  l'intégralité de son montant » ; § 1630 à 1660 : mise à la retraite,
  indemnité au moins égale à l'indemnité légale de licenciement, exonérée dans
  des limites (5 PASS), contribution patronale de 40 %.
- Code du travail, art. L1237-7 (en vigueur depuis le 01/09/2023) : « une
  indemnité de mise à la retraite au moins égale à l'indemnité de licenciement
  prévue à l'article L. 1234-9. »
- Cahier technique DSN 2026.1, S21.G00.62.002 : 038 mise à la retraite par
  l'employeur, 039 départ à la retraite à l'initiative du salarié ;
  S21.G00.52.001 : 005 indemnité légale de départ à la retraite, 003 de mise à
  la retraite.

Pas de barème conventionnel (décision d'Alexandre) : le minimum légal, et le
dossier dit qu'un montant conventionnel plus élevé n'a pas encore de champ.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.dsn_export.domain.evenements import bloc_fin_contrat, indemnites_de_rupture
from app.modules.employee_exits.schemas.requests import EmployeeExitCreate
from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from app.modules.payroll.engine.indemnites_sortie_brut import lignes_indemnites_sortie_soumises
from tests.unit.base_en_memoire import BaseEnMemoire
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"
_SANS_ICCP = {"montant": 0.0, "description": "ICCP", "details": {}}
_BAREMES = {"pss": {"annuel": 48060.0, "mensuel": 4005.0}}


def _salarie(hire_date: str) -> dict:
    return {
        "id": "emp-1",
        "hire_date": hire_date,
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 2500.0},
        "baremes": _BAREMES,
    }


def _bulletins(annee_fin: int, mois_fin: int, brut: float = 2766.54) -> BaseEnMemoire:
    """Douze bulletins mensuels jusqu'au mois précédant `mois_fin`."""
    lignes = []
    annee, mois = annee_fin, mois_fin
    for _ in range(12):
        mois -= 1
        if mois == 0:
            annee, mois = annee - 1, 12
        lignes.append(
            {
                "employee_id": "emp-1",
                "year": annee,
                "month": mois,
                "payslip_data": {
                    "salaire_brut": brut,
                    "calcul_du_brut": [{"libelle": "Salaire de base", "gain": brut}],
                },
            }
        )
    return BaseEnMemoire({"payslips": lignes})


def _depart_volontaire(**extra) -> dict:
    return {
        "id": "exit-1",
        "exit_type": "depart_retraite",
        "exit_request_date": "2026-05-31",
        "last_working_day": "2026-06-30",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        **extra,
    }


@pytest.mark.parametrize(
    "entree,mois_de_salaire",
    [
        ("2017-01-01", 0.0),  # 9 ans et demi : pas d'indemnité légale
        ("2014-01-01", 0.5),  # 12 ans
        ("2009-01-01", 1.0),  # 17 ans
        ("2001-01-01", 1.5),  # 25 ans
        ("1996-06-04", 2.0),  # plus de 30 ans
    ],
)
@patch(_ICCP, return_value=_SANS_ICCP)
def test_le_depart_volontaire_suit_le_bareme_de_d1237_1(_iccp, entree, mois_de_salaire):
    dossier = calculer_indemnites_sortie(_salarie(entree), _depart_volontaire(), _bulletins(2026, 6))

    indemnite = dossier["indemnite_depart_retraite"]
    assert indemnite["montant"] == round(2766.54 * mois_de_salaire, 2)
    assert dossier["total_gross_indemnities"] == indemnite["montant"]
    assert any("montant conventionnel" in a for a in indemnite["alertes"])


@patch(_ICCP, return_value=_SANS_ICCP)
def test_le_depart_volontaire_est_au_brut_soumis_a_cotisations_et_declare_en_005(_iccp):
    dossier = calculer_indemnites_sortie(_salarie("1996-06-04"), _depart_volontaire(), _bulletins(2026, 6))
    contexte = build_test_contexte(salaire_base=2500.0)
    contexte.exit_indemnities = dossier

    lignes = lignes_indemnites_sortie_soumises(contexte)
    assert ("Indemnité de départ à la retraite", 5533.08) in [(l["libelle"], l["gain"]) for l in lignes]
    assert indemnites_de_rupture({"calcul_du_brut": lignes}, sortie=True) == [("005", 5533.08, True)]


def _mise_a_la_retraite(**extra) -> dict:
    return {
        "id": "exit-2",
        "exit_type": "depart_retraite",
        "exit_notes": {"retirement_initiator": "employer"},
        "exit_request_date": "2026-03-01",
        "last_working_day": "2026-04-30",
        "notice_period_days": 60,
        "notice_end_date": "2026-04-30",
        "notice_indemnity_type": "executed",
        **extra,
    }


@patch(_ICCP, return_value=_SANS_ICCP)
def test_la_mise_a_la_retraite_vaut_au_moins_l_indemnite_legale_de_licenciement(_iccp):
    dossier = calculer_indemnites_sortie(_salarie("2006-01-01"), _mise_a_la_retraite(), _bulletins(2026, 3))

    indemnite = dossier["indemnite_mise_retraite"]
    # Du 01/01/2006 au 30/04/2026 : 244 mois ; 10 ans à 1/4, le reste à 1/3.
    attendu = round(2766.54 / 4 * 10 + 2766.54 / 3 * (244 / 12 - 10), 2)
    assert indemnite["montant"] == attendu
    regime = indemnite["regime_social"]
    assert regime["nature"] == "mise_retraite"
    assert regime["contribution_patronale"] == round(regime["exoneree_cotisations"] * 0.40, 2)
    assert "indemnite_depart_retraite" not in dossier


def test_la_dsn_declare_une_mise_a_la_retraite_en_038():
    salarie = {
        "sortie_dsn": {
            "exit_type": "depart_retraite",
            "exit_notes": {"retirement_initiator": "employer"},
            "last_working_day": "2026-04-30",
            "exit_request_date": "2026-03-01",
        }
    }
    bloc, _ = bloc_fin_contrat(salarie, date(2026, 4, 1), date(2026, 4, 30))
    assert bloc["S21.G00.62.002"] == "038"

    salarie["sortie_dsn"]["exit_notes"] = {}
    bloc, _ = bloc_fin_contrat(salarie, date(2026, 4, 1), date(2026, 4, 30))
    assert bloc["S21.G00.62.002"] == "039"


def test_l_ecran_dit_qui_prend_l_initiative_de_la_retraite():
    depart = EmployeeExitCreate(
        employee_id="emp-1",
        exit_type="depart_retraite",
        exit_request_date="2026-03-01",
        last_working_day="2026-04-30",
        retirement_initiator="employer",
    )
    assert depart.retirement_initiator == "employer"
