"""
Tests des enums du domaine Copilot.

Sans DB ni HTTP.
"""

import pytest

from app.modules.copilot.domain.enums import MessageRole


pytestmark = pytest.mark.unit


class TestMessageRole:
    """Enum des rôles de message (aligné OpenAI)."""

    def test_user_value(self):
        assert MessageRole.USER == "user"

    def test_assistant_value(self):
        assert MessageRole.ASSISTANT == "assistant"

    def test_system_value(self):
        assert MessageRole.SYSTEM == "system"

    def test_all_members_exist(self):
        assert set(MessageRole) == {
            MessageRole.USER,
            MessageRole.ASSISTANT,
            MessageRole.SYSTEM,
        }

    def test_string_usage(self):
        """Les valeurs sont des str, utilisables directement dans l'API."""
        assert isinstance(MessageRole.USER.value, str)
        assert MessageRole.USER.value == "user"
