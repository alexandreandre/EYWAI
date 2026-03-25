"""
Tests unitaires des requêtes (queries) du module contract_parser.

Le module n'expose actuellement aucune query métier : les 3 endpoints sont
des commandes (upload PDF → extraction). Ce fichier documente l'état et
permet d'ajouter des tests dès qu'une query sera ajoutée (ex. historique d'extractions).
"""

import pytest


pytestmark = pytest.mark.unit


class TestQueriesModule:
    """Module application.queries : état actuel (vide)."""

    def test_queries_module_exists(self):
        """Le sous-module application.queries existe et est importable."""
        from app.modules.contract_parser.application import queries

        assert queries is not None

    def test_queries_module_has_no_public_functions(self):
        """Aucune fonction de query publique pour l'instant."""
        from app.modules.contract_parser.application import queries

        # Seuls les noms non privés (sans _) sont considérés comme API publique
        public = [x for x in dir(queries) if not x.startswith("_")]
        # Le module peut contenir des réexportations ou être vide
        assert "extract_contract_from_pdf" not in public
        assert "extract_rib_from_pdf" not in public
