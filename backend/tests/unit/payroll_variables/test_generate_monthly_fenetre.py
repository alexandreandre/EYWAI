"""Les règles de variables comptent sur la fenêtre, pas sur le mois civil."""

from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.unit


def test_bornes_variables_suivent_le_service(monkeypatch):
    from app.modules.payroll_variables.application import generate_monthly as gm
    from app.shared.domain.periode_variables import FenetreVariables

    monkeypatch.setattr(
        gm,
        "resoudre_fenetre_variables",
        lambda cid, a, m: FenetreVariables(
            debut=date(2026, 6, 22), fin=date(2026, 7, 19), origine="manuel"
        ),
    )
    assert gm._bornes_variables("c1", 2026, 7) == (date(2026, 6, 22), date(2026, 7, 19))


def test_repli_sur_le_mois_si_la_resolution_echoue(monkeypatch):
    from app.modules.payroll_variables.application import generate_monthly as gm

    def _boum(cid, a, m):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(gm, "resoudre_fenetre_variables", _boum)
    assert gm._bornes_variables("c1", 2026, 7) == (date(2026, 7, 1), date(2026, 7, 31))
