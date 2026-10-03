"""Au premier mois d'un contrat, le bulletin ne reprend pas les cumuls du mois d'avant.

La réduction générale se calcule « pour chaque contrat de travail » (CSS L241-13,
III ; D241-7, V pour les CDD ; BOSS § 1070), l'indemnité de fin de CDD sur la
rémunération du seul contrat (C. trav. L1243-8), les congés repartent après
l'indemnité compensatrice versée à la fin du précédent (L1242-16). Les cumuls
d'un mois précédent appartiennent donc à un autre contrat : celui qui finissait
la veille, ou rien du tout pour une première embauche.

La suite en CDI d'un CDD (L1243-11, BOSS § 1080 : un seul calcul) ne change pas
la date d'entrée de la fiche : elle n'est pas un premier mois de contrat.
"""

from __future__ import annotations

import json

import pytest

from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents import payslip_run_heures
from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
from app.shared.domain.employment_rules import (
    cumuls_precedents_du_contrat,
    premier_mois_du_contrat,
)
from tests.unit.payroll.test_filet_heures_sur_arret import (  # noqa: F401 — fixture `moteur`
    EMP,
    _Base,
    moteur,
)

pytestmark = pytest.mark.unit

CUMULS_DU_CDD = {
    "periode": {"annee_en_cours": 2026, "dernier_mois_calcule": 8},
    "cumuls": {"brut_total": 9000.0, "heures_remunerees": 600.0, "reduction_generale_patronale": -1200.0},
}
VIDE = {"periode": {"annee_en_cours": 2026, "dernier_mois_calcule": 0}, "cumuls": {"brut_total": 0.0}}


class TestPremierMoisDuContrat:
    def test_le_mois_de_la_date_d_entree(self):
        assert premier_mois_du_contrat({"hire_date": "2026-09-01"}, 2026, 9)

    def test_une_entree_en_fin_de_mois(self):
        assert premier_mois_du_contrat({"hire_date": "2026-09-28"}, 2026, 9)

    def test_le_mois_suivant_n_est_plus_le_premier(self):
        assert not premier_mois_du_contrat({"hire_date": "2026-09-01"}, 2026, 10)

    def test_meme_mois_une_autre_annee(self):
        assert not premier_mois_du_contrat({"hire_date": "2025-09-01"}, 2026, 9)

    def test_le_debut_d_execution_prime_comme_pour_la_presence(self):
        fiche = {"hire_date": "2026-08-01", "date_debut_execution": "2026-09-01"}
        assert premier_mois_du_contrat(fiche, 2026, 9)
        assert not premier_mois_du_contrat(fiche, 2026, 8)

    def test_sans_date_d_entree(self):
        assert not premier_mois_du_contrat({}, 2026, 9)
        assert not premier_mois_du_contrat({"hire_date": "pas une date"}, 2026, 9)


class TestCumulsPrecedentsDuContrat:
    def test_premier_mois_on_repart_de_zero(self):
        depart = cumuls_precedents_du_contrat(CUMULS_DU_CDD, {"hire_date": "2026-09-01"}, 2026, 9, VIDE)
        assert depart == VIDE

    def test_le_zero_rendu_est_une_copie(self):
        depart = cumuls_precedents_du_contrat(CUMULS_DU_CDD, {"hire_date": "2026-09-01"}, 2026, 9, VIDE)
        depart["cumuls"]["brut_total"] = 1.0
        assert VIDE["cumuls"]["brut_total"] == 0.0

    def test_contrat_en_cours_les_cumuls_continuent(self):
        depart = cumuls_precedents_du_contrat(CUMULS_DU_CDD, {"hire_date": "2026-01-19"}, 2026, 9, VIDE)
        assert depart is CUMULS_DU_CDD

    def test_premiere_embauche_sans_cumul(self):
        depart = cumuls_precedents_du_contrat(None, {"hire_date": "2026-09-28"}, 2026, 9, VIDE)
        assert depart == VIDE


def _generer_avec_entree(monkeypatch, hire_date: str, cumuls_precedents: dict) -> dict:
    """Génère septembre en bac à sable et rend le fichier de cumuls d'août posé pour le calcul."""
    lu: dict = {}

    def run_espion(employee_path, year, month, *_a, **_k):
        lu["cumuls"] = json.loads((employee_path / "cumuls" / "08.json").read_text(encoding="utf-8"))
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    class _BaseEntree(_Base):
        def lire(self, table, colonnes):
            ligne = super().lire(table, colonnes)
            if table == "employees":
                ligne = {**ligne, "hire_date": hire_date, "contract_type": "CDD"}
            return ligne

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run_espion)
    monkeypatch.setattr(pg, "supabase", _BaseEntree([], compensation=False))
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: []})
    pg.process_payslip_generation(EMP, 2026, 9, bac_a_sable=BacASable(cumuls_precedents=cumuls_precedents))
    return lu["cumuls"]


class TestCablageDuGenerateurHeures:
    def test_un_nouveau_contrat_ne_reprend_pas_les_cumuls_du_precedent(self, monkeypatch, moteur):  # noqa: F811
        cumuls = _generer_avec_entree(monkeypatch, "2026-09-01", CUMULS_DU_CDD)
        assert cumuls["cumuls"]["brut_total"] == 0.0
        assert cumuls["cumuls"]["reduction_generale_patronale"] == 0.0
        assert cumuls["periode"]["dernier_mois_calcule"] == 0

    def test_un_contrat_en_cours_garde_ses_cumuls(self, monkeypatch, moteur):  # noqa: F811
        cumuls = _generer_avec_entree(monkeypatch, "2026-01-19", CUMULS_DU_CDD)
        assert cumuls == CUMULS_DU_CDD


def test_le_generateur_forfait_applique_la_meme_regle():
    """Le chemin forfait lit ses cumuls de la même façon : même règle, même place
    (après le choix entre la base et le bac à sable, avant l'écriture du fichier)."""
    import inspect

    from app.modules.payroll.documents import payslip_generator_forfait as pgf

    source = inspect.getsource(pgf.process_payslip_generation_forfait)
    choix = source.index("cumuls_de_depart(bac_a_sable, year)")
    regle = source.index("cumuls_precedents_du_contrat(")
    ecriture = source.index('employee_path / "cumuls"')
    assert choix < regle < ecriture
