"""Une erreur interne de génération ne montre jamais son texte technique.

Le serveur renvoyait `str(e)` : « list index out of range » arrivait tel quel
sur l'écran de la gestionnaire. Le détail reste dans les journaux ; l'écran
reçoit une phrase qui dit quoi faire. Le refus « pas en forfait jour » ne
parle plus du « générateur heures » ni du nom de dossier du salarié.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.payslips.api import router as r
from app.modules.payslips.schemas import PayslipRequest

_R = "app.modules.payslips.api.router."


def test_la_route_de_generation_ne_laisse_pas_passer_le_texte_technique():
    requete = PayslipRequest(employee_id="emp-1", year=2026, month=9)
    utilisateur = SimpleNamespace(id="u", first_name="A", last_name="B", active_company_id="co-1")
    with (
        patch(_R + "_require_rh_company_context", return_value="co-1"),
        patch(_R + "access_control_service"),
        patch(_R + "generate_payslip", side_effect=IndexError("list index out of range")),
        pytest.raises(HTTPException) as exc,
    ):
        r.generate_payslip_route(requete, current_user=utilisateur)
    assert exc.value.status_code == 500
    assert "index" not in str(exc.value.detail).lower()
    assert "range" not in str(exc.value.detail).lower()
    assert exc.value.detail == r.MESSAGE_ERREUR_GENERATION


def test_le_message_generique_dit_quoi_faire():
    assert "Réessayez" in r.MESSAGE_ERREUR_GENERATION
    assert "Martine" in r.MESSAGE_ERREUR_GENERATION


def test_le_refus_forfait_jour_ne_parle_ni_de_generateur_ni_de_dossier():
    from app.modules.payroll.documents.payslip_run_forfait import message_pas_forfait_jour

    message = message_pas_forfait_jour()
    assert "générateur" not in message
    assert "dossier" not in message.lower()
    assert "forfait jour" in message
