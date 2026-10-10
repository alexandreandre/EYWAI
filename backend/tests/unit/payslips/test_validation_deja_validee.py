"""Valider un bulletin déjà validé : un message clair, rien de refait.

Avant, la route revalidait en silence : nouvelle date de validation, salarié
renotifié peut-être, sans que la gestionnaire sache que c'était déjà fait.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.application import comparison_service as svc
from app.modules.payslips.application.dto import PayslipConflictError


def _detail(**en_plus):
    return {
        "id": "p-1",
        "employee_id": "emp-1",
        "company_id": "comp-1",
        "year": 2026,
        "month": 9,
        "status": "valide",
        "validated_at": "2026-10-06T07:30:00+00:00",
        "validated_by": "u-1",
        "payslip_data": {"net_a_payer": 100},
        **en_plus,
    }


def _valider(detail, noms):
    with (
        patch.object(svc, "payslip_meta_reader") as meta,
        patch.object(svc, "_ensure_edit_meta"),
        patch.object(svc, "get_payslip_details", return_value=detail),
        patch.object(svc, "fetch_noms_utilisateurs", return_value=noms),
        patch.object(svc, "mark_payslip_validated") as marquer,
        patch.object(svc, "_notify_payslip_available") as notifier,
    ):
        meta.get_payslip_meta.return_value = {"id": "p-1"}
        ctx = MagicMock()
        ctx.user_id = "rh-1"
        try:
            svc.validate_payslip_for_user("p-1", ctx)
        finally:
            fait = marquer.called or notifier.called
    return fait


def test_un_bulletin_deja_valide_dit_quand_et_par_qui_sans_rien_refaire():
    with pytest.raises(svc.PayslipDejaValideError) as exc:
        _valider(_detail(), {"u-1": "Camille Test"})
    assert str(exc.value) == (
        "Ce bulletin est déjà validé depuis le 6 octobre 2026 à 09:30, par Camille Test. "
        "Rien n'a été refait."
    )


def test_sans_nom_lisible_la_phrase_reste_vraie():
    with pytest.raises(svc.PayslipDejaValideError) as exc:
        _valider(_detail(), {})
    assert str(exc.value) == (
        "Ce bulletin est déjà validé depuis le 6 octobre 2026 à 09:30. Rien n'a été refait."
    )


def test_rien_n_est_refait_ni_notifie():
    with pytest.raises(svc.PayslipDejaValideError):
        fait = _valider(_detail(), {"u-1": "Camille Test"})
    # `_valider` n'atteint pas son `return` : on relit l'effet par un second appel.
    with (
        patch.object(svc, "payslip_meta_reader") as meta,
        patch.object(svc, "_ensure_edit_meta"),
        patch.object(svc, "get_payslip_details", return_value=_detail()),
        patch.object(svc, "fetch_noms_utilisateurs", return_value={}),
        patch.object(svc, "mark_payslip_validated") as marquer,
        patch.object(svc, "_notify_payslip_available") as notifier,
        pytest.raises(svc.PayslipDejaValideError),
    ):
        meta.get_payslip_meta.return_value = {"id": "p-1"}
        svc.validate_payslip_for_user("p-1", MagicMock())
    marquer.assert_not_called()
    notifier.assert_not_called()


def test_c_est_un_conflit_http_409_et_une_raison_de_refus_du_lot():
    erreur = svc.PayslipDejaValideError("Ce bulletin est déjà validé.")
    assert isinstance(erreur, PayslipConflictError)
    assert svc.raison_du_refus(erreur) == "Ce bulletin est déjà validé."
