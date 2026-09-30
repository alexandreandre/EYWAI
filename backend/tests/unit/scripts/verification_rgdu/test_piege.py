"""Le piège bloque toute écriture Supabase et se retire proprement."""
from unittest.mock import MagicMock

import pytest

from scripts.verification_rgdu import piege

pytestmark = pytest.mark.unit


def test_une_ecriture_est_bloquee_puis_le_piege_se_retire():
    import postgrest._sync.request_builder as rb

    original = rb.SyncRequestBuilder.insert
    piege.poser_le_piege()
    try:
        with pytest.raises(piege.EcritureInterdite):
            rb.SyncRequestBuilder.insert(MagicMock(path="employee_schedules"), {})
        assert piege.ECRITURES[-1].endswith("insert employee_schedules")
    finally:
        piege.retirer_le_piege()
    assert rb.SyncRequestBuilder.insert is original


def test_poser_deux_fois_ne_double_pas_le_piege():
    piege.poser_le_piege()
    piege.poser_le_piege()
    piege.retirer_le_piege()
    import postgrest._sync.request_builder as rb

    assert not getattr(rb.SyncRequestBuilder.insert, "_piege", False)
