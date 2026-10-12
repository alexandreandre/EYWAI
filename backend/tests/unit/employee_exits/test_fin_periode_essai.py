"""[H13] Fin de période d'essai : initiative, délai de prévenance, indemnité, suivi.

Code du travail (Légifrance, ouverts le 11/10/2026) :
- art. L1221-25 (version en vigueur depuis le 28/06/2014) : « Lorsqu'il est mis
  fin, par l'employeur, au contrat en cours ou au terme de la période d'essai
  [...] le salarié est prévenu dans un délai qui ne peut être inférieur à :
  1° Vingt-quatre heures en deçà de huit jours de présence ; 2° Quarante-huit
  heures entre huit jours et un mois de présence ; 3° Deux semaines après un
  mois de présence ; 4° Un mois après trois mois de présence. La période
  d'essai, renouvellement inclus, ne peut être prolongée du fait de la durée du
  délai de prévenance. Lorsque le délai de prévenance n'a pas été respecté, son
  inexécution ouvre droit pour le salarié, sauf s'il a commis une faute grave,
  à une indemnité compensatrice. Cette indemnité est égale au montant des
  salaires et avantages que le salarié aurait perçus s'il avait accompli son
  travail jusqu'à l'expiration du délai de prévenance, indemnité compensatrice
  de congés payés comprise. »
- art. L1221-26 (version en vigueur depuis le 27/06/2008) : « Lorsqu'il est mis
  fin à la période d'essai par le salarié, celui-ci respecte un délai de
  prévenance de quarante-huit heures. Ce délai est ramené à vingt-quatre heures
  si la durée de présence du salarié dans l'entreprise est inférieure à huit
  jours. »
- Cahier technique DSN 2026.1 (S21.G00.62.002) : 034 fin de période d'essai à
  l'initiative de l'employeur, 035 à l'initiative du salarié ; S21.G00.52.001,
  017 : « Dommages et intérêts dus [...] à une rupture de période d'essai
  (délai de prévenance) ».

Martine ne saisissait pas qui rompait, ne calculait aucun délai, ne versait
l'indemnité qu'à travers le préavis et ne passait jamais la période d'essai au
statut « rompue ».

La présence se compte en jours civils, du jour d'entrée au jour de la
notification compris ; un mois de présence est atteint le quantième du mois
suivant moins un jour.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.dsn_export.domain.evenements import bloc_fin_contrat, indemnites_de_rupture
from app.modules.employee_exits.application import commands
from app.modules.employee_exits.domain.delai_prevenance import delai_de_prevenance
from app.modules.employee_exits.schemas.requests import EmployeeExitCreate
from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from app.modules.payroll.engine.indemnites_sortie_brut import lignes_indemnites_sortie_soumises
from tests.unit.base_en_memoire import BaseEnMemoire
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "entree,notification,jours,libelle,article",
    [
        (date(2026, 10, 1), date(2026, 10, 5), 1, "24 heures", "L1221-25, 1°"),
        (date(2026, 10, 1), date(2026, 10, 8), 2, "48 heures", "L1221-25, 2°"),
        (date(2026, 9, 1), date(2026, 9, 30), 14, "2 semaines", "L1221-25, 3°"),
        (date(2026, 7, 1), date(2026, 9, 30), 30, "1 mois", "L1221-25, 4°"),
    ],
)
def test_le_delai_de_l_employeur_suit_le_temps_de_presence(entree, notification, jours, libelle, article):
    delai = delai_de_prevenance("employer", entree, notification)
    assert (delai.jours, delai.libelle, delai.article) == (jours, libelle, article)


@pytest.mark.parametrize(
    "notification,jours,libelle",
    [(date(2026, 10, 7), 1, "24 heures"), (date(2026, 10, 8), 2, "48 heures"), (date(2027, 1, 15), 2, "48 heures")],
)
def test_le_delai_du_salarie_est_de_48_heures_ou_24_sous_huit_jours(notification, jours, libelle):
    delai = delai_de_prevenance("employee", date(2026, 10, 1), notification)
    assert (delai.jours, delai.libelle, delai.article) == (jours, libelle, "L1221-26")


def test_les_jours_non_respectes_vont_jusqu_a_l_expiration_du_delai():
    delai = delai_de_prevenance("employer", date(2026, 6, 1), date(2026, 10, 1))
    assert delai.fin == date(2026, 11, 1)
    assert delai.jours_accordes(date(2026, 10, 10)) == 9
    assert delai.jours_non_respectes(date(2026, 10, 10)) == 22
    assert delai.jours_non_respectes(date(2026, 11, 1)) == 0


def _salarie() -> dict:
    return {
        "id": "emp-1",
        "hire_date": "2026-06-01",
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 3000.0},
        "duree_hebdomadaire": 35,
        "baremes": {"pss": {"annuel": 48060.0}},
    }


def _essai(initiative: str | None, dernier_jour: str = "2026-10-10") -> dict:
    return {
        "id": "exit-1",
        "exit_type": "fin_periode_essai",
        "exit_request_date": "2026-10-01",
        "last_working_day": dernier_jour,
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        "exit_notes": {"probation_ended_by": initiative} if initiative else {},
    }


_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_l_employeur_qui_ne_respecte_pas_le_delai_doit_l_indemnite(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _essai("employer"), BaseEnMemoire({}))

    bloc = dossier["indemnite_delai_prevenance"]
    assert bloc["montant"] == 2200.0  # 3 000 € / 30 × 22 jours non respectés
    assert bloc["jours_requis"] == 31
    assert bloc["jours_accordes"] == 9
    assert bloc["respecte"] is False
    assert bloc["conges_du_preavis"]
    assert "L1221-25" in bloc["calcul"]
    assert dossier["total_gross_indemnities"] == 2200.0

    contexte = build_test_contexte(salaire_base=3000.0)
    contexte.exit_indemnities = dossier
    lignes = lignes_indemnites_sortie_soumises(contexte)
    assert ("Indemnité compensatrice de délai de prévenance", 2200.0) in [(l["libelle"], l["gain"]) for l in lignes]
    assert indemnites_de_rupture({"calcul_du_brut": lignes}, sortie=True) == [("017", 2200.0, True)]


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_le_salarie_qui_rompt_ne_recoit_pas_d_indemnite_de_prevenance(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _essai("employee"), BaseEnMemoire({}))

    bloc = dossier["indemnite_delai_prevenance"]
    assert bloc["montant"] == 0.0
    assert bloc["jours_requis"] == 2
    assert bloc["respecte"] is True


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_sans_initiative_saisie_le_dossier_le_dit(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _essai(None), BaseEnMemoire({}))
    assert any("initiative" in a for a in dossier["indemnite_delai_prevenance"]["alertes"])


def test_la_dsn_declare_la_rupture_par_le_salarie_en_035():
    salarie = {
        "sortie_dsn": {
            "exit_type": "fin_periode_essai",
            "exit_notes": {"probation_ended_by": "employee"},
            "last_working_day": "2026-10-10",
            "exit_request_date": "2026-10-01",
        }
    }
    bloc, _ = bloc_fin_contrat(salarie, date(2026, 10, 1), date(2026, 10, 31))
    assert bloc["S21.G00.62.002"] == "035"

    salarie["sortie_dsn"]["exit_notes"] = {"probation_ended_by": "employer"}
    bloc, _ = bloc_fin_contrat(salarie, date(2026, 10, 1), date(2026, 10, 31))
    assert bloc["S21.G00.62.002"] == "034"


def _creer(base: BaseEnMemoire, **extra) -> dict:
    with patch.object(
        commands,
        "get_employee_by_id",
        return_value={"company_id": "co", "employment_status": "actif", "first_name": "A", "last_name": "B"},
    ), patch.object(commands, "exit_block_reason", return_value=None), patch.object(
        commands, "EmployeeExitRepository"
    ) as depot, patch.object(commands, "update_employee_employment_status"), patch.object(
        commands, "create_default_checklist_sync"
    ), patch.object(commands, "_run_post_create_indemnities_and_docs"):
        depot.return_value.create.side_effect = lambda ligne: {**ligne, "id": "exit-1"}
        return commands.create_employee_exit(
            {
                "employee_id": "emp-1",
                "exit_type": "fin_periode_essai",
                "exit_request_date": "2026-10-01",
                "last_working_day": "2026-10-10",
                "notice_period_days": 0,
                "notice_indemnity_type": "not_applicable",
                **extra,
            },
            "co",
            "user-1",
            supabase_client=base,
        )


def test_la_creation_range_l_initiative_et_rompt_la_periode_d_essai():
    assert EmployeeExitCreate(
        employee_id="emp-1",
        exit_type="fin_periode_essai",
        exit_request_date="2026-10-01",
        last_working_day="2026-10-10",
        probation_ended_by="employer",
    ).probation_ended_by == "employer"

    base = BaseEnMemoire(
        {
            "trial_periods": [
                {"id": "tp-1", "employee_id": "emp-1", "status": "en_cours", "end_date": "2026-11-30"},
            ]
        }
    )
    cree = _creer(base, probation_ended_by="employer")

    assert cree["exit_notes"]["probation_ended_by"] == "employer"
    assert cree["exit_notes"]["trial_period_id"] == "tp-1"
    assert base.ligne("trial_periods", id="tp-1")["status"] == "rompue"


def test_supprimer_le_depart_rend_la_periode_d_essai_en_cours():
    base = BaseEnMemoire(
        {"trial_periods": [{"id": "tp-1", "employee_id": "emp-1", "status": "rompue", "end_date": "2026-11-30"}]}
    )
    existant = {
        "id": "exit-1",
        "employee_id": "emp-1",
        "exit_type": "fin_periode_essai",
        "exit_notes": {"probation_ended_by": "employer", "trial_period_id": "tp-1"},
    }
    with patch.object(commands, "EmployeeExitRepository") as depot, patch.object(
        commands, "get_exit_documents_storage_paths", return_value=[]
    ), patch.object(commands, "update_employee_employment_status"):
        depot.return_value.get_by_id.return_value = existant
        commands.delete_employee_exit("exit-1", "co", supabase_client=base)

    assert base.ligne("trial_periods", id="tp-1")["status"] == "en_cours"
