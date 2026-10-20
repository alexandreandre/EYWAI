"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_les_lectures_d_import_rendent_l_absence_sans_planter(sans_ligne):
    from app.modules.schedules.application import timesheet_import_service as service
    from app.modules.schedules.infrastructure import timesheet_import_repository as depot

    sans_ligne(depot, service, accesseurs=("_admin", "_db"))
    lot = depot.TimesheetImportRepository()
    assert lot.get_batch("x") is None
    assert lot.is_cancel_requested("x") is False
    assert lot.request_cancel_batch("x") == {"status": "unknown", "cancel_requested": False}
    assert lot.get_profile("c", "profil", "csv") is None
    assert service.get_import_job("x") is None
    assert service._job_is_terminal("x") is False
