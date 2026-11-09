"""Un rappel de maintien rétablit le SMIC des mois d'arrêt qu'il paie.

Un arrêt sort du SMIC de référence à proportion du salaire que l'employeur n'a
pas maintenu (CSS D241-7, IV, 5e alinéa). Payé plus tard, le maintien en
rétablit la part, le mois où la paie en tient compte (BOSS, allègements
généraux, § 800), comme le fait Quadra (Comitech, septembre 2026). Martine
ajoutait le rappel au brut sans ces heures : octobre 2026, la réduction de M.G.
(Colorplast) se remboursait (−606,28 € au lieu de +1 524,86 €), celles de trois
salariés de Comitech baissaient de 704,98 €. Faute des heures dans le cumul, une
correction du seul montant aurait été reprise le mois suivant.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.calcul_reduction_generale import (
    PRIME_RAPPEL_MAINTIEN,
    heures_retablies_par_les_rappels_de_maintien,
    signaler_rappels_de_maintien_en_prime_libre,
)

pytestmark = pytest.mark.unit


def _rappel(montant: float) -> dict:
    return {"prime_id": PRIME_RAPPEL_MAINTIEN, "libelle": "Rappel maintien de salaire", "montant": montant}


def test_un_rappel_rend_les_heures_du_salaire_qu_il_paie():
    # 39 h, 2 400 € le mois complet : 600 € de rappel paient un quart du mois.
    assert heures_retablies_par_les_rappels_de_maintien([_rappel(600.0)], 169.0, 2400.0) == 42.25


def test_les_rappels_du_mois_s_additionnent():
    primes = [_rappel(457.12), _rappel(1048.32)]
    assert heures_retablies_par_les_rappels_de_maintien(primes, 151.67, 2000.0) == round(
        151.67 * 1505.44 / 2000.0, 2
    )


def test_une_autre_prime_ne_rend_aucune_heure():
    primes = [{"prime_id": "prime_exceptionnelle", "libelle": "Rappel maintien de salaire", "montant": 500.0}]
    assert heures_retablies_par_les_rappels_de_maintien(primes, 151.67, 2000.0) == 0.0


def test_un_trop_verse_repris_retire_les_heures():
    # Maintien versé en trop puis repris : le SMIC suit la paie dans les deux sens.
    assert heures_retablies_par_les_rappels_de_maintien([_rappel(-200.0)], 151.67, 2000.0) == -15.17


def test_sans_salaire_de_mois_complet_aucune_heure():
    assert heures_retablies_par_les_rappels_de_maintien([_rappel(600.0)], 151.67, 0.0) == 0.0


def _contexte() -> SimpleNamespace:
    return SimpleNamespace(alertes_baremes=[])


def test_un_rappel_de_maintien_en_prime_libre_se_signale():
    """R-277 : saisi hors catalogue, le rappel entre au brut sans ses heures de SMIC."""
    contexte = _contexte()
    primes = [{"prime_id": "rappel_maintien_du_12_09", "libelle": "Rappel maintien du 12/09", "montant": 650.0}]
    signaler_rappels_de_maintien_en_prime_libre(contexte, primes)
    alerte = contexte.alertes_baremes[0]
    assert alerte["code"] == "rappel_maintien_prime_libre"
    assert not alerte.get("critique")
    assert "Rappel maintien du 12/09" in alerte["message"]
    assert "réduction générale" in alerte["message"]
    assert "catalogue" in alerte["message"]


def test_une_regularisation_de_maintien_aussi():
    contexte = _contexte()
    signaler_rappels_de_maintien_en_prime_libre(
        contexte, [{"prime_id": "regul_maintien", "libelle": "Régul. maintien de salaire", "montant": 100.0}]
    )
    assert contexte.alertes_baremes


def test_la_prime_du_catalogue_ne_se_signale_pas():
    contexte = _contexte()
    signaler_rappels_de_maintien_en_prime_libre(contexte, [_rappel(600.0)])
    assert contexte.alertes_baremes == []


def test_une_prime_ordinaire_ne_se_signale_pas():
    contexte = _contexte()
    signaler_rappels_de_maintien_en_prime_libre(
        contexte, [{"prime_id": "prime_de_jeu", "libelle": "Prime de jeu", "montant": 80.0}]
    )
    assert contexte.alertes_baremes == []


@pytest.mark.parametrize("module", ["payslip_run_heures", "payslip_run_forfait"])
def test_les_deux_calculs_signalent_le_rappel(module):
    source = (
        Path(__file__).resolve().parents[3] / f"app/modules/payroll/documents/{module}.py"
    ).read_text(encoding="utf-8")
    assert "signaler_rappels_de_maintien_en_prime_libre(contexte, primes_soumises)" in source
