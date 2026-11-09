"""R-325 : la validation ne doit pas écraser une régénération qui passe au même moment.

Elle relisait le bulletin, le contrôlait, puis réécrivait `payslip_data` : un recalcul arrivé
entre-temps repartait en base sous l'ancien contenu, marqué validé. La validation prend le verrou
de génération pour la seule écriture, et n'écrit que si le contenu en base est celui qu'elle a
contrôlé. Les contrôles et la notification restent hors du verrou : une génération n'attend pas.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.documents.verrou_generation import GenerationDejaEnCours
from app.modules.payslips.application import comparison_service as svc
from app.modules.payslips.application.dto import PayslipConflictError
from app.modules.payslips.infrastructure import comparison_queries as cq

ANCIEN = {"net_a_payer": 100.0}
RECALCULE = {"net_a_payer": 150.0}


def _detail():
    return {
        "id": "p-1",
        "employee_id": "emp-1",
        "company_id": "comp-1",
        "year": 2026,
        "month": 10,
        "status": "brouillon",
        "payslip_data": dict(ANCIEN),
    }


def _table(contenu, status="brouillon"):
    """Une table `payslips` dont la lecture rend le contenu au moment de la validation."""
    table = MagicMock()
    lecture = table.select.return_value.eq.return_value.maybe_single.return_value.execute
    lecture.return_value = MagicMock(data={"payslip_data": contenu, "status": status})
    table.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "p-1", "payslip_data": contenu}]
    )
    return table


@contextmanager
def _chaine(journal, verrou=None):
    def _prendre(*_a):
        @contextmanager
        def _ctx():
            journal.append("verrou pris")
            try:
                yield
            finally:
                journal.append("verrou rendu")

        return _ctx()

    resultat = MagicMock()
    resultat.alerts = []

    def _comparer(*_a, **_k):
        journal.append("contrôles")
        return resultat

    with (
        patch.object(svc, "payslip_meta_reader"),
        patch.object(svc, "_ensure_edit_meta"),
        patch.object(svc, "get_payslip_details", return_value=_detail()),
        patch.object(svc, "_etat_actuel_du_bulletin", return_value=None),
        patch.object(svc, "signal_a_regenerer", return_value=None),
        patch.object(svc, "raisons_de_ne_pas_valider", return_value=[]),
        patch.object(svc, "fetch_previous_validated_payslip", return_value=None),
        patch.object(svc, "fetch_employee_statut", return_value="Non-Cadre"),
        patch.object(svc, "fetch_recent_nets_asc_for_r10", return_value=[]),
        patch.object(svc, "compute_comparison", side_effect=_comparer),
        patch.object(svc, "_entre_en_cours_de_mois", return_value=False),
        patch.object(svc, "jour_de_la_societe", return_value=0),
        patch.object(svc, "verrou_de_generation", side_effect=verrou or _prendre),
    ):
        yield


def _ctx():
    ctx = MagicMock()
    ctx.user_id = "rh-1"
    return ctx


def test_un_recalcul_arrive_entre_le_controle_et_l_ecriture_n_est_pas_ecrase():
    table = _table(dict(RECALCULE))
    with _chaine([]), patch.object(cq, "supabase") as base:
        base.table.return_value = table
        with pytest.raises(PayslipConflictError, match="recalculé"):
            svc.validate_payslip_for_user("p-1", _ctx())
    table.update.assert_not_called()


def test_un_contenu_inchange_se_valide():
    table = _table(dict(ANCIEN))
    with _chaine([]), patch.object(cq, "supabase") as base, patch.object(
        svc, "_notify_payslip_available", return_value=True
    ), patch.object(svc, "_persist_salarie_notifie_le"):
        base.table.return_value = table
        svc.validate_payslip_for_user("p-1", _ctx())
    assert table.update.call_args.args[0]["status"] == "valide"


def test_un_bulletin_valide_entre_temps_n_est_pas_revalide():
    table = _table(dict(ANCIEN), status="valide")
    with _chaine([]), patch.object(cq, "supabase") as base:
        base.table.return_value = table
        with pytest.raises(PayslipConflictError):
            svc.validate_payslip_for_user("p-1", _ctx())
    table.update.assert_not_called()


def test_une_generation_en_cours_refuse_la_validation_sans_rien_ecrire():
    def occupe(*_a):
        raise GenerationDejaEnCours()

    with _chaine([], verrou=occupe), patch.object(svc, "mark_payslip_validated") as marquer:
        with pytest.raises(GenerationDejaEnCours):
            svc.validate_payslip_for_user("p-1", _ctx())
    marquer.assert_not_called()


def test_dans_un_lot_la_generation_en_cours_donne_une_raison_lisible():
    assert "génération" in svc.raison_du_refus(GenerationDejaEnCours())


def test_le_verrou_ne_couvre_ni_les_controles_ni_la_notification():
    journal: list[str] = []

    def marquer(*_a, **_k):
        journal.append("écriture")
        return {"payslip_data": dict(ANCIEN)}

    def notifier(*_a, **_k):
        journal.append("notification")
        return True

    with _chaine(journal), patch.object(
        svc, "mark_payslip_validated", side_effect=marquer
    ), patch.object(svc, "_notify_payslip_available", side_effect=notifier), patch.object(
        svc, "_persist_salarie_notifie_le"
    ):
        svc.validate_payslip_for_user("p-1", _ctx())
    assert journal == ["contrôles", "verrou pris", "écriture", "verrou rendu", "notification"]
