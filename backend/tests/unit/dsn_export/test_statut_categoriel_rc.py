"""Statut catégoriel de retraite complémentaire (S21.G00.40.003).

Couples relevés dans 301 DSN acceptées du cabinet : 04/01, 06/04, et le statut conventionnel 05
sous deux formes, 05/02 et 05/04. Seule la fiche les distingue.
"""
import pytest

from app.modules.dsn_export.domain.contract_map import map_statut_categoriel_rc


@pytest.mark.parametrize(
    ("conventionnel", "fiche_cadre", "attendu"),
    [
        ("04", True, "01"),
        ("05", True, "02"),
        ("05", False, "04"),
        ("06", False, "04"),
        ("07", False, "04"),
    ],
)
def test_le_statut_de_retraite_suit_le_conventionnel_et_la_fiche(conventionnel, fiche_cadre, attendu):
    assert map_statut_categoriel_rc(conventionnel, fiche_cadre=fiche_cadre) == attendu


def test_sans_la_fiche_un_statut_05_reste_non_cadre():
    assert map_statut_categoriel_rc("05") == "04"
