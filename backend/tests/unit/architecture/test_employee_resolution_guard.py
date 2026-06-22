"""Garde-fou : une seule implémentation canonique de résolution employé."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

BACKEND_ROOT = Path(__file__).resolve().parents[3]
APP_DIR = BACKEND_ROOT / "app"

CANONICAL_DEF = "def resolve_employee_id_for_user_account"
FORBIDDEN_DEFS = (
    "def resolve_employee_id_for_user(",
    "def resolve_employee_id_for_notifications(",
)

# Modules autorisés à définir un wrapper documenté (délégation vers shared).
WRAPPER_ALLOWLIST: frozenset[str] = frozenset(
    {
        "app/modules/absences/application/service.py",
        "app/modules/expenses/application/queries.py",
        "app/modules/saisies_avances/application/queries.py",
    }
)


def test_single_canonical_resolve_employee_implementation():
    canonical_files: list[str] = []
    forbidden_hits: list[str] = []

    for py_file in APP_DIR.rglob("*.py"):
        rel = py_file.relative_to(BACKEND_ROOT).as_posix()
        if "/tests/" in rel or rel.startswith("tests/"):
            continue
        source = py_file.read_text(encoding="utf-8")
        if CANONICAL_DEF in source:
            canonical_files.append(rel)
        for forbidden in FORBIDDEN_DEFS:
            if forbidden in source and rel not in WRAPPER_ALLOWLIST:
                if "employee_resolution" in rel:
                    continue
                forbidden_hits.append(f"{rel}: {forbidden.strip()}")

    assert canonical_files == ["app/modules/employees/infrastructure/queries.py"], (
        "resolve_employee_id_for_user_account doit être défini une seule fois "
        f"(employees/infrastructure/queries.py), trouvé: {canonical_files}"
    )
    assert not forbidden_hits, (
        "Définitions parallèles de résolution employé (utiliser app.shared.employee_resolution):\n- "
        + "\n- ".join(forbidden_hits)
    )


def test_shared_employee_resolution_reexports_canonical():
    shared = (APP_DIR / "shared" / "employee_resolution.py").read_text(encoding="utf-8")
    assert "resolve_employee_id_for_user_account" in shared
    assert "employees.infrastructure.queries" in shared
