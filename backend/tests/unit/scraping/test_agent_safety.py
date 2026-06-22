"""Tests unitaires des garde-fous agent (allowlist, anti-hardcode)."""

from __future__ import annotations



from agent.safety import (
    detect_new_hardcoded_literals,
    is_allowed_path,
    validate_patch_paths,
)
from core.env import BACKEND_ROOT, SCRAPING_ROOT


def test_allowed_scraping_path():
    p = SCRAPING_ROOT / "SMIC.py"
    assert is_allowed_path(p)


def test_forbidden_path_outside_scraping():
    p = BACKEND_ROOT / "app" / "main.py"
    assert not is_allowed_path(p)


def test_validate_patch_paths_rejects_too_many_files():
    paths = [f"backend/scraping/f{i}.py" for i in range(20)]
    ok, msg = validate_patch_paths(paths)
    assert not ok
    assert "Trop de fichiers" in msg


def test_validate_patch_paths_accepts_scraper_file():
    rel = "backend/scraping/SMIC.py"
    ok, msg = validate_patch_paths([rel])
    assert ok, msg


def test_detect_hardcoded_rate_literal():
    old = "def parse():\n    return extract(html)\n"
    new = "def parse():\n    return 11.88\n"
    ok, msg = detect_new_hardcoded_literals(
        old, new, file_path=SCRAPING_ROOT / "SMIC.py"
    )
    assert not ok
    assert "hardcode" in msg.lower() or "suspects" in msg.lower()


def test_detect_allows_small_integers():
    old = "TIMEOUT = 10\n"
    new = "TIMEOUT = 25\n"
    ok, msg = detect_new_hardcoded_literals(
        old, new, file_path=SCRAPING_ROOT / "SMIC.py"
    )
    assert ok, msg
