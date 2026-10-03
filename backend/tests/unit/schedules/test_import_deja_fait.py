"""Un relevé déjà importé : la phrase dit où sont les heures et quoi faire, sans jargon."""

from unittest.mock import patch

import pytest

from app.modules.schedules.application.timesheet_import import reimport_service


def test_un_releve_deja_importe_dit_quoi_faire():
    lot = {"id": "batch-1", "filename": "releve.csv", "summary_json": {}}
    with patch.object(reimport_service, "timesheet_import_repository") as repo:
        repo.lots_valides_du_fichier.return_value = [lot]
        repo.nom_utilisateur.return_value = None
        with pytest.raises(Exception) as refus:
            reimport_service.verifier_import(
                "co-1", [("releve.csv", "abc")], refaire_import=False
            )
    message = str(getattr(refus.value, "message", refus.value))
    assert "hash" not in message
    assert "déjà été importé" in message
    assert "calendrier" in message
    assert "Refaire l'import de ce fichier" in message
    assert getattr(refus.value, "status_code", None) == 409
