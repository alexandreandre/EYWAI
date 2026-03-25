"""
Tests unitaires du domaine auth : règles métier et constantes.

Pas d'entités ni de value objects dans ce module (placeholders vides).
On teste uniquement domain/rules.py (règles pures, sans DB ni HTTP).
"""

from app.modules.auth.domain.rules import RESET_TOKEN_VALIDITY_HOURS, is_email_like


class TestResetTokenValidityHours:
    """Constante de validité du token de réinitialisation."""

    def test_reset_token_validity_hours_is_positive(self):
        """La durée de validité doit être un entier positif (heures)."""
        assert RESET_TOKEN_VALIDITY_HOURS >= 0
        assert isinstance(RESET_TOKEN_VALIDITY_HOURS, int)

    def test_reset_token_validity_hours_has_reasonable_value(self):
        """La durée doit être raisonnable pour la sécurité (ex. 1 à 24 h)."""
        assert 1 <= RESET_TOKEN_VALIDITY_HOURS <= 24


class TestIsEmailLike:
    """Règle pure is_email_like : détection d'une chaîne ressemblant à un email."""

    def test_contains_at_returns_true(self):
        """Une chaîne contenant @ est considérée comme email."""
        assert is_email_like("user@example.com") is True
        assert is_email_like("a@b") is True
        assert is_email_like("@") is True

    def test_no_at_returns_false(self):
        """Une chaîne sans @ n'est pas considérée comme email (ex. username)."""
        assert is_email_like("username") is False
        assert is_email_like("") is False
        assert is_email_like("login123") is False

    def test_empty_string(self):
        """Chaîne vide ne contient pas @."""
        assert is_email_like("") is False

    def test_whitespace_only_no_at(self):
        """Espaces seuls sans @."""
        assert is_email_like("   ") is False

    def test_email_with_subdomain(self):
        """Email avec sous-domaine contient @."""
        assert is_email_like("user@mail.example.com") is True
