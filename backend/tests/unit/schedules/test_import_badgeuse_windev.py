"""Import d'un export de badgeuse WinDev « Pointages "retenu" » (noms inventés).

Défauts constatés le 02/10/2026 sur des pointages de septembre : une fiche badge
sans prénom était jetée par le lecteur, et le salarié n'avait aucune heure ; les
annotations tapées par la gestionnaire sur le PDF (« +1 », « -0.5 », absences)
étaient dans la couche texte mais ignorées sans un mot, et un badgeage incomplet
donnait une journée fausse (3,53 h) présentée comme sûre.
"""

from datetime import date

import pytest

from app.modules.schedules.application.ai_fill import _build_proposal_from_cegid
from app.modules.schedules.application.parsers.cegid_weekly import (
    _normalize_note,
    try_parse_cegid_weekly,
)
from app.modules.schedules.application.timesheet_quality import (
    _apply_review_status_rules,
)
from app.modules.schedules.schemas.ai import AiEmployeeProposal, RosterEmployee
from tests.fixtures.timesheets.ocr_samples import CEGID_WEEK_22
from tests.fixtures.timesheets.windev_samples import WINDEV_BADGE_WEEK


def _lecture(texte: str = WINDEV_BADGE_WEEK):
    return try_parse_cegid_weekly(texte, target_year=2026, target_month=9)


def _fiche(matricule: str):
    return next(e for e in _lecture().employees if e.matricule == matricule)


class TestFicheBadgeAuNomSeul:
    def test_toutes_les_fiches_du_releve_sont_lues(self):
        assert [e.matricule for e in _lecture().employees] == ["101", "178", "172", "176"]

    def test_la_fiche_au_nom_seul_porte_ses_heures(self):
        fiche = _fiche("178")
        assert fiche.raw_name == "DUPRAT"
        assert [d.jour for d in fiche.days] == [14, 15, 16, 17, 18]
        assert [d.heures for d in fiche.days] == [9.08, 9.12, 8.43, 8.35, 6.28]
        assert fiche.empty_week is False

    def test_la_fiche_vide_reste_une_semaine_vide(self):
        vide = _fiche("172")
        assert vide.raw_name == "DUPRAT Claire"
        assert vide.empty_week is True
        assert vide.days == []

    def test_un_jour_de_la_semaine_seul_n_est_pas_un_nom(self):
        texte = WINDEV_BADGE_WEEK.replace("178 DUPRAT\n", "178 Lundi\n", 1)
        assert not any(e.raw_name.lower() == "lundi" for e in _lecture(texte).employees)


def _notes(matricule: str):
    return [(n.day, n.notes, n.incomplete_punches, n.hours_read) for n in _fiche(matricule).day_notes]


class TestAnnotationsDuReleve:
    def test_annotations_sur_la_ligne_du_jour_et_badgeage_incomplet(self):
        assert _notes("101") == [
            (date(2026, 9, 14), ["+1"], False, 9.5),
            (date(2026, 9, 17), ["-0.5"], False, 9.52),
            (date(2026, 9, 18), ["+1"], True, 3.53),
        ]

    def test_une_annotation_isolee_va_au_jour_qui_la_suit(self):
        assert _notes("178") == [(date(2026, 9, 18), ["+0.5"], False, 6.28)]

    def test_absences_ecrites_et_points_d_interrogation(self):
        assert _notes("176") == [
            (date(2026, 9, 14), ["???"], True, 6.23),
            (date(2026, 9, 15), ["ABSENCE JUSTIFIE -8.5"], False, None),
            (date(2026, 9, 18), ["CP"], False, None),
        ]

    def test_une_fiche_sans_annotation_n_en_a_aucune(self):
        assert _fiche("172").day_notes == []

    def test_les_heures_du_badge_ne_sont_pas_retouchees(self):
        assert [d.heures for d in _fiche("101").days] == [9.5, 9.35, 7.87, 9.52, 3.53]

    @pytest.mark.parametrize(
        ("lu", "attendu"),
        [
            ("+ 0 . 5", "+0.5"),
            ("+1.2 5", "+1.25"),
            ("-0.2 5", "-0.25"),
            ("- . 0.5", "-0.5"),
            ("? ? ?", "???"),
            ("?.", "?"),
            ("ABSENT- 5.5", "ABSENT-5.5"),
            ("ABSENCE JUSTIFIE -8.5", "ABSENCE JUSTIFIE -8.5"),
        ],
    )
    def test_le_texte_espace_par_le_pdf_est_recolle(self, lu, attendu):
        assert _normalize_note(lu) == attendu

    def test_la_mise_en_page_date_en_tete_n_invente_aucune_annotation(self):
        lus = try_parse_cegid_weekly(CEGID_WEEK_22, target_year=2026, target_month=5)
        assert all(e.day_notes == [] for e in lus.employees)


class TestAnnotationsALaRevue:
    ROSTER = (RosterEmployee(id="r1", first_name="Lina", last_name="ROUSSET"),)

    def _ligne(self):
        apercu = _build_proposal_from_cegid(
            year=2026,
            month=9,
            source="relevé Cegid (test)",
            parse_result=_lecture(),
            roster=list(self.ROSTER),
            default_nature="reel",
        )
        return next(e for e in apercu.employees if e.time_tracking_id == "101")

    def test_la_ligne_dit_ce_que_le_releve_porte_et_ce_qu_eywai_a_retenu(self):
        ligne = self._ligne()
        message = next(w for w in ligne.warnings if "annotations" in w)
        assert "heures du badge" in message
        assert "lun 14/09 « +1 »" in message
        assert "jeu 17/09 « -0.5 »" in message
        assert "ven 18/09 « +1 », badgeage incomplet, 3,53 h lues" in message
        assert ligne.sheet_annotations == [
            "lun 14/09 « +1 »",
            "jeu 17/09 « -0.5 »",
            "ven 18/09 « +1 », badgeage incomplet, 3,53 h lues",
        ]

    def test_une_ligne_annotee_reste_a_verifier(self):
        ligne = AiEmployeeProposal(
            raw_name="ROUSSET Lina",
            employee_id="r1",
            match_confidence="high",
            review_status="ok",
            sheet_annotations=["lun 14/09 « +1 »"],
        )
        assert _apply_review_status_rules(ligne).review_status == "warning"

    def test_un_apercu_resservi_garde_ses_annotations(self):
        from app.modules.schedules.application.employee_match import (
            rematch_proposal_employees,
        )
        from app.modules.schedules.schemas.ai import AiCalendarProposalResponse

        ligne = self._ligne()
        apercu = AiCalendarProposalResponse(
            year=2026, month=9, source="cache", employees=[ligne]
        )
        resservi = rematch_proposal_employees(apercu, list(self.ROSTER)).employees[0]
        assert resservi.sheet_annotations == ligne.sheet_annotations
        assert any("pas les annotations" in w for w in resservi.warnings)

    def test_une_ligne_sans_annotation_reste_prete(self):
        ligne = AiEmployeeProposal(
            raw_name="ROUSSET Lina",
            employee_id="r1",
            match_confidence="high",
            review_status="ok",
        )
        assert _apply_review_status_rules(ligne).review_status == "ok"
