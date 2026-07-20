"""Garde-fou pour fixes ORANGE (code moteur) sous tests + non-régression."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"


@dataclass
class CodeFixResult:
    success: bool
    message: str
    reverted: bool = False


def run_pytest(targets: List[str]) -> tuple[bool, str]:
    cmd = ["python", "-m", "pytest", *targets, "-q", "--tb=short"]
    proc = subprocess.run(
        cmd,
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    output = (proc.stdout or "") + (proc.stderr or "")
    return ok, output[-2000:]


def git_revert_last() -> bool:
    proc = subprocess.run(
        ["git", "checkout", "--", "."],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def apply_code_fix_with_guard(
    fix_fn: Callable[[], None],
    *,
    pytest_targets: List[str] | None = None,
    regression_fn: Callable[[], bool] | None = None,
) -> CodeFixResult:
    """
    Applique un fix code sous garde-fou :
    1. Exécute fix_fn (modifie le code)
    2. Lance pytest cible
    3. Vérifie non-régression via regression_fn
    4. Revert auto si échec
    """
    targets = pytest_targets or [
        "tests/unit/payroll/test_bulletin_officiel.py",
        "tests/unit/payroll/backtest/",
    ]
    try:
        fix_fn()
    except Exception as exc:
        return CodeFixResult(success=False, message=f"Fix failed to apply: {exc}")

    pytest_ok, pytest_out = run_pytest(targets)
    if not pytest_ok:
        git_revert_last()
        return CodeFixResult(
            success=False,
            message=f"Pytest failed, reverted. Output: {pytest_out}",
            reverted=True,
        )

    if regression_fn and not regression_fn():
        git_revert_last()
        return CodeFixResult(
            success=False,
            message="Regression check failed, reverted",
            reverted=True,
        )

    return CodeFixResult(success=True, message="Code fix applied and validated")
