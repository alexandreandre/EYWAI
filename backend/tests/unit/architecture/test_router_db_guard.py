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
# Routers encore couplés à la persistance (refactor progressif : services / DI).
# Retirer une entrée dès que le router ne dépend plus des imports / patterns listés.
ROUTER_PERSISTENCE_ALLOWLIST: frozenset[str] = frozenset()

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
        rel_posix = router_file.relative_to(BACKEND_ROOT).as_posix()
        if rel_posix in ROUTER_PERSISTENCE_ALLOWLIST:
            continue
        source = router_file.read_text(encoding="utf-8")
        violations = [
            *_find_forbidden_imports(router_file, source),
            *_find_forbidden_code(router_file, source),
        ]
        if violations:
            all_violations.extend(f"{rel_posix}: {entry}" for entry in violations)

    assert not all_violations, (
        "Accès persistance interdit détecté dans des routers:\n- "
        + "\n- ".join(all_violations)
    )


def test_router_persistence_allowlist_does_not_grow():
    """L'allowlist ne doit pas grossir sans revue explicite (objectif : 0)."""
    max_allowed = 0
    assert len(ROUTER_PERSISTENCE_ALLOWLIST) <= max_allowed, (
        f"ROUTER_PERSISTENCE_ALLOWLIST a {len(ROUTER_PERSISTENCE_ALLOWLIST)} entrées "
        f"(max {max_allowed}). Retirer des routers refactorés au lieu d'en ajouter."
    )


APPLICATION_FASTAPI_ALLOWLIST: frozenset[str] = frozenset(
    {
        "app/modules/access_control/application/commands.py",
        "app/modules/access_control/application/queries.py",
        "app/modules/access_control/application/service.py",
        "app/modules/auth/application/commands.py",
        "app/modules/auth/application/queries.py",
        "app/modules/auth/application/refresh.py",
        "app/modules/auth/application/service.py",
        "app/modules/bonus_types/application/service.py",
        "app/modules/collective_agreements/application/service.py",
        "app/modules/copilot/application/dto.py",
        "app/modules/cse/application/service.py",
        "app/modules/dashboard/application/service.py",
        "app/modules/employee_exits/application/dto.py",
        "app/modules/employees/application/commands.py",
        "app/modules/medical_follow_up/application/commands.py",
        "app/modules/medical_follow_up/application/queries.py",
        "app/modules/medical_follow_up/application/service.py",
        "app/modules/mutuelle_types/application/commands.py",
        "app/modules/mutuelle_types/application/queries.py",
        "app/modules/mutuelle_types/application/service.py",
        "app/modules/promotions/application/commands.py",
        "app/modules/promotions/application/queries.py",
        "app/modules/saisies_avances/application/dto.py",
        "app/modules/super_admin/application/service.py",
        "app/modules/uploads/application/commands.py",
        "app/modules/uploads/application/service.py",
    }
)


def test_application_layer_avoids_fastapi_imports():
    """La couche application ne doit pas importer FastAPI (hors allowlist temporaire)."""
    app_dir = BACKEND_ROOT / "app" / "modules"
    violations: list[str] = []
    for py_file in sorted(app_dir.glob("**/application/**/*.py")):
        rel = py_file.relative_to(BACKEND_ROOT).as_posix()
        if rel in APPLICATION_FASTAPI_ALLOWLIST:
            continue
        source = py_file.read_text(encoding="utf-8")
        if "fastapi" in source.lower():
            violations.append(rel)
    assert not violations, (
        "Import FastAPI interdit en application (hors allowlist):\n- "
        + "\n- ".join(violations)
    )
