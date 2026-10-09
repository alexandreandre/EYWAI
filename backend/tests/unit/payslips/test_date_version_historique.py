"""La date d'une version de l'historique porte son fuseau.

Écrite sans décalage (`datetime.now().isoformat()`), elle était lue par le
navigateur à son heure locale : une version créée à 00:05 à Paris le 10/10
s'affichait « 9 octobre » à « 22:05 », l'heure UTC du serveur.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.modules.payslips.application import commands as mod


def test_la_version_archivee_est_datee_en_utc_avec_son_fuseau():
    supabase = MagicMock()
    existant = {"id": "ps-1", "edit_history": [], "payslip_data": {}, "url": None}
    with (
        patch.object(mod, "supabase", supabase),
        patch("app.modules.payslips.application.impression.supprimer_pdfs"),
    ):
        mod.archiver_version(
            existant,
            edited_by=None,
            edited_by_name=None,
            changes_summary="test",
            action="regeneration",
        )
    payload = supabase.table.return_value.update.call_args.args[0]
    date = datetime.fromisoformat(payload["edit_history"][-1]["edited_at"])
    assert date.utcoffset() == timedelta(0)
