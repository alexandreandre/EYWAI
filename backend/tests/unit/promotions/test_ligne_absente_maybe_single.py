"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


SALARIE = {"id": "e", "user_id": "u", "job_title": "Opérateur", "contract_type": "CDI", "statut": "Non-Cadre"}


def test_le_snapshot_d_un_salarie_sans_acces_rh_dit_aucun_acces(sans_ligne):
    from app.modules.promotions.infrastructure import queries

    sans_ligne(queries, lignes={"employees": SALARIE})
    snapshot = queries.get_employee_snapshot_for_promotion("e", "c")
    assert snapshot["previous_rh_access"] is None


def test_l_acces_rh_d_un_salarie_sans_acces_est_vide(sans_ligne):
    from app.modules.promotions.infrastructure import queries

    sans_ligne(queries, lignes={"employees": SALARIE})
    acces = queries.PromotionQueries().get_employee_rh_access("e", "c")
    assert acces.has_access is False
