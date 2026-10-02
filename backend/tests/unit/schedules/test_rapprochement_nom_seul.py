"""Rapprochement d'une ligne de pointage au nom seul ou au nom d'usage (noms inventés).

Constaté le 02/10/2026 : une fiche badge « NOM » sans prénom ne trouvait personne,
et une fiche badge au nom d'usage n'était rapprochée que par le prénom, sans le
dire. Règle : un nom seul rapproche le salarié quand il est le seul de ce nom
(nom de famille ou nom d'usage) ; sinon l'ambiguïté est dite, jamais devinée.
"""

from unittest.mock import MagicMock, patch

from app.modules.schedules.application.employee_match import (
    resolve_employee_for_timesheet,
)
from app.modules.schedules.application.roster_enrichment import (
    enrich_roster_time_tracking_ids,
)
from app.modules.schedules.schemas.ai import RosterEmployee

ROSTER = [
    RosterEmployee(id="r1", first_name="Lina", last_name="ROUSSET"),
    RosterEmployee(id="m1", first_name="Claire", last_name="MOREL", usage_name="DUPRAT"),
    RosterEmployee(id="b1", first_name="Paul", last_name="BERTIN"),
    RosterEmployee(id="f1", first_name="Jules", last_name="FABRE"),
    RosterEmployee(id="f2", first_name="Nina", last_name="FABRE"),
    RosterEmployee(id="v1", first_name="Anne", last_name="VASSEUR", usage_name="LEROUX"),
    RosterEmployee(id="l1", first_name="Marc", last_name="LEROUX"),
]


def _rapproche(nom: str, matricule: str | None = "178"):
    return resolve_employee_for_timesheet(raw_name=nom, matricule=matricule, roster=ROSTER)


class TestNomSeul:
    def test_un_nom_seul_rapproche_le_seul_salarie_de_ce_nom(self):
        p = _rapproche("BERTIN")
        assert p.employee_id == "b1"
        assert p.review_status == "warning"
        assert any("Nom seul « BERTIN »" in w and "Paul BERTIN" in w for w in p.warnings)

    def test_un_nom_seul_rapproche_par_le_nom_d_usage(self):
        p = _rapproche("DUPRAT")
        assert p.employee_id == "m1"
        assert any("nom d'usage" in w for w in p.warnings)

    def test_deux_salaries_du_meme_nom_sont_signales_pas_devines(self):
        p = _rapproche("FABRE")
        assert p.employee_id is None
        assert p.review_status == "error"
        assert any("Jules FABRE" in w and "Nina FABRE" in w for w in p.warnings)

    def test_un_nom_d_usage_qui_est_le_nom_d_un_autre_est_ambigu(self):
        p = _rapproche("LEROUX")
        assert p.employee_id is None
        assert p.review_status == "error"
        assert any("Anne VASSEUR" in w and "Marc LEROUX" in w for w in p.warnings)

    def test_un_nom_seul_inconnu_n_est_pas_du_bruit_ocr(self):
        p = _rapproche("GARNIER")
        assert p.employee_id is None
        assert p.review_status == "error"
        assert not any("Ligne ignorée" in w for w in p.warnings)
        assert any("Aucun employé reconnu pour « GARNIER »" in w for w in p.warnings)

    def test_le_matricule_connu_prime_sur_le_nom_seul(self):
        roster = [*ROSTER, RosterEmployee(id="x1", first_name="Basile", last_name="PERRIN", time_tracking_id="178")]
        p = resolve_employee_for_timesheet(raw_name="BERTIN", matricule="178", roster=roster)
        assert p.employee_id == "x1"
        assert p.match_method == "matricule"


class TestNomDUsage:
    def test_nom_d_usage_et_prenom_rapprochent_exactement(self):
        p = _rapproche("DUPRAT Claire", matricule="172")
        assert p.employee_id == "m1"
        assert p.match_confidence == "high"

    def test_nom_d_usage_compose(self):
        roster = [RosterEmployee(id="c1", first_name="Inès", last_name="MOREAU", usage_name="DE LA TOUR")]
        p = resolve_employee_for_timesheet(raw_name="DE LA TOUR Inès", matricule="9", roster=roster)
        assert p.employee_id == "c1"


class TestPrenomSeulEnCommun:
    def test_un_rapprochement_par_le_seul_prenom_est_dit(self):
        p = _rapproche("CHAMPION Lina", matricule="170")
        assert p.employee_id == "r1"
        assert p.review_status == "warning"
        assert any("par le prénom seul" in w for w in p.warnings)


class TestRosterEnrichi:
    def test_le_nom_d_usage_de_la_fiche_complete_le_roster(self):
        reponse = MagicMock()
        reponse.data = [{"id": "m1", "time_tracking_id": None, "nom_usage": "DUPRAT"}]
        table = MagicMock()
        table.select.return_value.in_.return_value.execute.return_value = reponse
        client = MagicMock()
        client.table.return_value = table
        roster = [RosterEmployee(id="m1", first_name="Claire", last_name="MOREL")]
        with patch(
            "app.modules.schedules.application.roster_enrichment.supabase", client
        ):
            enrichi = enrich_roster_time_tracking_ids(roster, "co-1")
        assert enrichi[0].usage_name == "DUPRAT"
        assert "nom_usage" in table.select.call_args[0][0]
