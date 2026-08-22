"""Lot 4 Task 3 : la validation des heures sup retient VRAIMENT.

Avant : exiger la validation manager payait le pointé complet (HS
incluses) — plus que ne pas l'exiger — et approuver/refuser étaient des
no-ops. Désormais : HS en attente = non payées (théorique retenu),
approbation = heures écrites dans le calendrier réel (le chemin que tous
les recalculs lisent), refus = théorique confirmé.
"""

from unittest.mock import MagicMock, patch

from app.modules.schedules.domain.punch_accounting_entities import (
    PunchAccountingSettings,
)
from app.modules.schedules.domain.punch_accounting_rules import (
    compute_punch_day,
    slot_from_row,
)

_SETTINGS_AVEC_REVUE = PunchAccountingSettings(
    enabled=True,
    tolerance_minutes=10,
    default_break_deduct_minutes=0,
    require_manager_validation_for_overtime=True,
)
_SETTINGS_SANS_REVUE = PunchAccountingSettings(
    enabled=True,
    tolerance_minutes=10,
    default_break_deduct_minutes=0,
    require_manager_validation_for_overtime=False,
)
_SLOT = slot_from_row(
    {
        "code": "M",
        "entry_time": "08:00",
        "exit_time": "16:00",
        "theoretical_gross_minutes": 480,
        "break_deduct_minutes": 0,
    }
)


def _jour_avec_2h_de_depassement():
    from app.modules.schedules.domain.punch_accounting_entities import PunchDayInput

    # 08:00 → 18:00 : 10 h pointées, 8 h théoriques, 2 h d'excédent
    return PunchDayInput(entry_minutes=480, exit_minutes=1080, shift_code="M")


def test_les_hs_en_attente_de_validation_ne_sont_pas_payees():
    r = compute_punch_day(_jour_avec_2h_de_depassement(), _SETTINGS_AVEC_REVUE, [_SLOT])
    assert r.needs_review is True
    assert r.overtime_hours > 0
    assert r.accounted_hours == r.theoretical_net_hours, (
        "exiger la validation ne doit pas payer PLUS que ne pas l'exiger"
    )


def test_sans_revue_les_hs_sont_payees_directement():
    r = compute_punch_day(_jour_avec_2h_de_depassement(), _SETTINGS_SANS_REVUE, [_SLOT])
    assert r.needs_review is False
    assert r.accounted_hours == round(r.theoretical_net_hours + r.overtime_hours, 2)


class TestDecisionDeRevue:
    """L'approbation écrit les heures dans le calendrier réel ; le refus
    confirme le théorique ; tout est idempotent et réversible."""

    def _decider(self, ancien_statut, nouveau_statut, heures_jour=8.0):
        from app.modules.schedules.application import punch_accounting_commands as cmds

        etat = {
            "actual": {
                "periode": {"annee": 2026, "mois": 7},
                "calendrier_reel": [
                    {"jour": 3, "heures_faites": heures_jour, "type": "travail"}
                ],
            }
        }
        row_apres = {
            "id": "rev-1",
            "employee_id": "emp-1",
            "work_date": "2026-07-03",
            "overtime_hours": 2.0,
            "status": nouveau_statut,
        }
        fake_repo = MagicMock()
        fake_repo.get_overtime_review_status.return_value = ancien_statut
        fake_repo.update_overtime_review.return_value = row_apres

        fake_schedules = MagicMock()
        fake_schedules.get_actual_hours.return_value = dict(etat["actual"])

        def fake_upsert(employee_id, company_id, year, month, actual_hours=None, **kw):
            etat["actual"] = actual_hours

        fake_schedules.upsert_schedule.side_effect = fake_upsert

        payload = MagicMock()
        payload.status = nouveau_statut
        payload.review_note = None
        with (
            patch.object(cmds, "repo", fake_repo),
            patch.object(cmds, "schedule_repository", fake_schedules, create=True),
            patch.object(cmds, "list_punch_overtime_reviews", return_value=[]),
            patch.object(cmds, "get_employee_company", return_value="comp-1", create=True),
        ):
            try:
                cmds.update_punch_overtime_review(
                    "comp-1", "rev-1", payload, reviewed_by="mgr-1"
                )
            except Exception:
                pass  # le retour liste vide fait lever le lookup final — hors sujet
        jour = next(
            e for e in etat["actual"]["calendrier_reel"] if e["jour"] == 3
        )
        return jour["heures_faites"]

    def test_approbation_ajoute_les_hs_au_calendrier_reel(self):
        assert self._decider("pending", "approved") == 10.0

    def test_refus_confirme_le_theorique(self):
        assert self._decider("pending", "rejected") == 8.0

    def test_annuler_une_approbation_retire_les_hs(self):
        assert self._decider("approved", "rejected", heures_jour=10.0) == 8.0

    def test_re_approuver_n_ajoute_pas_deux_fois(self):
        assert self._decider("approved", "approved", heures_jour=10.0) == 10.0


def test_le_canal_historique_d_injection_a_disparu():
    """B1 — garder deux canaux payait les HS deux fois : l'approbation écrit
    le calendrier réel (que l'analyseur qualifie), l'injection dans
    payroll_events ne doit plus exister nulle part."""
    import subprocess

    from pathlib import Path

    backend = Path(__file__).resolve().parents[3]
    r = subprocess.run(
        [
            "grep", "-rn", "--include=*.py",
            "inject_approved_punch_overtime", str(backend / "app"),
        ],
        capture_output=True, text=True,
    )
    assert r.stdout == "", r.stdout


def test_la_retention_ne_credite_jamais_plus_que_le_pointe():
    """B2 — badge 05:00→05:15 avec créneau 08:00-16:30 : la revue early_entry
    ne doit pas créditer 7,75 h de théorique pour 15 minutes badgées."""
    from app.modules.schedules.domain.punch_accounting_entities import PunchDayInput

    slot = slot_from_row(
        {
            "code": "M",
            "entry_time": "08:00",
            "exit_time": "16:30",
            "theoretical_gross_minutes": 510,
            "break_deduct_minutes": 45,
        }
    )
    jour = PunchDayInput(entry_minutes=300, exit_minutes=315, shift_code="M")
    r = compute_punch_day(jour, _SETTINGS_AVEC_REVUE, [slot])
    assert r.needs_review is True
    assert r.accounted_hours == r.pointed_net_hours
    assert r.accounted_hours <= 0.25


def test_le_reimport_ne_retrograde_pas_une_revue_approuvee():
    """F3 — un ré-import du mois (opération courante avant paie) remettait
    la revue en pending et le jour au théorique : la décision du manager
    disparaissait en silence."""
    from unittest.mock import MagicMock, patch as p_

    from app.modules.schedules.infrastructure import punch_accounting_repository as repo

    fake_supabase = MagicMock()
    existante = MagicMock()
    existante.data = [
        {"id": "rev-1", "status": "approved", "overtime_hours": 2.0, "reason": "late_exit"}
    ]
    table = MagicMock()
    fake_supabase.table.return_value = table
    sel = MagicMock()
    table.select.return_value = sel
    sel.eq.return_value = sel
    sel.limit.return_value.execute.return_value = existante
    capture = {}

    def fake_update(payload):
        capture["payload"] = payload
        u = MagicMock()
        u.eq.return_value.execute.return_value = MagicMock(data=[payload])
        return u

    table.update.side_effect = fake_update
    from datetime import date

    with p_.object(repo, "supabase", fake_supabase):
        repo.upsert_overtime_review(
            "comp-1",
            employee_id="emp-1",
            work_date=date(2026, 7, 3),
            overtime_hours=2.0,
            reason="late_exit",
            raw_entry_time="08:00",
            raw_exit_time="18:10",
            applied_slot_id=None,
            status="pending",
        )
    assert capture["payload"]["status"] == "approved", (
        "même excédent, même motif : la décision du manager est conservée"
    )


def test_le_canal_feuilles_reapplique_aussi_l_excedent_approuve():
    """Trou miroir attrapé par la vérif delta : le ré-import d'une FEUILLE
    remettait le jour au théorique alors que la revue restait approved —
    sans transition de statut, plus personne ne re-créditait jamais."""
    from unittest.mock import patch as p_

    from app.modules.schedules.application import punch_accounting_service as svc
    from app.modules.schedules.domain.punch_accounting_entities import (
        PunchAccountingSettings,
    )
    from app.modules.schedules.schemas.ai import (
        AiCalendarProposalResponse,
        AiDayEntry,
        AiEmployeeProposal,
    )

    settings = PunchAccountingSettings(
        enabled=True,
        tolerance_minutes=10,
        default_break_deduct_minutes=0,
        require_manager_validation_for_overtime=True,
    )
    slot = {
        "code": "M",
        "entry_time": "08:00",
        "exit_time": "16:00",
        "theoretical_gross_minutes": 480,
        "break_deduct_minutes": 0,
    }
    from app.modules.schedules.domain.punch_accounting_rules import slot_from_row

    proposal = AiCalendarProposalResponse(
        year=2026,
        month=7,
        source="feuille",
        employees=[
            AiEmployeeProposal(
                employee_id="emp-1",
                raw_name="HUGO",
                days=[
                    AiDayEntry(
                        jour=3,
                        type="travail",
                        punch_entry_raw="08:00",
                        punch_exit_raw="18:00",
                    )
                ],
            )
        ],
    )
    with (
        p_.object(svc.repo, "get_settings", return_value=settings),
        p_.object(svc.repo, "list_slots", return_value=[slot_from_row(slot)]),
        p_.object(
            svc.repo,
            "upsert_overtime_review",
            return_value={"status": "approved", "overtime_hours": 2.0},
        ),
    ):
        out = svc.apply_punch_accounting_to_proposal(proposal, "comp-1")
    jour = out.employees[0].days[0]
    # théorique 8,0 + excédent approuvé 1,83 (10 h − 8 h − 10 min tolérance)
    assert jour.heures > 8.0, jour.heures
