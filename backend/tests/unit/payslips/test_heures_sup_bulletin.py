"""Lecture des heures supplémentaires conjoncturelles depuis un bulletin.

Enjeu : quand une RH corrige la quantité d'heures supplémentaires directement
sur le bulletin, il faut savoir quelle quantité relève du premier palier de
majoration et laquelle du second, pour les redéclarer *toutes les deux* au
moteur. N'en déclarer qu'une remettrait l'autre à zéro (cf.
`calcul_brut._appliquer_heures_sup_declarees`).
"""

from app.modules.payslips.domain.heures_sup import (
    quantites_heures_sup_conjoncturelles,
)


def _bulletin(lignes):
    return {"calcul_du_brut": lignes}


class TestQuantitesHeuresSupConjoncturelles:
    def test_bulletin_reel_bugny_les_deux_paliers(self):
        """Cas réel : 17,33 h structurelles ignorées, 12 h et 3,5 h retenues."""
        bulletin = _bulletin(
            [
                {"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.28},
                {
                    "libelle": "Heures suppl. structurelles majorées à 25%",
                    "quantite": 17.33,
                    "taux": 17.85,
                },
                {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "is_sous_total": True},
                {"libelle": "Heures suppl. majorées à 25%", "quantite": 12.0, "taux": 17.85},
                {"libelle": "Heures suppl. majorées à 50%", "quantite": 3.5, "taux": 21.42},
                {"libelle": "Prime exceptionnelle", "quantite": None, "taux": None},
            ]
        )
        assert quantites_heures_sup_conjoncturelles(bulletin) == (12.0, 3.5)

    def test_les_structurelles_ne_comptent_jamais(self):
        """Elles viennent du contrat : les déclarer les figerait à tort."""
        bulletin = _bulletin(
            [{"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "taux": 17.85}]
        )
        assert quantites_heures_sup_conjoncturelles(bulletin) == (0.0, 0.0)

    def test_le_palier_se_lit_sur_le_taux_pas_sur_le_libelle(self):
        """Une société peut majorer à 10 %/25 % : c'est le taux le plus élevé
        qui désigne le second palier, pas le nombre écrit dans le libellé."""
        bulletin = _bulletin(
            [
                {"libelle": "Heures suppl. majorées à 10%", "quantite": 8.0, "taux": 15.70},
                {"libelle": "Heures suppl. majorées à 25%", "quantite": 2.0, "taux": 17.85},
            ]
        )
        assert quantites_heures_sup_conjoncturelles(bulletin) == (8.0, 2.0)

    def test_un_seul_palier_a_50_pourcent(self):
        bulletin = _bulletin(
            [{"libelle": "Heures suppl. majorées à 50%", "quantite": 4.0, "taux": 21.42}]
        )
        assert quantites_heures_sup_conjoncturelles(bulletin) == (0.0, 4.0)

    def test_un_seul_palier_a_25_pourcent(self):
        bulletin = _bulletin(
            [{"libelle": "Heures suppl. majorées à 25%", "quantite": 6.0, "taux": 17.85}]
        )
        assert quantites_heures_sup_conjoncturelles(bulletin) == (6.0, 0.0)

    def test_les_heures_complementaires_sont_ignorees(self):
        """Temps partiel : régime différent, elles ne sont pas des HS."""
        bulletin = _bulletin(
            [{"libelle": "Heures complémentaires majorées à 10%", "quantite": 5.0, "taux": 12.0}]
        )
        assert quantites_heures_sup_conjoncturelles(bulletin) == (0.0, 0.0)

    def test_bulletin_sans_heures_sup(self):
        assert quantites_heures_sup_conjoncturelles(_bulletin([])) == (0.0, 0.0)
        assert quantites_heures_sup_conjoncturelles({}) == (0.0, 0.0)
        assert quantites_heures_sup_conjoncturelles(None) == (0.0, 0.0)

    def test_quantite_absente_ou_illisible(self):
        bulletin = _bulletin(
            [
                {"libelle": "Heures suppl. majorées à 25%", "quantite": None, "taux": 17.85},
                {"libelle": "Heures suppl. majorées à 50%", "quantite": "3,5", "taux": 21.42},
            ]
        )
        assert quantites_heures_sup_conjoncturelles(bulletin) == (0.0, 0.0)
