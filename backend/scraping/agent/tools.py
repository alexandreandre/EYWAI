"""Outils de l'agent : fichiers, patch, tests, git, fetch."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from agent.safety import (
    REPO_ROOT,
    SCRAPING_ROOT,
    validate_file_edit,
    validate_patch_paths,
)
from core.env import BACKEND_ROOT
from core.http import DEFAULT_HEADERS, fetch_html

logger = logging.getLogger(__name__)


@dataclass
class FileEdit:
    path: str
    old_content: str
    new_content: str


@dataclass
class TestResult:
    ok: bool
    stage: str
    output: str


def resolve_repo_path(rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute():
        return p.resolve()
    return (REPO_ROOT / rel).resolve()


def read_file(rel_path: str) -> str:
    path = resolve_repo_path(rel_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_file(rel_path: str, content: str) -> None:
    path = resolve_repo_path(rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def apply_edits(edits: list[FileEdit]) -> tuple[bool, str]:
    paths = [e.path for e in edits]
    ok, msg = validate_patch_paths(paths)
    if not ok:
        return False, msg

    for edit in edits:
        path = resolve_repo_path(edit.path)
        current = read_file(edit.path) if path.exists() else ""
        old = edit.old_content if edit.old_content else current
        ok_edit, err = validate_file_edit(path, old, edit.new_content)
        if not ok_edit:
            return False, f"{edit.path}: {err}"
        write_file(edit.path, edit.new_content)
    return True, ""


def fetch_page(url: str, *, timeout: int = 25) -> tuple[int, str]:
    """Fetch HTML ; retourne (status_hint, body)."""
    try:
        html = fetch_html(url, timeout=timeout)
        return 200, html
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        body = e.response.text[:5000] if e.response is not None else ""
        return code, body
    except Exception as e:
        return 0, str(e)


def check_url_alive(url: str, *, timeout: int = 20) -> tuple[bool, int, str]:
    """GET (puis HEAD en secours). Retourne (alive, status_code, final_url).

    Preferer GET : beaucoup de sites officiels (Urssaf, BOSS) bloquent HEAD ou
    les UA bots, ce qui renvoie status 0 et fausse la validation mensuelle.
    """
    headers = {**DEFAULT_HEADERS}
    try:
        r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        if r.status_code >= 400:
            r = requests.head(url, timeout=timeout, headers=headers, allow_redirects=True)
        ok = 200 <= r.status_code < 400
        return ok, r.status_code, r.url
    except requests.RequestException as e:
        return False, 0, str(e)


def run_pytest_unit_scraping() -> TestResult:
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/unit/scraping/test_parsers_primary.py",
        "tests/unit/scraping/test_parsers_secondary.py",
        "tests/unit/scraping/test_validation.py",
        "tests/unit/scraping/test_agent_safety.py",
        "-q", "--tb=short",
    ]
    proc = subprocess.run(
        cmd, cwd=str(BACKEND_ROOT), capture_output=True, text=True, timeout=120
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return TestResult(ok=proc.returncode == 0, stage="pytest_unit", output=out[-4000:])


def run_compile_scraping() -> TestResult:
    cmd = [sys.executable, "scraping/test_scrapers.py"]
    proc = subprocess.run(
        cmd, cwd=str(BACKEND_ROOT), capture_output=True, text=True, timeout=180
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return TestResult(ok=proc.returncode == 0, stage="compile", output=out[-2000:])


def run_dry_run_scraper(scraper_name: str, *, live: bool = True) -> TestResult:
    cmd = [sys.executable, "scraping/test_scrapers.py"]
    if live:
        cmd.append("--live")
    cmd.extend(["--no-ai", "--only", scraper_name])
    proc = subprocess.run(
        cmd, cwd=str(BACKEND_ROOT), capture_output=True, text=True, timeout=300
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return TestResult(ok=proc.returncode == 0, stage=f"dry_run_{scraper_name}", output=out[-4000:])


def run_full_merge_gate(scraper_name: str) -> tuple[bool, list[TestResult]]:
    """Batterie complète avant merge."""
    results: list[TestResult] = []
    for fn in (run_compile_scraping, run_pytest_unit_scraping):
        r = fn()
        results.append(r)
        if not r.ok:
            return False, results
    r_live = run_dry_run_scraper(scraper_name, live=True)
    results.append(r_live)
    if not r_live.ok:
        return False, results
    r_all = run_dry_run_all()
    results.append(r_all)
    return r_all.ok, results


def run_dry_run_all() -> TestResult:
    cmd = [
        sys.executable, "scraping/test_scrapers.py",
        "--live", "--no-ai",
    ]
    proc = subprocess.run(
        cmd, cwd=str(BACKEND_ROOT), capture_output=True, text=True, timeout=900
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return TestResult(ok=proc.returncode == 0, stage="dry_run_all", output=out[-6000:])


def scraper_script_paths(scraper_name: str) -> list[str]:
    """Chemins relatifs repo des scripts primary du scraper."""
    from scraper_manifest import get_manifest

    for entry in get_manifest():
        if entry.name == scraper_name:
            d = SCRAPING_ROOT / entry.dir
            paths: list[str] = []
            for py in sorted(d.glob("*.py")):
                if py.name.startswith("orchestrator") or py.name == "spec.py":
                    continue
                if "_AI" in py.name or py.name == "_logic.py":
                    continue
                rel = py.resolve().relative_to(REPO_ROOT.resolve())
                paths.append(str(rel))
            return paths[:6]
    return []


def find_url_constants_in_scripts(scraper_name: str) -> list[tuple[str, str]]:
    """Retourne (fichier, url) des constantes URL_* dans les scripts."""
    out: list[tuple[str, str]] = []
    url_re = re.compile(
        r'(?:URL_[A-Z0-9_]+|SERIE_PAGE_URL|FALLBACK_[A-Z_]+)\s*=\s*["\']([^"\']+)["\']'
    )
    for rel in scraper_script_paths(scraper_name):
        content = read_file(rel)
        for m in url_re.finditer(content):
            out.append((rel, m.group(1)))
    return out


def replace_url_in_file(rel_path: str, old_url: str, new_url: str) -> bool:
    content = read_file(rel_path)
    if old_url not in content:
        return False
    new_content = content.replace(old_url, new_url, 1)
    write_file(rel_path, new_content)
    return True


def git_commit_and_push(
    *,
    branch: str,
    message: str,
    files: list[str],
) -> tuple[bool, str]:
    """Commit + push ; utilisé en CI avec GITHUB_TOKEN."""
    try:
        subprocess.run(["git", "config", "user.email", "scraping-agent@eywai.app"], check=True)
        subprocess.run(["git", "config", "user.name", "EYWAI Scraping Agent"], check=True)
        subprocess.run(["git", "checkout", "-B", branch], cwd=str(REPO_ROOT), check=True)
        for f in files:
            subprocess.run(["git", "add", f], cwd=str(REPO_ROOT), check=True)
        subprocess.run(["git", "commit", "-m", message], cwd=str(REPO_ROOT), check=True)
        subprocess.run(["git", "push", "-u", "origin", branch, "--force-with-lease"], cwd=str(REPO_ROOT), check=True)
        return True, branch
    except subprocess.CalledProcessError as e:
        return False, str(e)


def create_pr_and_merge(branch: str, title: str, body: str) -> tuple[bool, str]:
    try:
        subprocess.run(
            [
                "gh", "pr", "create",
                "--title", title,
                "--body", body,
                "--head", branch,
                "--base", "main",
                "--label", "scraping-agent",
            ],
            cwd=str(REPO_ROOT), check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["gh", "pr", "merge", branch, "--auto", "--squash"],
            cwd=str(REPO_ROOT), check=True,
        )
        return True, "merged"
    except subprocess.CalledProcessError as e:
        err = getattr(e, "stderr", "") or str(e)
        return False, err


def parse_edits_from_llm(data: dict[str, Any]) -> list[FileEdit]:
    edits: list[FileEdit] = []
    for item in data.get("edits", []):
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        new_content = item.get("new_content")
        if path and new_content is not None:
            edits.append(
                FileEdit(
                    path=str(path),
                    old_content=str(item.get("old_content") or ""),
                    new_content=str(new_content),
                )
            )
    return edits
