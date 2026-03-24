"""
Liste et exécution des tests : ``backend_api/tests`` (pytest) et ``e2e/`` (Playwright).

La page Super Admin « Tests » affiche l'arbre des cibles et lance pytest ou
``npm run test`` (Playwright) selon le préfixe de la cible.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.paths import REPO_ROOT, TESTS_DIR

# Cibles Playwright : préfixe ``pw:`` puis chemin relatif sous ``e2e/`` (ex. ``specs/auth.spec.ts``), ou ``pw:`` seul = toute la suite.
PLAYWRIGHT_TARGET_PREFIX = "pw:"


# Labels des niveaux (alignés sur tests/README.md)
LEVEL_LABELS = {
    "unit": "Unitaires",
    "integration": "Intégration",
    "e2e": "E2E / Smoke",
    "migration": "Migration",
    "architecture": "Architecture",
}


def get_tests_tree() -> Dict[str, Any]:
    """
    Construit l'arbre des cibles de test (niveaux → modules/fichiers).

    Retourne une structure adaptée au front : niveaux unit, integration, e2e, migration,
    chacun avec une entrée "Tout" (run entire level) et des enfants par module ou fichier.
    """
    if not TESTS_DIR.is_dir():
        return {"levels": []}

    levels: List[Dict[str, Any]] = []

    # unit/ et integration/ : sous-dossiers = modules
    for level_id in ("unit", "integration"):
        level_path = TESTS_DIR / level_id
        if not level_path.is_dir():
            continue
        children: List[Dict[str, Any]] = [
            {"id": f"tests/{level_id}", "label": "Tout", "path": f"tests/{level_id}", "is_full_level": True}
        ]
        for sub in sorted(level_path.iterdir()):
            if sub.is_dir() and not sub.name.startswith("_"):
                rel = f"tests/{level_id}/{sub.name}"
                children.append({
                    "id": rel,
                    "label": sub.name,
                    "path": rel,
                    "is_full_level": False,
                })
        levels.append({
            "id": level_id,
            "label": LEVEL_LABELS.get(level_id, level_id),
            "path": f"tests/{level_id}",
            "children": children,
        })

    # e2e/ : fichiers test_*.py à la racine + sous-dossier cross_module
    e2e_path = TESTS_DIR / "e2e"
    if e2e_path.is_dir():
        e2e_children: List[Dict[str, Any]] = [
            {"id": "tests/e2e", "label": "Tout", "path": "tests/e2e", "is_full_level": True}
        ]
        for item in sorted(e2e_path.iterdir()):
            if item.is_file() and item.name.startswith("test_") and item.suffix == ".py":
                rel = f"tests/e2e/{item.name}"
                e2e_children.append({"id": rel, "label": item.name, "path": rel, "is_full_level": False})
            elif item.is_dir() and item.name == "cross_module":
                rel = f"tests/e2e/cross_module"
                e2e_children.append({"id": rel, "label": "cross_module", "path": rel, "is_full_level": False})
        levels.append({
            "id": "e2e",
            "label": LEVEL_LABELS.get("e2e", "e2e"),
            "path": "tests/e2e",
            "children": e2e_children,
        })

    pw_level = _build_playwright_level()
    if pw_level:
        levels.append(pw_level)

    # migration/ : fichiers test_*.py
    migration_path = TESTS_DIR / "migration"
    if migration_path.is_dir():
        mig_children: List[Dict[str, Any]] = [
            {"id": "tests/migration", "label": "Tout", "path": "tests/migration", "is_full_level": True}
        ]
        for item in sorted(migration_path.iterdir()):
            if item.is_file() and item.name.startswith("test_") and item.suffix == ".py":
                rel = f"tests/migration/{item.name}"
                mig_children.append({"id": rel, "label": item.name, "path": rel, "is_full_level": False})
        levels.append({
            "id": "migration",
            "label": LEVEL_LABELS.get("migration", "migration"),
            "path": "tests/migration",
            "children": mig_children,
        })

    # architecture/ : garde-fous d'architecture (fichiers test_*.py)
    architecture_path = TESTS_DIR / "unit" / "architecture"
    if architecture_path.is_dir():
        architecture_children: List[Dict[str, Any]] = [
            {
                "id": "tests/unit/architecture",
                "label": "Tout",
                "path": "tests/unit/architecture",
                "is_full_level": True,
            }
        ]
        for item in sorted(architecture_path.iterdir()):
            if item.is_file() and item.name.startswith("test_") and item.suffix == ".py":
                rel = f"tests/unit/architecture/{item.name}"
                architecture_children.append({
                    "id": rel,
                    "label": item.name,
                    "path": rel,
                    "is_full_level": False,
                })
        levels.append({
            "id": "architecture",
            "label": LEVEL_LABELS.get("architecture", "architecture"),
            "path": "tests/unit/architecture",
            "children": architecture_children,
        })

    return {"levels": levels}


def _e2e_playwright_dir() -> Path:
    return REPO_ROOT / "e2e"


def _validate_playwright_spec_rel(e2e_dir: Path, rel: str) -> Optional[Path]:
    """Retourne le fichier résolu si ``rel`` est ``specs/<fichier>.spec.ts`` sous ``e2e_dir``."""
    p = Path(rel)
    if len(p.parts) != 2 or p.parts[0] != "specs":
        return None
    name = p.parts[1]
    if not name.endswith(".spec.ts") or ".." in rel.replace("\\", "/"):
        return None
    resolved = (e2e_dir / rel).resolve()
    try:
        resolved.relative_to(e2e_dir.resolve())
    except ValueError:
        return None
    if not resolved.is_file():
        return None
    return resolved


def _build_playwright_level() -> Optional[Dict[str, Any]]:
    e2e_dir = _e2e_playwright_dir()
    if not e2e_dir.is_dir():
        return None
    specs_dir = e2e_dir / "specs"
    children: List[Dict[str, Any]] = [
        {
            "id": PLAYWRIGHT_TARGET_PREFIX,
            "label": "Tout (tous les navigateurs)",
            "path": PLAYWRIGHT_TARGET_PREFIX,
            "is_full_level": True,
        }
    ]
    if specs_dir.is_dir():
        for f in sorted(specs_dir.glob("*.spec.ts")):
            rel = f"specs/{f.name}"
            path = f"{PLAYWRIGHT_TARGET_PREFIX}{rel}"
            children.append({
                "id": path,
                "label": f.name,
                "path": path,
                "is_full_level": False,
            })
    return {
        "id": "playwright",
        "label": "E2E navigateur (Playwright · dossier e2e/)",
        "path": PLAYWRIGHT_TARGET_PREFIX,
        "children": children,
    }


def _run_playwright_target(e2e_dir: Path, target: str) -> Dict[str, Any]:
    """Exécute ``npm run test`` dans ``e2e_dir``. ``target`` : ``pw:`` ou ``pw:specs/….spec.ts``."""
    if not target.startswith(PLAYWRIGHT_TARGET_PREFIX):
        return {
            "target": target,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "Cible Playwright invalide (préfixe attendu : pw:).",
        }
    rest = target[len(PLAYWRIGHT_TARGET_PREFIX) :].strip()
    npm = shutil.which("npm")
    if not npm:
        return {
            "target": target,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "npm introuvable dans le PATH (installez Node.js).",
        }
    if not (e2e_dir / "package.json").is_file():
        return {
            "target": target,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Dossier e2e absent ou incomplet : {e2e_dir}",
        }
    extra: List[str] = []
    if rest:
        if _validate_playwright_spec_rel(e2e_dir, rest) is None:
            return {
                "target": target,
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Fichier spec non autorisé ou introuvable : {rest!r}",
            }
        extra = [rest]
    cmd = [npm, "run", "test", "--"] + extra
    try:
        result = subprocess.run(
            cmd,
            cwd=str(e2e_dir),
            capture_output=True,
            text=True,
            timeout=1800,
            env=os.environ.copy(),
        )
        return {
            "target": target,
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
        }
    except subprocess.TimeoutExpired:
        return {
            "target": target,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "Timeout (1800 s) dépassé pour Playwright.",
        }
    except Exception as e:
        return {
            "target": target,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
        }


def _run_one_target(backend_root: Path, target: str) -> Dict[str, Any]:
    """Exécute pytest sur une seule cible. Retourne dict avec target, success, exit_code, stdout, stderr."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--tb=short",
        target,
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(backend_root),
            capture_output=True,
            text=True,
            timeout=600,
        )
        return {
            "target": target,
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
        }
    except subprocess.TimeoutExpired:
        return {
            "target": target,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "Timeout (600s) dépassé.",
        }
    except Exception as e:
        return {
            "target": target,
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
        }


def run_tests(targets: List[str]) -> Dict[str, Any]:
    """
    Exécute pytest ou Playwright pour chaque cible (une exécution par cible).

    - Pytest : chemins relatifs à ``backend_api`` (ex. ``tests/unit``, ``tests/e2e/test_smoke_global.py``).
    - Playwright : préfixe ``pw:`` (ex. ``pw:`` pour toute la suite, ``pw:specs/auth.spec.ts``).
    """
    if not targets:
        return {
            "results": [
                {
                    "target": "",
                    "success": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Aucune cible sélectionnée.",
                }
            ],
        }

    backend_root = TESTS_DIR.parent
    e2e_dir = _e2e_playwright_dir()
    results: List[Dict[str, Any]] = []
    for target in targets:
        if target.startswith(PLAYWRIGHT_TARGET_PREFIX):
            results.append(_run_playwright_target(e2e_dir, target))
        else:
            results.append(_run_one_target(backend_root, target))
    return {"results": results}
