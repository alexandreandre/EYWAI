"""[B1] Un taux à 0 % posé par l'écran n'est pas un taux transmis par la DGFiP.

La fenêtre de création envoyait `{is_personnalise: false, taux: 0}` même case
décochée, et la fiche renvoyait `taux: 0` à chaque enregistrement d'une fiche
sans taux. Le moteur ne lisait pas `is_personnalise` : ce 0 passait pour un taux
personnalisé et le salarié n'était prélevé de rien, quel que soit son salaire.

Service-public F34009 : sans taux personnalisé, l'administration « vous applique
un taux par défaut […] fixé en fonction de votre base mensuelle de prélèvement ».

Trois sortes de bloc, que la base distingue :
- transmis par la DGFiP (DSN ou compte rendu métier) : un type, un identifiant
  ou une période d'origine. 0 % compris, appliqué tel quel ;
- saisi à la main, case cochée : `is_personnalise` vrai, appliqué tel quel ;
- ni l'un ni l'autre (le bloc de la fenêtre de création) : aucun taux connu,
  donc la grille du taux neutre.
"""

from __future__ import annotations

import copy

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.writer import encode_dsn_bytes
from app.modules.payroll.engine.calcul_net import _calculer_prelevement_a_la_source
from tests.unit.dsn_export.test_builder_complements import BULLETIN, SALARIE, SOCIETE
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot

BLOC_DE_LA_FENETRE_DE_CREATION = {"is_personnalise": False, "taux": 0}


class _Contexte:
    def __init__(self, bloc_pas):
        self.contrat = {"specificites_paie": {"prelevement_a_la_source": bloc_pas}}
        self.baremes = baremes_snapshot()
        self.entreprise = {"identification": {"adresse": {"code_postal": "79140"}}}
        self.is_alsace_moselle = False
        self.is_apprenti = False


def _pas(bloc, net_imposable=2000.0):
    return _calculer_prelevement_a_la_source(_Contexte(bloc), net_imposable)


class TestLeBlocDeLaFenetreDeCreation:
    def test_case_decochee_et_taux_zero_applique_la_grille(self):
        """2 000 € dépassent la dernière tranche de la fixture : 11 %, pas 0 %."""
        assert _pas(BLOC_DE_LA_FENETRE_DE_CREATION) == 220.0

    def test_un_taux_seul_sans_origine_applique_la_grille(self):
        assert _pas({"taux": 0}) == 220.0

    def test_sous_le_premier_seuil_la_grille_ne_preleve_rien(self):
        assert _pas(BLOC_DE_LA_FENETRE_DE_CREATION, net_imposable=1500.0) == 0.0


class TestLesVraisTauxRestentTelsQuels:
    def test_zero_pour_cent_transmis_par_la_dgfip_reste_a_zero(self):
        """Les 120 fiches de type 01 à 0 % venues des DSN : un taux, pas une absence."""
        assert _pas({"taux": 0.0, "type_taux": "01", "is_personnalise": False}) == 0.0

    def test_zero_pour_cent_avec_son_identifiant_reste_a_zero(self):
        assert _pas({"taux": 0.0, "identifiant_taux": "123456789"}) == 0.0

    def test_un_taux_date_par_sa_periode_reste_tel_quel(self):
        assert _pas({"taux": 4.3, "periode": "2026-06"}) == 86.0

    def test_un_taux_saisi_case_cochee_est_applique(self):
        assert _pas({"taux": 4.3, "is_personnalise": True}) == 86.0

    def test_zero_pour_cent_saisi_case_cochee_reste_a_zero(self):
        assert _pas({"taux": 0, "is_personnalise": True}) == 0.0


def test_la_dsn_declare_le_bareme_au_taux_de_la_grille():
    """Bout en bout : le bulletin prélève à la grille, la DSN le déclare en type 13
    (barème, faute d'identifiant DGFiP) au taux de la grille, pas à 0,00 %."""
    net_imposable = 2000.0
    montant = _pas(BLOC_DE_LA_FENETRE_DE_CREATION, net_imposable)
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["synthese_net"]["impot_prelevement_a_la_source"] = {
        "base": net_imposable,
        "taux": round(montant / net_imposable * 100, 2),
        "montant": montant,
    }
    salarie = {
        **SALARIE,
        "specificites_paie": {"prelevement_a_la_source": dict(BLOC_DE_LA_FENETRE_DE_CREATION)},
    }
    fichier, _ = build_parsed_dsn_from_payroll(
        SOCIETE, [{"employee": salarie, "payslip_data": bulletin}], "2026-09"
    )
    texte = encode_dsn_bytes(fichier).decode("iso-8859-15")
    lignes = [(l.split(",", 1)[0], l.split(",", 1)[1].strip("'")) for l in texte.splitlines()]
    assert ("S21.G00.50.007", "13") in lignes
    assert ("S21.G00.50.006", "11.00") in lignes
    assert ("S21.G00.50.009", "220.00") in lignes
