"""Un taux inconnu déclenche la grille par défaut, un taux nul reçu ne la déclenche pas.

Tant que la DGFiP n'a pas renvoyé de taux — un nouvel embauché avant le premier
compte rendu métier — l'employeur applique la grille. Prélever 0 % reviendrait à
décider à la place de l'administration.
"""

from app.modules.payroll.engine.calcul_net import (
    _calculer_prelevement_a_la_source,
    _zone_pas,
    taux_pas_neutre,
)
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot


class _Contexte:
    """Contexte minimal : seuls le bloc PAS, les barèmes et l'adresse comptent ici."""

    def __init__(self, bloc_pas, code_postal="79140"):
        self.contrat = {"specificites_paie": {"prelevement_a_la_source": bloc_pas}}
        self.baremes = baremes_snapshot()
        self.entreprise = {
            "identification": {"adresse": {"code_postal": code_postal}}
        }
        self.is_alsace_moselle = False
        self.is_apprenti = False


def _pas(bloc, net_imposable=2000.0, code_postal="79140"):
    return _calculer_prelevement_a_la_source(_Contexte(bloc, code_postal), net_imposable)


def test_taux_inconnu_applique_la_grille():
    """2 000 € dépassent la dernière tranche de la fixture : 11 %."""
    assert _pas({}) == 220.0


def test_bloc_absent_applique_la_grille():
    assert _pas({"type_taux": "01"}) == 220.0


def test_taux_zero_recu_reste_a_zero():
    """Un 0 % transmis par la DGFiP est un taux, pas une absence de taux."""
    assert _pas({"taux": 0.0, "type_taux": "01"}) == 0.0


def test_taux_personnalise_ignore_la_grille():
    assert _pas({"taux": 5.0, "type_taux": "01"}) == 100.0


def test_grille_sous_le_premier_seuil_ne_preleve_rien():
    assert _pas({}, net_imposable=1500.0) == 0.0


class TestUnites:
    def test_le_bareme_est_rendu_en_pourcentage(self):
        """Le barème stocke des fractions ; le moteur raisonne en pourcentage."""
        assert taux_pas_neutre(baremes_snapshot()["pas"], 5000.0, "metropole") == 11.0

    def test_bareme_vide_ne_preleve_rien(self):
        assert taux_pas_neutre([], 2000.0) == 0.0


class TestZone:
    def test_metropole_par_defaut(self):
        assert _zone_pas(_Contexte({}, "79140")) == "metropole"

    def test_antilles_reunion(self):
        assert _zone_pas(_Contexte({}, "97200")) == "guadeloupe_reunion_martinique"

    def test_guyane_mayotte(self):
        assert _zone_pas(_Contexte({}, "97300")) == "guyane_mayotte"

    def test_alsace_moselle_reste_en_metropole(self):
        """L'Alsace-Moselle est une particularité d'assurance maladie, pas d'impôt."""
        ctx = _Contexte({}, "57000")
        ctx.is_alsace_moselle = True
        assert _zone_pas(ctx) == "metropole"

    def test_adresse_absente_retombe_sur_metropole(self):
        ctx = _Contexte({})
        ctx.entreprise = {}
        assert _zone_pas(ctx) == "metropole"
