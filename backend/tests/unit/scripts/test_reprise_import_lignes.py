"""Un bulletin repris de Quadra porte les valeurs du PDF, pas celles de notre rejeu.

Constat du 21/09/2026 : les bulletins de janvier à juin portaient les lignes
de brut du rejeu (Bugny mai : 4 h d'heures sup au lieu de 15) et un bloc de
cumuls à plat que la vue ne sait pas lire. Le contingent d'heures sup et la
comparaison d'un mois à l'autre lisent ces lignes.
"""

from __future__ import annotations

import pytest

from app.modules.repos_compensateur.domain.rules import (
    extraire_heures_hs_du_bulletin,
)
from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.reprise_colorplast_import_litteral import (
    _cumuls_affiches,
    _donnees_reprises,
    _lignes_du_brut,
)

pytestmark = pytest.mark.unit


def _bulletin_bugny_mai() -> Bulletin:
    """Les lignes du PDF de mai 2026, Bugny, dans l'ordre du document."""
    b = Bulletin(matricule="BUGNY", pages=[1, 2])
    b.lignes = [
        Ligne(None, "SALAIRE DE BASE", base=151.67, taux=14.28, gain=2165.85),
        Ligne(None, "H. supp majorées à 25 %", base=17.33, taux=17.85, gain=309.34),
        Ligne(None, "SOUS TOTAL SALAIRE DE BASE", base=169.0, gain=2475.19),
        Ligne(None, "Heures supplémentaires 25", base=15.0, taux=17.85, gain=267.75),
        Ligne("BPA", "Prime exceptionnelle", base=150.0, gain=150.0),
        Ligne("BANC", "Prime ancienneté", base=1980.15, taux=3.0, gain=59.4),
        Ligne(None, "SALAIRE BRUT", gain=2952.34),
        Ligne(None, "Sécu.Soc Plafonnée", base=2952.34, taux=6.9, montant_sal=203.71, section="Q300 RETRAITE"),
    ]
    b.droite = {
        "cumul_bruts": 14817.53, "cumul_heures": 924.5, "cumul_hs": 190.48,
        "cumul_bases": 14817.53, "smic": 12.31, "plafond": 4005.0,
    }
    b.net = {
        "net_imposable_cumul": 12551.0, "pas_cumul": 445.23,
        "net_hs_exo_cumul": 3100.0, "net_a_payer": 5479.53,
    }
    return b


class TestLignesDuBrut:
    def test_les_lignes_du_pdf_deviennent_le_calcul_du_brut(self):
        lignes = _lignes_du_brut(_bulletin_bugny_mai())
        libelles = [l["libelle"] for l in lignes]
        assert libelles == [
            "Salaire de base",
            "Heures suppl. structurelles majorées à 25%",
            "SOUS-TOTAL SALAIRE CONTRACTUEL",
            "Heures suppl. majorées à 25%",
            "Prime exceptionnelle",
            "Prime ancienneté",
        ]

    def test_les_quantites_et_montants_viennent_du_pdf(self):
        lignes = {l["libelle"]: l for l in _lignes_du_brut(_bulletin_bugny_mai())}
        hs = lignes["Heures suppl. majorées à 25%"]
        assert hs["quantite"] == 15.0 and hs["taux"] == 17.85 and hs["gain"] == 267.75

    def test_le_sous_total_est_marque_comme_tel(self):
        lignes = {l["libelle"]: l for l in _lignes_du_brut(_bulletin_bugny_mai())}
        assert lignes["SOUS-TOTAL SALAIRE CONTRACTUEL"]["is_sous_total"] is True

    def test_les_cotisations_ne_sont_pas_des_lignes_de_brut(self):
        assert not any(
            "Sécu" in l["libelle"] for l in _lignes_du_brut(_bulletin_bugny_mai())
        )

    def test_le_contingent_d_heures_sup_lit_les_heures_du_pdf(self):
        """17,33 structurelles + 15 conjoncturelles, comme Quadra."""
        donnees = _donnees_reprises(None, _bulletin_bugny_mai(), 2026, 5)
        assert extraire_heures_hs_du_bulletin(donnees) == pytest.approx(32.33)

    def test_une_retenue_du_pdf_devient_une_perte(self):
        b = _bulletin_bugny_mai()
        b.lignes.insert(
            4, Ligne(None, "Abs. Abs aut nonpayé 100526", base=7.0, taux=12.31, montant_sal=86.17)
        )
        ligne = next(
            l for l in _lignes_du_brut(b) if l["libelle"].startswith("Abs.")
        )
        assert ligne["perte"] == 86.17 and ligne["gain"] is None

    def test_la_reduction_des_hs_pour_absence_n_est_pas_une_heure_sup_de_plus(self):
        """« H. supp majorées à 25 % » en retenue après le brut : une réduction."""
        b = _bulletin_bugny_mai()
        b.lignes.insert(
            4, Ligne(None, "H. supp majorées à 25 %", base=1.6, taux=17.85, montant_sal=28.56)
        )
        lignes = _lignes_du_brut(b)
        reduction = [l for l in lignes if l["perte"]]
        assert len(reduction) == 1
        assert reduction[0]["libelle"] == "Réduction HS structurelles (jours d'absence)"


class TestEnteteDesConges:
    """« Congés payés : 020126 » en tête de bulletin est l'entête du bloc CP :
    Quadra réimprime le même montant en ligne de paie « ARBITRAGE DES CONGES
    PAYES ». Le compter deux fois gonflait le brut reconstitué de l'indemnité."""

    def _bulletin_avec_conges(self) -> Bulletin:
        b = _bulletin_bugny_mai()
        b.lignes = [
            Ligne(None, "Congés payés : 020126", base=1.0, taux=112.0, gain=112.0),
            Ligne(None, "H.Absence Congés Payés", base=7.0, taux=14.0, montant_sal=98.0),
        ] + b.lignes
        avant_le_brut = next(
            i for i, l in enumerate(b.lignes) if l.libelle.strip().upper() == "SALAIRE BRUT"
        )
        b.lignes.insert(
            avant_le_brut, Ligne("BQCP", "ARBITRAGE DES CONGES PAYES", base=112.0, gain=112.0)
        )
        return b

    def test_l_entete_n_est_pas_une_ligne_de_paie(self):
        libelles = [l["libelle"] for l in _lignes_du_brut(self._bulletin_avec_conges())]
        assert not any(l.startswith("Congés payés :") for l in libelles)
        assert "ARBITRAGE DES CONGES PAYES" in libelles

    def test_la_somme_des_lignes_fait_le_brut(self):
        b = self._bulletin_avec_conges()
        lignes = _lignes_du_brut(b)
        somme = sum(
            (l["gain"] or 0) - (l["perte"] or 0) for l in lignes if not l.get("is_sous_total")
        )
        # 2 952,34 du bulletin de base, moins la retenue de 98, plus l'arbitrage de 112
        assert somme == pytest.approx(2952.34 - 98.0 + 112.0)


class TestCumuls:
    def test_le_bloc_a_la_forme_que_la_vue_sait_lire(self):
        cumuls = _cumuls_affiches(_bulletin_bugny_mai(), 2026, 5)
        assert cumuls["cumuls"]["brut_total"] == 14817.53
        assert cumuls["cumuls"]["heures_remunerees"] == 924.5
        assert cumuls["cumuls"]["heures_supplementaires_remunerees"] == 190.48
        assert cumuls["periode"] == {"annee_en_cours": 2026, "dernier_mois_calcule": 5}

    def test_la_vue_du_bulletin_affiche_les_cumuls_repris(self):
        from app.modules.payroll.documents.bulletin_view import construire_lateral

        donnees = _donnees_reprises(None, _bulletin_bugny_mai(), 2026, 5)
        blocs = {b["titre"]: b for b in construire_lateral(donnees)}
        valeurs = {v["libelle"]: v["valeur"] for v in blocs["CUMULS"]["valeurs"]}
        assert valeurs["Bruts"].startswith("14 817")


class TestPasDeDoublonDAbsence:
    """Les absences du PDF sont dans `calcul_du_brut` : les garder aussi dans
    `details_absences` (celles du rejeu) les compterait deux fois."""

    def test_les_sections_du_rejeu_sont_vidées(self):
        b = _bulletin_bugny_mai()
        b.lignes.insert(
            3, Ligne(None, "Abs. Abs aut nonpayé 100526", base=7.0, taux=12.31, montant_sal=86.17)
        )
        donnees = _donnees_reprises(
            {
                "details_absences": [{"libelle": "Absence arrêt maladie", "perte": 90.64}],
                "details_conges": [{"libelle": "Absence congés payés", "perte": 12.0}],
            },
            b,
            2026,
            5,
        )
        assert donnees["details_absences"] == []
        assert donnees["details_conges"] == []
        assert any(l["libelle"].startswith("Abs.") for l in donnees["calcul_du_brut"])
