"""Bulletin de sortie : période arrêtée au départ, compteurs de congés soldés.

Retours de la réunion du 10/11/2026 (Colorplast, F.A.O., fin de CDD au 02/10) :
- la période imprimée doit s'arrêter au dernier jour du contrat (« du 01/10 au
  02/10 »), C. trav. R3243-1 5° : le bulletin porte « la période [...] à
  laquelle se rapporte le salaire » ;
- le bulletin de sortie n'est pas le reçu pour solde de tout compte, document
  distinct qui « fait l'inventaire des sommes versées au salarié lors de la
  rupture » (C. trav. L1234-20, lus le 10/11/2026) ;
- les compteurs de congés payés y sont soldés à zéro, les jours restants étant
  payés en indemnité compensatrice (C. trav. L3141-28).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.documents.bulletin_view import (
    construire_bandeau,
    construire_compteurs,
)
from app.modules.payroll.engine.bulletin import (
    date_de_sortie_du_bulletin,
    solder_les_conges_au_depart,
)

pytestmark = pytest.mark.unit


def _contexte(sortie):
    return SimpleNamespace(contrat={"contrat": {"date_sortie": sortie}})


class TestDateDeSortie:
    def test_sortie_dans_le_mois(self):
        assert date_de_sortie_du_bulletin(_contexte("2026-10-02"), 2026, 10, True) == date(2026, 10, 2)

    def test_pas_un_bulletin_de_sortie(self):
        assert date_de_sortie_du_bulletin(_contexte("2026-10-02"), 2026, 10, False) is None

    def test_sortie_un_autre_mois(self):
        assert date_de_sortie_du_bulletin(_contexte("2026-12-29"), 2026, 10, True) is None

    def test_fin_de_contrat_prevue_a_defaut(self):
        contexte = SimpleNamespace(contrat={"contrat": {"date_fin_contrat": "2026-10-31"}})
        assert date_de_sortie_du_bulletin(contexte, 2026, 10, True) == date(2026, 10, 31)


SOLDE = {
    "date_reference": "02/10/2026",
    "conges_payes": {"acquis": 2.29, "pris": 0.0, "solde": 0.42, "ajustement": -1.87},
    "conges_payes_periode_precedente": {"acquis": 0.0, "pris": 0.0, "solde": 0.0},
}
DETAIL = {"periodes": [{"libelle": "2026-2027", "restants": 0.42, "retenu": 50.01}], "total": 50.01}


class TestSolderLesConges:
    def test_compteurs_soldes_a_zero(self):
        solde, alerte = solder_les_conges_au_depart(SOLDE, DETAIL, iccp_versee=True)
        assert alerte is None
        assert solde["conges_payes"]["solde"] == 0.0
        assert solde["conges_payes"]["indemnise"] == 0.42
        assert solde["conges_payes"]["acquis"] == 2.29
        assert "indemnise" not in solde["conges_payes_periode_precedente"]
        # L'entrée n'est pas modifiée.
        assert SOLDE["conges_payes"]["solde"] == 0.42

    def test_deux_periodes(self):
        solde_entree = {
            "conges_payes": {"acquis": 4.16, "pris": 0.0, "solde": 4.16},
            "conges_payes_periode_precedente": {"acquis": 25.0, "pris": 20.0, "solde": 5.0},
        }
        detail = {"periodes": [{"restants": 5.0}, {"restants": 4.16}]}
        solde, alerte = solder_les_conges_au_depart(solde_entree, detail, iccp_versee=True)
        assert alerte is None
        assert solde["conges_payes"]["solde"] == 0.0
        assert solde["conges_payes_periode_precedente"]["solde"] == 0.0
        assert solde["conges_payes_periode_precedente"]["indemnise"] == 5.0

    def test_sans_indemnite_rien_ne_bouge(self):
        solde, alerte = solder_les_conges_au_depart(SOLDE, None, iccp_versee=False)
        assert solde == SOLDE and alerte is None

    def test_ecart_entre_compteur_et_indemnite_se_dit(self):
        detail = {"periodes": [{"restants": 0.21}]}
        solde, alerte = solder_les_conges_au_depart(SOLDE, detail, iccp_versee=True)
        assert solde["conges_payes"]["solde"] == 0.42
        assert alerte["code"] == "compteurs_conges_non_soldes_au_depart"
        assert "0,42" in alerte["message"] and "0,21" in alerte["message"]

    def test_indemnite_du_dossier_sans_detail(self):
        solde, alerte = solder_les_conges_au_depart(SOLDE, None, iccp_versee=True)
        assert alerte is None
        assert solde["conges_payes"]["solde"] == 0.0


class TestRendu:
    def test_bandeau_arrete_au_depart(self):
        bulletin = {
            "bulletin_de_sortie": True,
            "en_tete": {
                "annee": 2026,
                "mois": 10,
                "periode": "Octobre 2026",
                "date_debut_periode": "2026-10-01",
                "date_fin_periode": "2026-10-02",
                "date_sortie": "2026-10-02",
            },
        }
        bandeau = construire_bandeau(bulletin)
        assert (bandeau["du"], bandeau["au"]) == ("01/10/2026", "02/10/2026")
        assert bandeau["sortie"] == "Bulletin de sortie : dernier jour du contrat le 02/10/2026"

    def test_bandeau_mois_ordinaire(self):
        bandeau = construire_bandeau({"en_tete": {"annee": 2026, "mois": 10}})
        assert bandeau["au"] == "31/10/2026" and bandeau["sortie"] == ""

    def test_compteurs_disent_l_indemnite(self):
        solde, _ = solder_les_conges_au_depart(SOLDE, DETAIL, iccp_versee=True)
        vue = construire_compteurs({"pied_de_page": {"solde_conges": solde}})
        cp_n = next(c for c in vue["colonnes"] if c["titre"] == "CP N")
        assert cp_n["solde"] == 0.0
        assert any(
            "0,42 j payé en indemnité compensatrice de congés payés" in n for n in vue["notes"]
        )
