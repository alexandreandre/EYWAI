"""
Tests d'intégration du repository du module contract_parser.

Le module contract_parser n'expose actuellement aucun repository avec opérations
CRUD ou métier (pas de persistance des extractions). Le fichier infrastructure/repository.py
est un placeholder.
Ces tests vérifient l'import et la cohérence du module ; dès qu'un repository
sera implémenté (ex. sauvegarde des résultats d'extraction en DB), ajouter ici
les tests contre une DB de test (fixture db_session).
"""
import pytest

from app.modules.contract_parser.infrastructure import repository as repo_module


pytestmark = pytest.mark.integration


class TestContractParserRepositoryModule:
    """Module infrastructure.repository : état actuel (placeholder)."""

    def test_repository_module_exists(self):
        """Le sous-module infrastructure.repository existe et est importable."""
        assert repo_module is not None

    def test_repository_has_no_crud_attributes(self):
        """Aucune fonction CRUD ou instance de repository exposée pour l'instant."""
        # Le module ne définit pas de repository injectable ni de fonctions save/get
        public = [x for x in dir(repo_module) if not x.startswith("_")]
        # Pas de save_extraction, get_by_id, etc.
        assert "save_extraction" not in public
        assert "get_by_id" not in public

    def test_db_session_fixture_documentation(self):
        """
        Documente la fixture db_session pour de futurs tests repository.

        Quand un repository contract_parser sera implémenté avec une DB :
        - Utiliser la fixture db_session (conftest.py) pour une connexion de test.
        - Ajouter des tests du type : sauvegarde d'un résultat d'extraction,
          lecture par id, liste par company_id, etc.
        """
        # Test factice pour documenter l'intention ; aucun appel DB ici
        assert True
