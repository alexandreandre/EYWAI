"""Tests chaînage cumuls depuis disque."""

import json
from pathlib import Path

from app.modules.dsn_import.application.cumuls import (
    build_cumuls_for_month,
    rebuild_cumuls_with_previous_on_disk,
    write_cumuls_file,
)


def test_rebuild_cumuls_chains_from_previous_month_on_disk(tmp_path, monkeypatch):
    from app.modules.dsn_import.application import cumuls as cumuls_mod

    folder = "TEST_DSN_CHAIN"
    monkeypatch.setattr(
        cumuls_mod,
        "payroll_engine_employee_folder",
        lambda _name: tmp_path / _name,
    )

    jan_doc = build_cumuls_for_month(None, {"brut": 2000.0, "net_imposable": 1600.0, "pas": 40.0, "heures": 151.67, "reduction_generale_patronale": 0.0}, 1)
    write_cumuls_file(folder, 1, jan_doc)

    feb_totals = {"brut": 2100.0, "net_imposable": 1680.0, "pas": 42.0, "heures": 151.67, "reduction_generale_patronale": 0.0}
    fallback = build_cumuls_for_month(None, feb_totals, 2)
    rebuilt = rebuild_cumuls_with_previous_on_disk(folder, 2, feb_totals, fallback)

    assert rebuilt["cumuls"]["brut_total"] == 4100.0
    assert rebuilt["periode"]["dernier_mois_calcule"] == 2
