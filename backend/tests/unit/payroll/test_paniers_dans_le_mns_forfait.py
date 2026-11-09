"""R-333 : le réglage « paniers non soumis dans le MNS » vaut aussi au forfait.

Lu seulement côté heures, il laissait au forfait jours le panier repas hors du
montant net social, quel que soit le réglage de la société. Aucun forfait avec
panier en base au 08/11/2026 : aucun montant existant ne bouge.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.payroll.documents import payslip_generator as heures
from app.modules.payroll.documents import payslip_generator_forfait as forfait
from app.modules.payroll.engine.frais_professionnels import entree_de_frais_professionnels

pytestmark = pytest.mark.unit

PANIER = {"name": "Panier repas", "description": "", "amount": 30.0, "catalog_prime_id": None}
AUTRE = {"name": "Indemnité trajet", "description": "", "amount": 12.0, "catalog_prime_id": None}
AVEC = {"settings": {"paniers_non_soumis_dans_mns": True}}
SANS = {"settings": {}}


def test_panier_avec_le_reglage_entre_dans_le_mns():
    entree = heures.entree_de_frais_non_soumis(PANIER, AVEC)
    assert entree != entree_de_frais_professionnels(PANIER)
    assert entree["soumise_a_cotisations"] is False
    assert entree["soumise_a_impot"] is False
    assert entree["montant"] == 30.0


def test_sans_le_reglage_le_panier_reste_hors_mns():
    assert heures.entree_de_frais_non_soumis(PANIER, SANS) == entree_de_frais_professionnels(PANIER)


def test_un_frais_qui_n_est_pas_un_panier_reste_hors_mns():
    assert heures.entree_de_frais_non_soumis(AUTRE, AVEC) == entree_de_frais_professionnels(AUTRE)


def test_le_forfait_lit_le_meme_reglage():
    assert "entree_de_frais_non_soumis(row, company_data)" in Path(forfait.__file__).read_text(encoding="utf-8")
