"""Quels bulletins relire, qui peut lancer, combien ça coûte."""

from __future__ import annotations

import pytest

from app.modules.relecture_ia.domain.cout import cout_usd, estimer_cout_eur
from app.modules.relecture_ia.domain.droits import compte_autorise
from app.modules.relecture_ia.domain.selection import bulletins_a_relire

pytestmark = pytest.mark.unit


def _bulletin(i: str, maj: str, kind=None) -> dict:
    return {"id": i, "updated_at": maj, "bulletin_kind": kind}


class TestSelection:
    def test_jamais_relu_est_a_relire(self):
        assert [b["id"] for b in bulletins_a_relire([_bulletin("a", "2026-11-01T10:00:00+00:00")], {})] == ["a"]

    def test_inchange_depuis_la_derniere_relecture_est_ignore(self):
        b = _bulletin("a", "2026-11-01T10:00:00+00:00")
        assert bulletins_a_relire([b], {"a": "2026-11-01T10:00:00+00:00"}) == []

    def test_meme_instant_ecrit_autrement_est_ignore(self):
        b = _bulletin("a", "2026-11-01T10:00:00Z")
        assert bulletins_a_relire([b], {"a": "2026-11-01T11:00:00+01:00"}) == []

    def test_modifie_depuis_est_a_relire(self):
        b = _bulletin("a", "2026-11-01T10:00:01+00:00")
        assert len(bulletins_a_relire([b], {"a": "2026-11-01T10:00:00+00:00"})) == 1

    def test_date_illisible_est_a_relire(self):
        assert len(bulletins_a_relire([_bulletin("a", "demain")], {"a": "hier"})) == 1

    def test_regularisation_exclue(self):
        b = _bulletin("a", "2026-11-01T10:00:00Z", kind="regularisation_participation")
        assert bulletins_a_relire([b], {}) == []


class TestDroits:
    def test_defaut(self):
        assert compte_autorise("eandre@maji-invest.fr", None)

    def test_casse_et_espaces(self):
        assert compte_autorise(" EAndre@Maji-Invest.FR ", " autre@exemple.fr , eandre@maji-invest.fr ")

    def test_refus(self):
        assert not compte_autorise("autre@exemple.fr", None)

    def test_compte_sans_email(self):
        assert not compte_autorise(None, None)
        assert not compte_autorise("", "")


class TestCout:
    def test_au_tarif_du_modele(self):
        usage = {
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "cache_read_input_tokens": 1_000_000,
            "cache_creation_input_tokens": 1_000_000,
        }
        assert cout_usd(usage) == pytest.approx(4 + 20 + 0.2 + 8)

    def test_estimation_croit_avec_les_bulletins(self):
        assert estimer_cout_eur(0) == 0
        assert 0 < estimer_cout_eur(1) < estimer_cout_eur(100)
