"""La phrase d'arbitrage des congés payés doit dire vrai.

Le bulletin annonce laquelle des deux règles a été retenue, maintien de salaire
ou dixième. C'est une mention lue par le salarié et opposable, donc elle ne doit
pas comparer deux grandeurs sans rapport.

Deux pièges, tous deux constatés sur le bulletin de juillet 2026 de Cédric Demory :
l'indemnité du mois arrive en deux lignes qu'il faut additionner, et l'indemnité
compensatrice de fin de contrat se cumule avec elle au lieu de s'y substituer,
donc n'entre pas dans l'arbitrage.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.bulletin import creer_bulletin_final
from tests.unit.payroll.helpers import build_test_contexte

NETS = {"net_imposable": 1500.0, "net_a_payer": 1200.0, "montant_impot_pas": 0.0}


def _ligne(libelle: str, *, gain: float | None = None, perte: float | None = None) -> dict:
    return {"libelle": libelle, "gain": gain, "perte": perte, "taux": None, "quantite": None}


def _arbitrage(details_brut: list[dict]) -> str | None:
    contexte = build_test_contexte(salaire_base=1850.37)
    contexte.year = 2026
    bulletin = creer_bulletin_final(contexte, 2000.0, details_brut, [], NETS, [], 2026, 7)
    return bulletin.get("arbitrage_conges")


class TestArbitrageDesCongesDuMois:
    def test_les_deux_parts_de_l_indemnite_s_additionnent(self):
        # 86,17 + 12,31 = 98,48, exactement la retenue : maintien de salaire.
        # En n'en gardant qu'une, le bulletin comparait 12,31 à 98,48.
        texte = _arbitrage(
            [
                _ligne("Absence congés payés (1 jour : 13/07)", perte=98.48),
                _ligne("Indemnité de congés payés (partie base)", gain=86.17),
                _ligne("Indemnité de congés payés (partie HS 25%)", gain=12.31),
            ]
        )
        assert texte is not None
        assert "maintien de salaire" in texte
        assert "98.48" in texte

    def test_le_dixieme_annonce_le_total_des_deux_parts(self):
        texte = _arbitrage(
            [
                _ligne("Absence congés payés (1 jour : 13/07)", perte=98.48),
                _ligne("Indemnité de congés payés (partie base)", gain=110.00),
                _ligne("Indemnité de congés payés (partie HS 25%)", gain=15.00),
            ]
        )
        assert texte is not None
        assert "1/10ème" in texte
        assert "125.00" in texte

    def test_plusieurs_journees_d_absence_s_additionnent_aussi(self):
        texte = _arbitrage(
            [
                _ligne("Absence congés payés (1 jour : 13/07)", perte=98.48),
                _ligne("Absence congés payés (1 jour : 14/07)", perte=98.48),
                _ligne("Indemnité de congés payés (partie base)", gain=196.96),
            ]
        )
        assert texte is not None
        assert "maintien de salaire" in texte
        assert "196.96" in texte


class TestIndemniteCompensatriceDeFinDeContrat:
    def test_elle_n_entre_pas_dans_l_arbitrage_du_mois(self):
        # Le cas réel : 876,74 € d'indemnité compensatrice faisaient annoncer la
        # règle du dixième face à un maintien de 98,48 €.
        texte = _arbitrage(
            [
                _ligne("Absence congés payés (1 jour : 13/07)", perte=98.48),
                _ligne("Indemnité de congés payés (partie base)", gain=86.17),
                _ligne("Indemnité de congés payés (partie HS 25%)", gain=12.31),
                _ligne("Indemnité compensatrice de congés payés (CDD)", gain=876.74),
            ]
        )
        assert texte is not None
        assert "maintien de salaire" in texte
        assert "876.74" not in texte

    def test_seule_elle_ne_declenche_aucune_phrase_d_arbitrage(self):
        # Aucun arbitrage n'a eu lieu : ne rien affirmer. Le bulletin de sortie
        # écrit sa propre phrase depuis la méthode réellement retenue.
        texte = _arbitrage(
            [_ligne("Indemnité compensatrice de congés payés (CDD)", gain=876.74)]
        )
        assert texte is None


class TestSansConges:
    def test_aucune_phrase_sans_ligne_de_conges(self):
        assert _arbitrage([_ligne("Prime exceptionnelle", gain=100.0)]) is None

    def test_une_absence_non_payee_ne_declenche_pas_l_arbitrage(self):
        assert _arbitrage([_ligne("Absence autorisée non payée", perte=92.0)]) is None


class TestMontantsInchanges:
    def test_la_correction_ne_touche_pas_au_brut(self):
        details = [
            _ligne("Absence congés payés (1 jour : 13/07)", perte=98.48),
            _ligne("Indemnité de congés payés (partie base)", gain=86.17),
            _ligne("Indemnité compensatrice de congés payés (CDD)", gain=876.74),
        ]
        contexte = build_test_contexte(salaire_base=1850.37)
        contexte.year = 2026
        bulletin = creer_bulletin_final(contexte, 2000.0, details, [], NETS, [], 2026, 7)
        assert bulletin["salaire_brut"] == pytest.approx(2000.0)
