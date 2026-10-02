"""Un relevé déjà importé : la phrase dit où sont les heures et quoi faire, sans jargon."""

from unittest.mock import patch

import pytest

from app.modules.schedules.application.timesheet_import import cache_service


def test_un_releve_deja_importe_dit_quoi_faire():
    with patch.object(cache_service, "check_file_hash_committed", return_value="batch-1"):
        with pytest.raises(Exception) as refus:
            cache_service.assert_not_committed_duplicate("co-1", "abc")
    message = str(getattr(refus.value, "message", refus.value))
    assert "hash" not in message
    assert "déjà été importé" in message
    assert "calendrier" in message
    assert getattr(refus.value, "status_code", None) == 409
