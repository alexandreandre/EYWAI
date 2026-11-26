"""Congé parental d'éducation à temps plein : compté pour moitié dans l'ancienneté.

C. trav. L1225-54 (code.travail.gouv.fr, version du 11/03/2023, loi n° 2023-171,
art. 18, qui n'a fait qu'y insérer « à temps plein ») : « La durée du congé
parental d'éducation à temps plein est prise en compte pour moitié pour la
détermination des droits que le salarié tient de son ancienneté. » Un seul
calcul (`jours_d_anciennete_neutralises`) : la date d'ancienneté est repoussée
de la moitié des jours de congé, pour la prime d'ancienneté, la condition du
maintien de salaire, les fériés payés, le préavis et l'indemnité de rupture.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.shared.domain.conge_parental import (
    SOUS_TYPE_CONGE_PARENTAL,
    decaler_l_anciennete,
    jours_d_anciennete_neutralises,
)

pytestmark = pytest.mark.unit


def _conge(debut: str, fin: str, **k) -> dict:
    d0, d1 = date.fromisoformat(debut), date.fromisoformat(fin)
    jours = [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
    return {"type": "sans_solde", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "selected_days": jours, **k}


def test_la_moitie_des_jours_de_conge_jusqu_a_la_date():
    conge = _conge("2026-08-26", "2027-08-25")  # 365 jours
    assert jours_d_anciennete_neutralises([conge], date(2027, 8, 31)) == 182
    assert jours_d_anciennete_neutralises([conge], date(2026, 11, 30)) == 48  # 97 jours, arrondi en faveur du salarié
    assert jours_d_anciennete_neutralises([conge], date(2026, 8, 1)) == 0


def test_ni_sans_solde_ordinaire_ni_demande_annulee():
    autres = [
        {"type": "sans_solde", "selected_days": ["2026-09-01", "2026-09-02"]},
        _conge("2026-01-01", "2026-03-31", status="cancelled"),
        {"type": "rtt", "event_subtype": SOUS_TYPE_CONGE_PARENTAL, "selected_days": ["2026-09-03"]},
    ]
    assert jours_d_anciennete_neutralises(autres, date(2026, 12, 31)) == 0


def test_la_date_d_anciennete_est_repoussee():
    assert decaler_l_anciennete(date(2025, 1, 6), 182) == date(2025, 7, 7)
    assert decaler_l_anciennete(date(2025, 1, 6), 0) == date(2025, 1, 6)
    assert decaler_l_anciennete(None, 10) is None


def _contexte(jours: int | None):
    from .helpers import build_test_contexte

    ctx = build_test_contexte(date_entree="2020-01-06")
    if jours is not None:
        ctx.contrat.setdefault("contrat", {})["jours_anciennete_neutralises"] = jours
    return ctx


def test_moteur_prime_et_maintien_et_contexte_lisent_la_meme_date():
    from app.modules.payroll.engine.maintien_salaire_service import _date_anciennete
    from app.modules.payroll.engine.prime_anciennete import _resolve_date_entree

    sans = _contexte(None)
    avec = _contexte(365)
    assert _resolve_date_entree(sans) == "2020-01-06"
    assert _resolve_date_entree(avec) == "2021-01-05"
    assert avec.date_anciennete_prime == "2021-01-05"
    assert _date_anciennete(sans) == date(2020, 1, 6)
    assert _date_anciennete(avec) == date(2021, 1, 5)


def test_les_generateurs_posent_la_neutralisation_du_mois():
    from app.modules.payroll.documents.payslip_generator import neutralisation_de_l_anciennete

    conge = _conge("2026-08-26", "2027-08-25")
    assert neutralisation_de_l_anciennete([conge], 2026, 11) == {"jours_anciennete_neutralises": 48}
    assert neutralisation_de_l_anciennete([], 2026, 11) == {}


def test_le_preavis_part_de_la_date_repoussee(monkeypatch):
    from app.modules.employee_exits.application import queries

    lus = {}

    def jours(employee_id, jusqu_au, client):
        lus["appel"] = (employee_id, jusqu_au)
        return 182

    monkeypatch.setattr(queries, "jours_neutralises_du_salarie", jours)
    assert queries.decaler_l_anciennete(date(2025, 1, 6), jours("e-1", date(2027, 9, 1), None)) == date(2025, 7, 7)
    assert lus["appel"] == ("e-1", date(2027, 9, 1))


def test_lecture_des_demandes_du_salarie():
    from unittest.mock import MagicMock

    from app.shared.infrastructure.conge_parental import jours_neutralises_du_salarie

    client = MagicMock()
    chaine = client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value
    chaine.execute.return_value.data = [_conge("2026-08-26", "2026-09-04"), {"type": "rtt", "selected_days": []}]
    assert jours_neutralises_du_salarie("e-1", date(2026, 12, 31), client) == 5
    assert jours_neutralises_du_salarie(None, date(2026, 12, 31), client) == 0
