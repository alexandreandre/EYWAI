"""Mois de sortie : la fenêtre des variables va jusqu'au dernier jour du contrat.

Sortie le 30/11, arrêté des variables au 22/11 : le mois suivant n'a pas de
bulletin, ce qui tombe entre les deux n'était donc payé ni retenu nulle part
(registre R-238, R-239).
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.application import periode_variables_service as pvs
from app.modules.payroll.engine.calcul_brut import evenements_de_la_periode
from app.modules.schedules.domain.periode_a_saisir import periode_a_saisir
from app.shared.domain.periode_variables import FenetreVariables, fin_au_depart

pytestmark = pytest.mark.unit

MOIS = (date(2026, 11, 1), date(2026, 11, 30))
DEBUT, ARRETE, SORTIE = date(2026, 10, 26), date(2026, 11, 22), date(2026, 11, 30)


class TestFinAuDepart:
    def test_sortie_apres_l_arrete_dans_le_mois(self):
        assert fin_au_depart(ARRETE, 2026, 11, SORTIE) == SORTIE

    def test_date_de_sortie_en_texte(self):
        assert fin_au_depart(ARRETE, 2026, 11, "2026-11-30") == SORTIE

    def test_sortie_avant_l_arrete_ne_change_rien(self):
        assert fin_au_depart(ARRETE, 2026, 11, date(2026, 11, 13)) == ARRETE

    def test_sortie_le_mois_suivant_ne_change_rien(self):
        assert fin_au_depart(ARRETE, 2026, 11, date(2026, 12, 15)) == ARRETE

    @pytest.mark.parametrize("sortie", [None, "", "illisible"])
    def test_pas_de_sortie_lisible(self, sortie):
        assert fin_au_depart(ARRETE, 2026, 11, sortie) == ARRETE


@pytest.mark.parametrize(
    "type_ev",
    [
        "travail_hs25",
        "travail_hs50",
        "absence_non_remuneree",
        "absence_injustifiee_base",
        "absence_injustifiee_hs25",
        "evenement_familial",
        "conges_payes",
    ],
)
class TestChaqueTypeRattacheAuxVariables:
    def test_retenu_entre_l_arrete_et_la_sortie(self, type_ev):
        ev = {"date_complete": "2026-11-26", "type": type_ev, "heures": 7.0}
        bornes = (DEBUT, fin_au_depart(ARRETE, 2026, 11, SORTIE))
        assert evenements_de_la_periode([ev], MOIS, bornes) == [ev]

    def test_sans_sortie_il_attend_le_mois_suivant(self, type_ev):
        ev = {"date_complete": "2026-11-26", "type": type_ev, "heures": 7.0}
        bornes = (DEBUT, fin_au_depart(ARRETE, 2026, 11, None))
        assert evenements_de_la_periode([ev], MOIS, bornes) == []


class TestPeriodeASaisir:
    def _manquant(self, date_sortie):
        periode = periode_a_saisir(
            annee=2026, mois=11, fenetre=(DEBUT, ARRETE), calendriers={}, date_sortie=date_sortie
        )
        return next(j for j in periode.manquants if j.jour == date(2026, 11, 26))

    def test_les_jours_jusqu_a_la_sortie_sont_a_saisir(self):
        assert self._manquant(SORTIE).bloquant is True

    def test_sans_sortie_ils_restent_informatifs(self):
        assert self._manquant(None).bloquant is False


class TestBulletinProlonge:
    FENETRE = FenetreVariables(DEBUT, ARRETE, "regle")

    def test_le_bulletin_de_sortie_n_est_pas_a_regenerer(self):
        ligne = {"debut": "2026-10-26", "fin": "2026-11-30", "fin_societe": "2026-11-22"}
        assert pvs.bulletin_hors_fenetre(ligne, self.FENETRE) is False

    def test_si_la_fenetre_de_la_societe_a_change_il_l_est(self):
        ligne = {"debut": "2026-10-26", "fin": "2026-11-30", "fin_societe": "2026-11-15"}
        assert pvs.bulletin_hors_fenetre(ligne, self.FENETRE) is True


@pytest.fixture
def banc(monkeypatch):
    """Le générateur pour de vrai, sur le banc du filet : septembre, arrêté au 20."""
    from app.modules.payroll.application import empreinte_entrees_service
    from app.modules.payroll.documents import payslip_generator as pg
    from app.modules.payroll.documents import payslip_run_heures
    from app.modules.planning.application import shift_payroll_aggregation
    from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
    from app.modules.payroll.documents.bac_a_sable import BacASable
    from tests.unit.payroll import test_filet_heures_sur_arret as filet

    return SimpleNamespace(
        mp=monkeypatch, pg=pg, run=payslip_run_heures, agg=shift_payroll_aggregation,
        arrets=arrets_valides_reader, BacASable=BacASable, filet=filet,
        empreinte=empreinte_entrees_service,
    )


from tests.unit.payroll.test_filet_heures_sur_arret import moteur  # noqa: E402,F401


def _generer(banc, sortie):
    filet, mp, pg = banc.filet, banc.mp, banc.pg

    class Base(filet._Base):
        def lire(self, table, colonnes):
            data = super().lire(table, colonnes)
            if table == "employees" and sortie:
                return {**data, "contract_end_date": sortie}
            return data

    vu = {}
    mp.setattr(
        pvs,
        "resoudre_fenetre_variables",
        lambda *_a, **_k: FenetreVariables(date(2026, 8, 24), date(2026, 9, 20), "regle"),
    )

    def agregateur(*_a, **k):
        vu["paniers_fin"] = k["end"]
        return None

    def run(employee_path, *_a, **_k):
        vu["entreprise"] = json.loads((employee_path / "entreprise.json").read_text("utf-8"))
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    def empreinte(donnees, **k):
        vu["empreinte"] = k["fenetre_variables"]
        return donnees

    mp.setattr(banc.agg, "aggregate_shift_payroll_metrics", agregateur)
    mp.setattr(banc.run, "run_payslip_generation_heures", run)
    mp.setattr(banc.empreinte, "poser_empreinte_depuis_lectures", empreinte)
    mp.setattr(pg, "supabase", Base([], compensation=False))
    mp.setattr(banc.arrets, "par_salarie", lambda *_a, **_k: {})
    pg.process_payslip_generation(filet.EMP, 2026, 9, bac_a_sable=banc.BacASable())
    return vu


@pytest.mark.usefixtures("moteur")
class TestGenerateur:
    def test_les_paniers_et_le_moteur_vont_jusqu_a_la_sortie(self, banc):
        vu = _generer(banc, "2026-09-28")
        assert vu["paniers_fin"] == date(2026, 9, 28)
        periode = vu["entreprise"]["entreprise"]["parametres_paie"]["periode_variables"]
        assert periode["fin"] == "2026-09-28"
        assert periode["fin_societe"] == "2026-09-20"

    def test_l_empreinte_garde_la_fenetre_de_la_societe(self, banc):
        """Sinon le bulletin de sortie paraît « à recalculer » pour toujours."""
        assert _generer(banc, "2026-09-28")["empreinte"]["fin"] == "2026-09-20"

    def test_sans_sortie_rien_ne_change(self, banc):
        vu = _generer(banc, None)
        assert vu["paniers_fin"] == date(2026, 9, 20)
        periode = vu["entreprise"]["entreprise"]["parametres_paie"]["periode_variables"]
        assert periode["fin"] == "2026-09-20"
        assert "fin_societe" not in periode


def test_le_solde_imprime_compte_jusqu_a_la_sortie(monkeypatch):
    """R-294 : au mois de sortie, la fenêtre prolongée (fin_au_depart) arrive
    jusqu'au solde imprimé : il dit la même chose que l'indemnité de congés."""
    from app.modules.payroll.engine import bulletin as module_bulletin
    from tests.unit.payroll.helpers import build_test_contexte

    vus = []
    monkeypatch.setattr(
        module_bulletin,
        "build_solde_conges_pied_de_page",
        lambda _e, _a, _m, fin=None: vus.append(fin) or {},
    )
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    ctx.date_fin_variables = fin_au_depart(ARRETE, 2026, 11, SORTIE)
    nets = {"net_imposable": 1500.0, "net_a_payer": 1200.0, "montant_impot_pas": 0.0}
    module_bulletin.creer_bulletin_final(ctx, 2000.0, [], [], nets, [], 2026, 11)
    assert vus == [SORTIE]
