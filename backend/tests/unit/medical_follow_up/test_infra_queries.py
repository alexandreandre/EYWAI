"""
Tests unitaires des requêtes d'infrastructure medical_follow_up.

Client Supabase mocké ; pas de DB.
"""

from unittest.mock import MagicMock

from app.modules.medical_follow_up.infrastructure import queries as infra_queries


def _mock_supabase():
    """Client Supabase mock exposant la chaîne table().update().eq().execute()."""
    supabase = MagicMock()
    table = supabase.table.return_value
    table.update.return_value.eq.return_value.execute.return_value = None
    return supabase, table


class TestUpdateObligationCompleted:
    """Écriture d'une visite réalisée."""

    def test_writes_amenagement_poste_true(self):
        """La case cochée est persistée avec le reste de la visite."""
        supabase, table = _mock_supabase()
        infra_queries.update_obligation_completed(
            supabase, "obl-1", "2026-08-02", "Visite effectuée", True
        )
        supabase.table.assert_called_once_with("medical_follow_up_obligations")
        table.update.assert_called_once_with(
            {
                "status": "realisee",
                "completed_date": "2026-08-02",
                "justification": "Visite effectuée",
                "amenagement_poste": True,
            }
        )
        table.update.return_value.eq.assert_called_once_with("id", "obl-1")

    def test_writes_amenagement_poste_false(self):
        """Case décochée : la colonne est remise à False, jamais laissée telle quelle."""
        supabase, table = _mock_supabase()
        infra_queries.update_obligation_completed(
            supabase, "obl-1", "2026-08-02", None, False
        )
        table.update.assert_called_once_with(
            {
                "status": "realisee",
                "completed_date": "2026-08-02",
                "justification": None,
                "amenagement_poste": False,
            }
        )
