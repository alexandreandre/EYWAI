"""Runtime paie : racine sous ``app/``, templates présents, pas de dossier legacy."""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_payroll_engine_root_is_under_app_package():
    from app.core import paths

    app_dir = Path(paths.__file__).resolve().parent.parent
    root = paths.payroll_engine_root().resolve()
    try:
        root.relative_to(app_dir)
    except ValueError as e:
        raise AssertionError(
            f"payroll_engine_root() doit être sous {app_dir}, obtenu: {root}"
        ) from e


def test_payroll_engine_root_not_backend_calculs():
    from app.core.paths import payroll_engine_root

    assert "backend_calculs" not in payroll_engine_root().resolve().parts


def test_path_aliases_match():
    from app.core.paths import PATH_TO_PAYROLL_ENGINE, PAYROLL_ENGINE_ROOT

    assert PATH_TO_PAYROLL_ENGINE == PAYROLL_ENGINE_ROOT


def test_payroll_engine_templates_contain_bulletin_template():
    from app.core.paths import payroll_engine_templates

    tpl = payroll_engine_templates() / "template_bulletin.html"
    assert tpl.is_file(), f"Template bulletin manquant : {tpl}"
    style = payroll_engine_templates() / "style.css"
    assert style.is_file(), f"Feuille de style bulletin manquante : {style}"


def test_payroll_engine_employee_folder_under_data_employes():
    from app.core.paths import payroll_engine_data, payroll_engine_employee_folder

    folder = payroll_engine_employee_folder("TEST_FOLDER_NAME")
    assert folder.parent == payroll_engine_data() / "employes"
    assert folder.name == "TEST_FOLDER_NAME"
