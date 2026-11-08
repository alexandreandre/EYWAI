"""Les cases corrigées à la relecture doivent arriver en base.

Constat du 21/09/2026 : `persist-timesheet` avec un `batch_id` commitait
l'aperçu du modèle tel quel — les corrections faites à l'écran étaient perdues.
"""

from unittest.mock import patch

import pytest

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee

SERVICE = "app.modules.schedules.application.timesheet_import.commit_service"


def _lot():
    return {
        "id": "b1",
        "company_id": "c1",
        "status": "previewed",
        "preview_json": AiCalendarProposalResponse(
            year=2026,
            month=7,
            source="test",
            employees=[
                AiEmployeeProposal(
                    raw_name="MARION",
                    employee_id="e-marion",
                    days=[AiDayEntry(jour=3, heures=7.5, type="travail", nature="reel")],
                    review_status="ok",
                    match_confidence="high",
                ),
                AiEmployeeProposal(
                    raw_name="MARION",  # même salariée sur un second fichier
                    employee_id="e-marion",
                    days=[AiDayEntry(jour=9, heures=7.5, type="travail", nature="reel")],
                    review_status="ok",
                    match_confidence="high",
                ),
                AiEmployeeProposal(
                    raw_name="HUGO",
                    employee_id="e-hugo",
                    days=[AiDayEntry(jour=3, heures=5.0, type="travail", nature="reel")],
                    review_status="ok",
                    match_confidence="high",
                ),
            ],
        ).model_dump(mode="json"),
        "summary_json": {},
    }


@patch(f"{SERVICE}.timesheet_import_repository")
def test_les_jours_relus_remplacent_ceux_du_modele_pour_le_salarie(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    mock_repo.get_batch.return_value = _lot()

    appliquer_revue_au_lot(
        "b1",
        company_id="c1",
        employees=[
            PersistTimesheetEmployee(
                employee_id="e-marion",
                days=[
                    AiDayEntry(jour=3, heures=5.0, type="travail", nature="reel"),
                    AiDayEntry(jour=9, heures=1.0, type="travail", nature="reel"),
                ],
            )
        ],
    )

    (batch_id, payload), _ = mock_repo.update_batch.call_args
    assert batch_id == "b1"
    employes = payload["preview_json"]["employees"]
    marion = [e for e in employes if e["employee_id"] == "e-marion"]
    # Une seule entrée porte les jours relus ; l'autre est vidée (fusion par salarié au commit).
    assert [d["heures"] for e in marion for d in e["days"]] == [5.0, 1.0]
    hugo = next(e for e in employes if e["employee_id"] == "e-hugo")
    assert hugo["days"][0]["heures"] == 5.0  # non relu : inchangé


@patch(f"{SERVICE}.timesheet_import_repository")
def test_un_salarie_relu_absent_du_lot_est_refuse(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    mock_repo.get_batch.return_value = _lot()

    with pytest.raises(ScheduleAppError) as exc:
        appliquer_revue_au_lot(
            "b1",
            company_id="c1",
            employees=[PersistTimesheetEmployee(employee_id="e-inconnu", days=[])],
        )
    assert exc.value.status_code == 400


@patch(f"{SERVICE}.timesheet_import_repository")
def test_sans_jours_relus_l_apercu_n_est_pas_touche(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    mock_repo.get_batch.return_value = _lot()

    appliquer_revue_au_lot("b1", company_id="c1", employees=[])

    mock_repo.update_batch.assert_not_called()


def _lot_avec_un_nom_non_reconnu():
    lot = _lot()
    lot["preview_json"]["employees"].append(
        AiEmployeeProposal(
            raw_name="YSOLDE RECETTE",
            employee_id=None,
            days=[AiDayEntry(jour=5, heures=7.0, type="travail", nature="reel")],
            review_status="warning",
            match_confidence="none",
        ).model_dump(mode="json")
    )
    lot["summary_json"] = {
        "multi_month": True,
        "month_groups": [
            {
                "year": 2026,
                "month": 7,
                "employees": [
                    {"raw_name": "YSOLDE RECETTE", "employee_id": None, "review_status": "warning",
                     "days": [{"jour": 5, "heures": 7.0, "type": "travail", "nature": "reel"}]},
                ],
            }
        ],
    }
    return lot


@patch(f"{SERVICE}.timesheet_import_repository")
def test_un_salarie_associe_a_la_main_est_rattache_a_sa_ligne_du_lot(mock_repo):
    """Constat du 06/10/2026 : « Associer… » puis Enregistrer renvoyait 400
    « Salarié(s) relu(s) absent(s) du lot » : la ligne du lot n'avait pas de salarié."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    mock_repo.get_batch.return_value = _lot_avec_un_nom_non_reconnu()

    appliquer_revue_au_lot(
        "b1",
        company_id="c1",
        employees=[
            PersistTimesheetEmployee(
                employee_id="e-ysolde",
                raw_name="YSOLDE RECETTE",
                days=[AiDayEntry(jour=5, heures=6.5, type="travail", nature="reel")],
            )
        ],
    )

    (_, payload), _ = mock_repo.update_batch.call_args
    ysolde = next(e for e in payload["preview_json"]["employees"] if e["raw_name"] == "YSOLDE RECETTE")
    assert ysolde["employee_id"] == "e-ysolde"
    assert ysolde["review_status"] == "ok"
    assert [d["heures"] for d in ysolde["days"]] == [6.5]
    groupe = payload["summary_json"]["month_groups"][0]["employees"][0]
    assert groupe["employee_id"] == "e-ysolde"
    assert groupe["review_status"] == "ok"


@patch(f"{SERVICE}.timesheet_import_repository")
def test_un_nom_lu_absent_du_lot_reste_refuse(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    mock_repo.get_batch.return_value = _lot_avec_un_nom_non_reconnu()

    with pytest.raises(ScheduleAppError) as exc:
        appliquer_revue_au_lot(
            "b1",
            company_id="c1",
            employees=[PersistTimesheetEmployee(employee_id="e-x", raw_name="AUTRE NOM", days=[])],
        )
    assert exc.value.status_code == 400


def _lot_sur_deux_mois():
    """Lot multi-mois : l'enregistrement lit `month_groups`, pas l'aperçu."""
    lot = {
        "id": "b2",
        "company_id": "c1",
        "status": "previewed",
        "preview_json": AiCalendarProposalResponse(
            year=2026,
            month=7,
            source="test",
            employees=[
                AiEmployeeProposal(
                    raw_name="MARION",
                    employee_id="e-marion",
                    days=[AiDayEntry(jour=3, heures=7.5, type="travail", nature="prevu", year=2026, month=7)],
                    review_status="ok",
                    match_confidence="high",
                ),
                AiEmployeeProposal(
                    raw_name="MARION",
                    employee_id="e-marion",
                    days=[AiDayEntry(jour=4, heures=7.5, type="travail", nature="prevu", year=2026, month=8)],
                    review_status="ok",
                    match_confidence="high",
                ),
            ],
        ).model_dump(mode="json"),
        "summary_json": {
            "multi_month": True,
            "month_groups": [
                {
                    "year": 2026,
                    "month": 7,
                    "employees": [
                        {
                            "employee_id": "e-marion",
                            "raw_name": "MARION",
                            "review_status": "ok",
                            "days": [
                                {
                                    "jour": 3,
                                    "heures": 7.5,
                                    "type": "travail",
                                    "nature": "prevu",
                                    "shift_code": "M1",
                                }
                            ],
                        }
                    ],
                },
                {
                    "year": 2026,
                    "month": 8,
                    "employees": [
                        {
                            "employee_id": "e-marion",
                            "raw_name": "MARION",
                            "review_status": "ok",
                            "days": [
                                {"jour": 4, "heures": 7.5, "type": "travail", "nature": "prevu"}
                            ],
                        }
                    ],
                },
            ],
        },
    }
    return lot


def _jours_des_groupes(payload):
    return {
        (g["month"], d["jour"]): d
        for g in payload["summary_json"]["month_groups"]
        for e in g["employees"]
        for d in e["days"]
    }


@patch(f"{SERVICE}.timesheet_import_repository")
def test_lot_sur_deux_mois_les_jours_relus_vont_dans_leur_mois(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    mock_repo.get_batch.return_value = _lot_sur_deux_mois()

    appliquer_revue_au_lot(
        "b2",
        company_id="c1",
        employees=[
            PersistTimesheetEmployee(
                employee_id="e-marion",
                days=[AiDayEntry(jour=3, heures=6.0, type="travail", nature="prevu", year=2026, month=7)],
            ),
            PersistTimesheetEmployee(
                employee_id="e-marion",
                days=[AiDayEntry(jour=4, heures=4.0, type="conge", nature="prevu", year=2026, month=8)],
            ),
        ],
    )

    (_, payload), _ = mock_repo.update_batch.call_args
    jours = _jours_des_groupes(payload)
    assert jours[(7, 3)]["heures"] == 6.0
    assert jours[(8, 4)]["heures"] == 4.0
    assert jours[(8, 4)]["type"] == "conge"
    # La note du serveur survit, et les mois restent portés par le groupe.
    assert jours[(7, 3)]["shift_code"] == "M1"
    assert jours[(7, 3)].get("month") is None


@patch(f"{SERVICE}.timesheet_import_repository")
def test_lot_sur_deux_mois_un_mois_non_relu_garde_ses_jours(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    mock_repo.get_batch.return_value = _lot_sur_deux_mois()

    appliquer_revue_au_lot(
        "b2",
        company_id="c1",
        employees=[
            PersistTimesheetEmployee(
                employee_id="e-marion",
                days=[AiDayEntry(jour=3, heures=6.0, type="travail", nature="prevu", year=2026, month=7)],
            ),
        ],
    )

    (_, payload), _ = mock_repo.update_batch.call_args
    jours = _jours_des_groupes(payload)
    assert jours[(7, 3)]["heures"] == 6.0
    assert jours[(8, 4)]["heures"] == 7.5


@patch(f"{SERVICE}.timesheet_import_repository")
def test_lot_tableur_les_jours_sans_mois_sont_ceux_du_mois_affiche(mock_repo):
    """Tableur sur plusieurs mois : l'aperçu ne montre que le mois d'ancrage."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    lot = _lot_sur_deux_mois()
    lot["preview_json"]["employees"].pop()
    mock_repo.get_batch.return_value = lot

    appliquer_revue_au_lot(
        "b2",
        company_id="c1",
        employees=[
            PersistTimesheetEmployee(
                employee_id="e-marion",
                days=[AiDayEntry(jour=3, heures=5.0, type="travail", nature="prevu")],
            ),
        ],
    )

    (_, payload), _ = mock_repo.update_batch.call_args
    jours = _jours_des_groupes(payload)
    assert jours[(7, 3)]["heures"] == 5.0
    assert jours[(8, 4)]["heures"] == 7.5


@patch(f"{SERVICE}.timesheet_import_repository")
def test_lot_sur_deux_mois_des_lignes_sans_mois_sont_refusees_avec_une_phrase(mock_repo):
    """Aperçu préparé avant le correctif : on ne devine pas le mois d'une ligne."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    mock_repo.get_batch.return_value = _lot_sur_deux_mois()

    with pytest.raises(ScheduleAppError) as exc:
        appliquer_revue_au_lot(
            "b2",
            company_id="c1",
            employees=[
                PersistTimesheetEmployee(
                    employee_id="e-marion",
                    days=[AiDayEntry(jour=3, heures=6.0, type="travail", nature="prevu")],
                ),
                PersistTimesheetEmployee(
                    employee_id="e-marion",
                    days=[AiDayEntry(jour=4, heures=4.0, type="travail", nature="prevu")],
                ),
            ],
        )
    assert exc.value.status_code == 409
    assert "relancez" in exc.value.message.lower()
    mock_repo.update_batch.assert_not_called()


@patch(f"{SERVICE}.timesheet_import_repository")
def test_lot_sur_deux_mois_un_jour_d_un_mois_absent_du_lot_est_refuse(mock_repo):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    mock_repo.get_batch.return_value = _lot_sur_deux_mois()

    with pytest.raises(ScheduleAppError) as exc:
        appliquer_revue_au_lot(
            "b2",
            company_id="c1",
            employees=[
                PersistTimesheetEmployee(
                    employee_id="e-marion",
                    days=[AiDayEntry(jour=2, heures=6.0, type="travail", nature="prevu", year=2026, month=9)],
                ),
            ],
        )
    assert exc.value.status_code == 400
    mock_repo.update_batch.assert_not_called()


def test_l_apercu_d_un_lot_sur_plusieurs_mois_porte_le_mois_de_chaque_jour():
    from app.modules.schedules.application.planning_import.service import (
        build_proposal_from_month_groups,
    )

    proposition = build_proposal_from_month_groups(
        _lot_sur_deux_mois()["summary_json"]["month_groups"],
        year=2026,
        month=7,
        filename="calendrier.xlsx",
    )

    assert [(d.year, d.month, d.jour) for e in proposition.employees for d in e.days] == [
        (2026, 7, 3),
        (2026, 8, 4),
    ]
