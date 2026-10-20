"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_un_matricule_inconnu_dit_qu_aucun_employe_actif_ne_le_porte(sans_ligne):
    from app.modules.badgeuse.application import qr_service

    sans_ligne()
    with pytest.raises(ValueError, match="Aucun employé actif"):
        qr_service.punch_by_username(username="inconnu", company_id="c", actor_user_id="u")


def test_l_etat_du_terminal_sans_societe_lue_reste_vide(sans_ligne):
    from types import SimpleNamespace

    from app.modules.badgeuse.api import terminal_router

    sans_ligne()
    etat = terminal_router.get_terminal_status(
        ctx=SimpleNamespace(company_id="c", device_id="d", label="Atelier", device_label="Atelier")
    )
    assert etat["company_name"] is None
