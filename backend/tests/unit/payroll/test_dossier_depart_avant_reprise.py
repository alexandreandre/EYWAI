"""Départ payé par l'ancien logiciel : le dossier recompte les congés sans la reprise.

La reprise des congés d'une société est datée de la fin du dernier mois payé
par l'ancien logiciel. Son solde d'ouverture vient de ce bulletin, après le
solde de tout compte : le logiciel a payé les congés et son compteur affiche 0
(bulletin de septembre de Quadra : « CP N acquis 0,00 / solde 0,00 »). Un
départ daté au plus tard de la reprise ne peut pas lire ses droits dans ce
compteur : Martine les recompte depuis l'entrée (L3141-3, L1242-16) et le dit.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.application import queries
from app.modules.absences.domain.leave_policy import EmployeeLeaveAdjustment
from app.modules.payroll.engine import calcul_indemnites_sortie as module

pytestmark = pytest.mark.unit

EMPLOYE = "11111111-1111-1111-1111-111111111111"
REPRISE = EmployeeLeaveAdjustment(
    cp_n1_opening_balance=0.0,
    cp_n_opening_balance=-6.38,
    rtt_opening_balance=0.0,
    rtt_forfeited_at=None,
    rtt_forfeited_days=0.0,
    jtc_opening_balance=0.0,
    note="Reprise : bulletin de 09/2026",
    cp_opening_reference_date=date(2026, 9, 30),
)
COMPTEURS = {"conges_payes": {"pris": 0.0, "solde": 6.38, "periode": "01/06/2026 – 31/05/2027"}}
CUMULS_DE_SEPTEMBRE = {
    "cumuls": {"brut_reference_n_1": 6272.73, "brut_reference_period_start": "2026-06-01"}
}


def _dossier(depart: date):
    with (
        patch(
            "app.modules.absences.infrastructure.planning_cp_repository.get_cp_opening_reference_dates",
            return_value={EMPLOYE: REPRISE.cp_opening_reference_date},
        ),
        patch(
            "app.modules.absences.application.queries.get_absence_balances_for_payslip",
            return_value=COMPTEURS,
        ) as compteurs,
        patch.object(module, "_cumuls_du_mois_precedent", return_value=CUMULS_DE_SEPTEMBRE),
        patch(
            "app.modules.payroll.documents.payslip_run_heures._brut_de_la_periode_precedente",
            return_value=None,
        ),
    ):
        cfg = module._conges_par_periode_a_la_sortie(
            EMPLOYE, depart, MagicMock(), entree=date(2026, 6, 29), salaire=3000.0
        )
    return cfg, compteurs.call_args.kwargs


def test_un_depart_a_la_date_de_la_reprise_recompte_sans_elle_et_le_dit():
    cfg, appel = _dossier(date(2026, 9, 30))

    assert appel["sans_la_reprise"] is True
    assert any("ancien logiciel" in a and "30/09/2026" in a for a in cfg["alertes"])


def test_un_depart_apres_la_reprise_lit_les_compteurs_repris():
    cfg, appel = _dossier(date(2026, 10, 31))

    assert appel.get("sans_la_reprise", False) is False
    assert not cfg.get("alertes")


class _Arret(Exception):
    pass


def test_sans_la_reprise_les_compteurs_partent_d_un_ajustement_vide_et_du_planning_entier(monkeypatch):
    """Départ au 30/06, reprise au 30/09. Le compteur d'un mois antérieur à la reprise se calcule (pas de case
    vide), sur un ajustement vide, et le planning garde ses congés d'avant la
    reprise (le solde repris ne les absorbe plus)."""
    monkeypatch.setattr(queries, "_parse_hire_date", lambda _id: date(2026, 6, 29))
    monkeypatch.setattr(
        queries, "get_cp_opening_reference_dates", lambda ids: {EMPLOYE: date(2026, 9, 30)}, raising=False
    )
    monkeypatch.setattr(queries, "_date_de_sortie", lambda _id: date(2026, 6, 30))
    lectures = []

    def _planning(ids, **kw):
        lectures.append(kw)
        return []

    monkeypatch.setattr(queries.absence_repository, "list_validated_for_employees", _planning)
    monkeypatch.setattr(queries, "get_repos_credits_by_employee_year", lambda ids, annee: {})
    monkeypatch.setattr(queries, "_leave_context", lambda *_a, **_k: (None, REPRISE, 0, None))
    monkeypatch.setattr(queries, "_cp_balance_extras", lambda *_a, **_k: {})
    vus = []

    def _calcul(*_a, adjustment=None, **_k):
        vus.append(adjustment)
        raise _Arret

    monkeypatch.setattr(queries, "compute_cp_balances_for_bulletin", _calcul)

    with pytest.raises(_Arret):
        queries.get_absence_balances_for_payslip(
            EMPLOYE, 2026, 6, date_de_sortie=date(2026, 6, 30), sans_la_reprise=True
        )

    assert lectures == [{"avec_coupure_de_reprise": False}]
    assert vus == [EmployeeLeaveAdjustment.empty()]


def test_la_phrase_de_l_ancien_logiciel_reste_quand_la_base_se_lit_sur_les_bulletins():
    from app.shared.domain.dixieme_conges import BaseDixieme
    with (
        patch(
            "app.modules.absences.infrastructure.planning_cp_repository.get_cp_opening_reference_dates",
            return_value={EMPLOYE: REPRISE.cp_opening_reference_date},
        ),
        patch("app.modules.absences.application.queries.get_absence_balances_for_payslip", return_value=COMPTEURS),
        patch.object(module, "_cumuls_du_mois_precedent", return_value=None),
        patch("app.modules.payroll.documents.payslip_run_heures._brut_de_la_periode_precedente", return_value=None),
        patch("app.modules.payroll.infrastructure.reference_dixieme.base_de_reference", return_value=BaseDixieme(None, alertes=("Bulletin 06/2026 absent : rémunération du dixième inconnue.",))),
    ):
        cfg = module._conges_par_periode_a_la_sortie(
            EMPLOYE, date(2026, 9, 30), MagicMock(), entree=date(2026, 6, 29), salaire=3000.0
        )

    assert any("ancien logiciel" in a for a in cfg["alertes"])
    assert "Bulletin 06/2026 absent : rémunération du dixième inconnue." in cfg["alertes"]
    assert cfg["periode_en_cours"]["brut_avant_mois"] is None


def test_la_date_de_reprise_est_celle_des_compteurs_toutes_annees_confondues():
    """Même source que la garde des compteurs (`get_cp_opening_reference_dates`) :
    une reprise rangée sur l'année suivante compte aussi."""
    with patch(
        "app.modules.absences.infrastructure.planning_cp_repository.get_cp_opening_reference_dates",
        return_value={EMPLOYE: date(2027, 1, 31)},
    ):
        assert module._date_de_reprise_des_conges(EMPLOYE) == date(2027, 1, 31)


def test_sans_compteurs_le_dossier_ne_lit_aucun_bulletin():
    with (
        patch.object(module, "_date_de_reprise_des_conges", return_value=None),
        patch("app.modules.absences.application.queries.get_absence_balances_for_payslip", return_value=None),
        patch.object(module, "_cumuls_du_mois_precedent", return_value=None),
        patch.object(module, "bruts_du_contrat") as bruts,
    ):
        assert module._conges_par_periode_a_la_sortie(EMPLOYE, date(2026, 9, 30), MagicMock()) is None
    bruts.assert_not_called()
