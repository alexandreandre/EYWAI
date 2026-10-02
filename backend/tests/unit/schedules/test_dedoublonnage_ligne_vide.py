"""Une ligne sans aucune heure ne prend jamais le salarié d'une ligne qui en porte.

Constaté le 02/10/2026 : une ancienne fiche badge vide « NOM Prénom » était
rapprochée de la salariée dont la vraie fiche (au nom seul) portait les heures.
Le dédoublonnage gardait la ligne la plus « confiante » — la vide, rapprochée
exactement — et renvoyait la fiche pleine en association manuelle. Noms inventés.
"""

from app.modules.schedules.application.ai_fill import _build_proposal_from_cegid
from app.modules.schedules.application.employee_match import (
    deduplicate_employee_matches,
)
from app.modules.schedules.application.parsers.cegid_weekly import (
    try_parse_cegid_weekly,
)
from app.modules.schedules.schemas.ai import (
    AiDayEntry,
    AiEmployeeProposal,
    RosterEmployee,
)
from tests.fixtures.timesheets.windev_samples import WINDEV_BADGE_WEEK


def _ligne(nom, *, heures, confiance, statut="ok"):
    return AiEmployeeProposal(
        raw_name=nom,
        employee_id="m1",
        matched_name="Claire MOREL",
        match_confidence=confiance,
        review_status=statut,
        days=[AiDayEntry(jour=14 + i, heures=h) for i, h in enumerate(heures)],
    )


class TestDedoublonnage:
    def test_la_ligne_qui_porte_les_heures_garde_le_salarie(self):
        vide = _ligne("DUPRAT Claire", heures=[], confiance="high", statut="empty")
        pleine = _ligne("DUPRAT", heures=[9.08, 9.12], confiance="medium", statut="warning")
        vide, pleine = deduplicate_employee_matches([vide, pleine])
        assert pleine.employee_id == "m1"
        assert pleine.review_status == "warning"
        assert vide.employee_id is None
        assert vide.review_status == "empty"
        assert any("« DUPRAT »" in w for w in vide.warnings)

    def test_des_jours_a_zero_heure_ne_comptent_pas_comme_des_heures(self):
        a_zero = _ligne("DUPRAT Claire", heures=[0.0, 0.0], confiance="high")
        pleine = _ligne("DUPRAT", heures=[7.5], confiance="medium", statut="warning")
        a_zero, pleine = deduplicate_employee_matches([a_zero, pleine])
        assert pleine.employee_id == "m1"
        assert a_zero.employee_id is None
        assert a_zero.review_status == "empty"

    def test_une_ligne_d_absences_passe_avant_une_ligne_vide(self):
        vide = _ligne("DUPRAT Claire", heures=[], confiance="high", statut="empty")
        absences = AiEmployeeProposal(
            raw_name="DUPRAT",
            employee_id="m1",
            match_confidence="medium",
            review_status="warning",
            days=[AiDayEntry(jour=14, heures=0.0, type="conge")],
        )
        vide, absences = deduplicate_employee_matches([vide, absences])
        assert absences.employee_id == "m1"
        assert vide.employee_id is None
        assert vide.review_status == "empty"

    def test_deux_lignes_avec_heures_restent_en_association_manuelle(self):
        sure = _ligne("MOREL Claire", heures=[8.0], confiance="high")
        douteuse = _ligne("MOREL C", heures=[7.0], confiance="medium", statut="warning")
        sure, douteuse = deduplicate_employee_matches([sure, douteuse])
        assert sure.employee_id == "m1"
        assert douteuse.employee_id is None
        assert douteuse.review_status == "error"


ROSTER_RELEVE = (
    RosterEmployee(id="r1", first_name="Lina", last_name="ROUSSET"),
    RosterEmployee(id="m1", first_name="Claire", last_name="MOREL", usage_name="DUPRAT"),
    RosterEmployee(id="b1", first_name="Paul", last_name="BERTIN"),
)


class TestReleveBadgeuseDeBoutEnBout:
    def _apercu(self):
        lecture = try_parse_cegid_weekly(WINDEV_BADGE_WEEK, target_year=2026, target_month=9)
        apercu = _build_proposal_from_cegid(
            year=2026,
            month=9,
            source="relevé Cegid (test)",
            parse_result=lecture,
            roster=list(ROSTER_RELEVE),
            default_nature="reel",
        )
        lignes = deduplicate_employee_matches(list(apercu.employees))
        return {e.time_tracking_id: e for e in lignes}

    def test_la_fiche_au_nom_seul_porte_les_heures_de_la_salariee(self):
        fiche = self._apercu()["178"]
        assert fiche.employee_id == "m1"
        assert sum(d.heures for d in fiche.days) == 41.26

    def test_l_ancienne_fiche_vide_n_ecrase_personne(self):
        vide = self._apercu()["172"]
        assert vide.employee_id is None
        assert vide.review_status == "empty"
