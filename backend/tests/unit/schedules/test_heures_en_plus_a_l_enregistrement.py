"""Heures en plus à valider : notées à l'aperçu, créées à l'enregistrement.

Constat du 04/11/2026 chez LEWIS : analyser un tableur de badgeuse créait déjà
les revues d'heures en plus « en attente » (30 pour un aperçu), même quand la
RH repartait par « Retour » sans rien enregistrer. L'aperçu note maintenant les
heures en plus sur le jour ; la revue n'est créée qu'à l'enregistrement, pour
un jour enregistré et resté travaillé.
"""

from datetime import date
from unittest.mock import MagicMock, patch

from app.modules.schedules.application import punch_accounting_service as svc
from app.modules.schedules.domain.punch_accounting_entities import PunchAccountingSettings
from app.modules.schedules.domain.punch_accounting_rules import slot_from_row
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee

SERVICE = "app.modules.schedules.application.timesheet_import.commit_service"

REGLAGE = PunchAccountingSettings(
    enabled=True,
    tolerance_minutes=10,
    default_break_deduct_minutes=0,
    require_manager_validation_for_overtime=True,
)
CRENEAU = slot_from_row(
    {
        "id": "s1",
        "company_id": "comp-1",
        "code": "J",
        "label": "Journée",
        "entry_time": "08:00",
        "exit_time": "16:00",
        "theoretical_gross_minutes": 480,
        "break_deduct_minutes": 0,
    }
)


def _apercu(entree: str = "08:00", sortie: str = "18:00") -> AiCalendarProposalResponse:
    return AiCalendarProposalResponse(
        year=2026,
        month=7,
        source="feuille",
        employees=[
            AiEmployeeProposal(
                employee_id="emp-1",
                raw_name="HUGO",
                days=[
                    AiDayEntry(
                        jour=3, type="travail", nature="reel",
                        punch_entry_raw=entree, punch_exit_raw=sortie,
                    )
                ],
            )
        ],
    )


def _jour_de_l_apercu(revue_existante=None) -> AiDayEntry:
    ecriture = MagicMock(side_effect=AssertionError("l'aperçu ne doit rien écrire"))
    with (
        patch.object(svc.repo, "get_settings", return_value=REGLAGE),
        patch.object(svc.repo, "list_slots", return_value=[CRENEAU]),
        patch.object(svc.repo, "get_overtime_review", return_value=revue_existante),
        patch.object(svc.repo, "upsert_overtime_review", ecriture),
    ):
        out = svc.apply_punch_accounting_to_proposal(_apercu(), "comp-1")
    ecriture.assert_not_called()
    return out.employees[0].days[0]


class TestLApercuNEcritRien:
    def test_les_heures_en_plus_sont_notees_sur_le_jour(self):
        jour = _jour_de_l_apercu()
        assert jour.heures == 8.0
        assert jour.heures_en_plus_a_valider and jour.heures_en_plus_a_valider > 0
        assert jour.motif_heures_en_plus
        assert jour.creneau_applique_id == "s1"

    def test_une_decision_deja_approuvee_au_meme_contenu_reste_creditee(self):
        brut = _jour_de_l_apercu()
        approuvee = {
            "status": "approved",
            "overtime_hours": brut.heures_en_plus_a_valider,
            "reason": brut.motif_heures_en_plus,
        }
        jour = _jour_de_l_apercu(approuvee)
        assert jour.heures == round(8.0 + brut.heures_en_plus_a_valider, 2)

    def test_une_decision_approuvee_pour_un_autre_excedent_ne_credite_pas(self):
        brut = _jour_de_l_apercu()
        autre = {"status": "approved", "overtime_hours": 0.5, "reason": brut.motif_heures_en_plus}
        assert _jour_de_l_apercu(autre).heures == 8.0


class TestLEnregistrementCreeLesRevues:
    def _jour(self, **kw) -> AiDayEntry:
        base = dict(
            jour=3, heures=8.0, type="travail", nature="reel",
            punch_entry_raw="08:00", punch_exit_raw="18:00",
            heures_en_plus_a_valider=1.83, motif_heures_en_plus="late_exit",
            creneau_applique_id="s1",
        )
        base.update(kw)
        return AiDayEntry(**base)

    def test_un_jour_travaille_enregistre_cree_sa_revue_en_attente(self):
        ecriture = MagicMock(return_value={})
        employes = [PersistTimesheetEmployee(employee_id="emp-1", days=[self._jour()])]
        with patch.object(svc.repo, "upsert_overtime_review", ecriture):
            svc.enregistrer_heures_en_plus_a_valider("comp-1", 2026, 7, employes)
        ecriture.assert_called_once_with(
            "comp-1",
            employee_id="emp-1",
            work_date=date(2026, 7, 3),
            overtime_hours=1.83,
            reason="late_exit",
            raw_entry_time="08:00",
            raw_exit_time="18:00",
            applied_slot_id="s1",
            status="pending",
        )

    def test_rien_pour_un_jour_retype_un_jour_prevu_ou_sans_heures_en_plus(self):
        ecriture = MagicMock(return_value={})
        employes = [
            PersistTimesheetEmployee(
                employee_id="emp-1",
                days=[
                    self._jour(type="conges_payes"),
                    self._jour(nature="prevu"),
                    self._jour(heures_en_plus_a_valider=None),
                    self._jour(heures_en_plus_a_valider=0.0),
                ],
            )
        ]
        with patch.object(svc.repo, "upsert_overtime_review", ecriture):
            svc.enregistrer_heures_en_plus_a_valider("comp-1", 2026, 7, employes)
        ecriture.assert_not_called()

    def test_le_jour_d_un_autre_mois_garde_sa_date(self):
        ecriture = MagicMock(return_value={})
        employes = [PersistTimesheetEmployee(employee_id="emp-1", days=[self._jour(jour=30, year=2026, month=6)])]
        with patch.object(svc.repo, "upsert_overtime_review", ecriture):
            svc.enregistrer_heures_en_plus_a_valider("comp-1", 2026, 7, employes)
        assert ecriture.call_args.kwargs["work_date"] == date(2026, 6, 30)


@patch(f"{SERVICE}.enregistrer_heures_en_plus_a_valider")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_le_commit_d_un_lot_cree_les_revues_apres_l_ecriture(
    mock_statut, mock_repo, mock_sched_repo, mock_enregistrer
):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        commit_batch_bulk,
    )
    from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest

    jour = AiDayEntry(
        jour=3, heures=8.0, type="travail", nature="reel",
        heures_en_plus_a_valider=1.83, motif_heures_en_plus="late_exit",
    )
    mock_repo.get_batch.return_value = {
        "id": "b1",
        "company_id": "c1",
        "status": "previewed",
        "file_hash": "h1",
        "preview_json": AiCalendarProposalResponse(
            year=2026, month=7, source="test",
            employees=[
                AiEmployeeProposal(
                    raw_name="HUGO", employee_id="e1", days=[jour],
                    review_status="ok", match_confidence="high",
                )
            ],
        ).model_dump(mode="json"),
        "summary_json": {},
    }
    mock_statut.return_value = ("c1", "CDI")
    mock_sched_repo.list_schedules_for_employees.return_value = {}
    ordre: list[str] = []
    mock_sched_repo.bulk_upsert_schedules.side_effect = lambda *_a, **_k: ordre.append("planning")
    mock_enregistrer.side_effect = lambda *_a, **_k: ordre.append("revues")

    commit_batch_bulk("b1", company_id="c1", request=TimesheetImportCommitRequest())

    assert ordre == ["planning", "revues"]
    societe, annee, mois, employes = mock_enregistrer.call_args.args
    assert (societe, annee, mois) == ("c1", 2026, 7)
    assert employes[0].days[0].heures_en_plus_a_valider == 1.83


@patch(f"{SERVICE}.timesheet_import_repository")
def test_la_relecture_garde_les_heures_en_plus_notees_par_le_serveur(mock_repo):
    """L'écran renvoie le jour sans les notes du serveur : elles restent sur le
    lot pour un jour toujours travaillé, et tombent si la RH l'a retypé."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        appliquer_revue_au_lot,
    )

    note = dict(
        type="travail", nature="reel", heures=8.0,
        punch_entry_raw="08:00", punch_exit_raw="18:00",
        heures_en_plus_a_valider=1.83, motif_heures_en_plus="late_exit",
        creneau_applique_id="s1",
    )
    mock_repo.get_batch.return_value = {
        "id": "b1",
        "preview_json": {
            "employees": [
                {"employee_id": "e1", "raw_name": "HUGO", "days": [{"jour": 3, **note}, {"jour": 4, **note}]}
            ]
        },
        "summary_json": {},
    }
    ecran = [
        PersistTimesheetEmployee(
            employee_id="e1",
            days=[
                AiDayEntry(jour=3, heures=8.0, type="travail", nature="reel"),
                AiDayEntry(jour=4, heures=0.0, type="conges_payes", nature="reel"),
            ],
        )
    ]
    appliquer_revue_au_lot("b1", company_id="c1", employees=ecran)
    jours = mock_repo.update_batch.call_args.args[1]["preview_json"]["employees"][0]["days"]
    assert jours[0]["heures_en_plus_a_valider"] == 1.83
    assert jours[0]["motif_heures_en_plus"] == "late_exit"
    assert jours[0]["punch_entry_raw"] == "08:00"
    assert jours[1].get("heures_en_plus_a_valider") is None
