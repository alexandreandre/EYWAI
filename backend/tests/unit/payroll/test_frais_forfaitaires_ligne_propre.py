"""Une indemnité de frais non soumise a sa ligne au bulletin, à son libellé. [D1]

Relevé à l'écran (vidéo G, 11/10/2026) : « Indemnité panier repas » 40 € (catalogue,
non soumise) était ajoutée au net sans aucune ligne imprimée ; rangée par le
générateur dans l'acompte (`acompte_verse = −40`), elle se fondait dans la ligne
« Acomptes et avances », qui imprimait −110,00 pour une retenue de 150 € sur le
net. Elle manquait aussi aux « Primes du mois » de l'onglet « Corriger ».

Chaque élément non soumis a sa ligne, à son libellé ; une retenue sur le net
reste une ligne à part. L'indemnité reste un remboursement de frais : versée au
net, hors montant net social (BOSS, Montant net social, II, A, 1 : « Les
remboursements de frais professionnels (au réel ou forfaitaires) dans la limite
de chacun de leurs plafonds d'exonération »).
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import _lignes_hors_brut
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.frais_professionnels import (
    entree_de_frais_professionnels,
    ligne_de_frais_professionnels,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

PANIER = {
    "id": "saisie-panier",
    "name": "Indemnité panier repas",
    "amount": 40.0,
    "is_socially_taxed": False,
    "is_taxable": False,
    "catalog_prime_id": "indemnite_panier_repas",
}


def _ligne():
    return ligne_de_frais_professionnels(entree_de_frais_professionnels(PANIER))


def test_la_ligne_porte_le_libelle_de_la_saisie_et_son_identifiant():
    ligne = _ligne()

    assert ligne["libelle"] == "Indemnité panier repas"
    assert ligne["montant"] == 40.0
    # L'onglet « Corriger » liste les lignes qui portent leur saisie.
    assert ligne["saisie_id"] == "saisie-panier"


def test_le_code_export_suit_le_libelle_comme_pour_une_prime():
    entree = entree_de_frais_professionnels({**PANIER, "export_code": "SPAN"})

    assert entree["libelle"] == "Indemnité panier repas (SPAN)"


def test_versee_au_net_hors_montant_net_social():
    ctx = build_test_contexte(salaire_base=2100.0)
    ctx.year = 2026
    sans = calculer_net_et_impot(ctx, 2100.0, [], 400.0, [], 0.0, 0.0, [])
    avec = calculer_net_et_impot(ctx, 2100.0, [], 400.0, [_ligne()], 0.0, 0.0, [])

    assert avec["net_a_payer"] == pytest.approx(sans["net_a_payer"] + 40.0)
    assert avec["montant_net_social"] == pytest.approx(sans["montant_net_social"])


def test_au_bulletin_une_ligne_a_son_nom_et_la_retenue_a_part():
    bulletin = {
        "primes_non_soumises": [_ligne()],
        # La retenue de 150 € saisie « sur le net », seule dans l'acompte.
        "synthese_net": {"acompte_verse": 150.0},
    }

    lignes = {l["libelle"]: l["montant_salarial"] for l in _lignes_hors_brut(bulletin)}

    assert lignes["Indemnité panier repas"] == pytest.approx(40.0)
    assert lignes["Acomptes et avances"] == pytest.approx(-150.0)


class TestLeGenerateurNeLaRangePlusDansLAcompte:
    """Le générateur passe l'indemnité au moteur comme une ligne de frais, pas
    dans le total de l'acompte."""

    def test_entree_marquee_frais_professionnels(self):
        entree = entree_de_frais_professionnels(PANIER)

        assert entree["frais_professionnels"] is True
        assert entree["prime_id"] == "indemnite_panier_repas"
        assert entree["soumise_a_cotisations"] is False
