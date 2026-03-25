"""
Tests du service applicatif du module scraping.

Le module application/service.py est un placeholder (orchestration déléguée aux
commands et queries). On vérifie l'import et l'absence de logique exposée à tester.
"""


class TestScrapingServiceModule:
    """Présence et stabilité du module service."""

    def test_service_module_imports_without_error(self):
        """Le module service peut être importé sans erreur."""
        from app.modules.scraping.application import service

        assert service is not None
        assert hasattr(service, "__doc__")

    def test_service_has_no_public_functions_to_test(self):
        """Le service n'expose pas de fonctions publiques (logique dans commands/queries)."""
        from app.modules.scraping.application import service

        # Seuls les modules avec __doc__ et éventuellement des constantes
        public = [x for x in dir(service) if not x.startswith("_")]
        # Rien d'appelable à tester côté service
        assert len(public) <= 1  # au plus __doc__ ou rien
