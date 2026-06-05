"""Tests parser SMH national (métallurgie)."""

from __future__ import annotations

from app.modules.collective_agreements.rules.bareme_parser import parse_smh_national

SAMPLE_SMH_TABLE = """
Barème unique des salaires minima hiérarchiques à partir de l'année 2025

| Groupe d'emploi | Classe d'emploi | Salaire annuel brut minimum 2025 |
| A | 1 | 21 700 € |
| A | 2 | 21 850 € |
| B | 3 | 22 450 € |
| B | 4 | 23 400 € |
| C | 5 | 24 250 € |
| C | 6 | 25 550 € |
| D | 7 | 26 400 € |
| D | 8 | 28 450 € |
| E | 9 | 30 500 € |
| E | 10 | 33 700 € |
| F | 11 | 34 900 € |
| F | 12 | 36 700 € |
| G | 13 | 40 000 € |
| G | 14 | 43 900 € |
| H | 15 | 47 000 € |
| H | 16 | 52 000 € |
| I | 17 | 59 300 € |
| I | 18 | 68 000 € |
"""


class TestBaremeParser:
    def test_parse_smh_national_full_table(self):
        grille = parse_smh_national(SAMPLE_SMH_TABLE)
        assert grille is not None
        assert grille.zone_type == "national"
        assert len(grille.minima) == 18
        assert grille.minima[0].coefficient == 1.0
        assert grille.minima[0].valeur == round(21_700 / 12, 2)
        assert grille.minima[17].coefficient == 18.0
        assert grille.minima[17].valeur == round(68_000 / 12, 2)

    def test_parse_smh_returns_none_on_short_text(self):
        assert parse_smh_national("valeur du point 5,83 €") is None

    def test_parse_smh_partial_table_insufficient(self):
        partial = """
        A | 1 | 21 700 €
        A | 2 | 21 850 €
        """
        assert parse_smh_national(partial) is None
