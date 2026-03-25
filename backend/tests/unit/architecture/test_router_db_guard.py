from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


BACKEND_ROOT = Path(__file__).resolve().parents[3]
MODULES_DIR = BACKEND_ROOT / "app" / "modules"


# Imports interdits dans les routers (accès direct à la persistance)
FORBIDDEN_IMPORT_PATTERNS = (
    "app.core.database",
    ".infrastructure.repository",
    ".infrastructure.queries",
    ".infrastructure.providers",
)

# Patterns de code interdits dans les routers.
# Le but est de bloquer les accès DB/SQL directs, pas la logique HTTP.
FORBIDDEN_CODE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bsupabase\b", "usage direct de 'supabase'"),
    (r"\.table\s*\(", "appel direct '.table(...)'"),
    (
        r"(?i)\bexecute\s*\(\s*[\"']\s*(select|insert|update|delete)\b",
        "exécution SQL brute",
    ),
    (
        r"(?i)[\"']\s*(select|insert|update|delete)\b[\s\S]{0,120}\bfrom\b",
        "chaîne SQL brute",
    ),
)


def _router_files() -> list[Path]:
    return sorted(MODULES_DIR.glob("*/api/router.py"))


def _find_forbidden_imports(file_path: Path, source: str) -> list[str]:
    violations: list[str] = []
    tree = ast.parse(source, filename=str(file_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported = alias.name
                if any(pattern in imported for pattern in FORBIDDEN_IMPORT_PATTERNS):
                    violations.append(
                        f"import interdit '{imported}' (ligne {node.lineno})"
                    )
        elif isinstance(node, ast.ImportFrom):
            base_module = node.module or ""
            if node.level:
                # On ne résout pas les imports relatifs précisément ; le nom suffit
                # pour détecter les imports infrastructure explicites.
                base_module = f"{'.' * node.level}{base_module}"
            if any(pattern in base_module for pattern in FORBIDDEN_IMPORT_PATTERNS):
                violations.append(
                    f"from import interdit '{base_module}' (ligne {node.lineno})"
                )

    return violations


def _find_forbidden_code(file_path: Path, source: str) -> list[str]:
    violations: list[str] = []
    for regex, label in FORBIDDEN_CODE_PATTERNS:
        for match in re.finditer(regex, source):
            line_number = source.count("\n", 0, match.start()) + 1
            violations.append(f"{label} (ligne {line_number})")
    return violations


def test_routers_do_not_access_persistence_directly():
    """Les routers ne doivent pas accéder à la DB ni exécuter du SQL brut."""
    files = _router_files()
    assert files, "Aucun router trouvé dans app/modules/*/api/router.py"

    all_violations: list[str] = []

    for router_file in files:
        source = router_file.read_text(encoding="utf-8")
        violations = [
            *_find_forbidden_imports(router_file, source),
            *_find_forbidden_code(router_file, source),
        ]
        if violations:
            rel = router_file.relative_to(BACKEND_ROOT)
            all_violations.extend(f"{rel}: {entry}" for entry in violations)

    assert not all_violations, (
        "Accès persistance interdit détecté dans des routers:\n- "
        + "\n- ".join(all_violations)
    )
