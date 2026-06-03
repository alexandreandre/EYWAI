"""Garde-fous pour l'agent de réparation : allowlist, anti-hardcode, limites."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from core.env import BACKEND_ROOT, REPO_ROOT, SCRAPING_ROOT

ALLOWED_PREFIXES = (
    SCRAPING_ROOT,
    BACKEND_ROOT / "tests" / "fixtures" / "scraping",
    BACKEND_ROOT / "tests" / "unit" / "scraping",
    BACKEND_ROOT / "requirements.txt",
)

MAX_PATCH_FILES = 12
MAX_FILE_BYTES = 200_000
MAX_DIFF_LINES = 400

# Literals autorisés dans les scrapers static (catalogues codés en dur légaux).
_STATIC_SCRAPER_DIRS = {"heuressupp", "primes"}


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def is_allowed_path(path: Path) -> bool:
    resolved = path.resolve()
    for prefix in ALLOWED_PREFIXES:
        if resolved == prefix.resolve() or prefix.resolve() in resolved.parents:
            return True
    return False


def validate_patch_paths(paths: list[str]) -> tuple[bool, str]:
    if len(paths) > MAX_PATCH_FILES:
        return False, f"Trop de fichiers modifiés ({len(paths)} > {MAX_PATCH_FILES})"
    for raw in paths:
        p = (REPO_ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        if not is_allowed_path(p):
            return False, f"Chemin interdit : {raw}"
        if p.exists() and p.stat().st_size > MAX_FILE_BYTES:
            return False, f"Fichier trop volumineux : {raw}"
    return True, ""


def _is_static_scraper_path(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(SCRAPING_ROOT.resolve())
    except ValueError:
        return False
    return rel.parts[0] in _STATIC_SCRAPER_DIRS if rel.parts else False


def detect_new_hardcoded_literals(
    old_content: str,
    new_content: str,
    *,
    file_path: Path,
) -> tuple[bool, str]:
    """Rejette les nouveaux literals numériques suspects dans les parsers."""
    if _is_static_scraper_path(file_path):
        return True, ""
    if not file_path.suffix == ".py":
        return True, ""

    try:
        old_tree = ast.parse(old_content)
        new_tree = ast.parse(new_content)
    except SyntaxError as e:
        return False, f"Syntaxe Python invalide : {e}"

    def _numeric_literals(tree: ast.AST) -> set[str]:
        out: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                out.add(repr(node.value))
        return out

    old_nums = _numeric_literals(old_tree)
    new_nums = _numeric_literals(new_tree)
    added = new_nums - old_nums
    # Tolère 0, 1, petits entiers (indices, timeouts).
    suspicious = [
        n
        for n in added
        if not re.match(r"^(0|1|2|3|4|5|10|20|25|50|100|180|300|120|1800)$", n.strip("'\""))
        and ("." in n or float(n.strip("'\"")) > 5 if n.replace(".", "").replace("-", "").isdigit() else True)
    ]
    if suspicious:
        return (
            False,
            f"Nouveaux literals numériques suspects (hardcode?) : {suspicious[:5]}",
        )
    return True, ""


def validate_file_edit(
    file_path: Path,
    old_content: str,
    new_content: str,
) -> tuple[bool, str]:
    if not is_allowed_path(file_path):
        return False, f"Chemin interdit : {file_path}"
    if len(new_content.splitlines()) > MAX_DIFF_LINES * 2:
        return False, "Patch trop volumineux"
    ok, msg = detect_new_hardcoded_literals(
        old_content, new_content, file_path=file_path
    )
    if not ok:
        return False, msg
    return True, ""
