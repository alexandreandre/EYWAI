#!/usr/bin/env python3
"""
Auto-test des scrapers EYWAI.

- Mode hermétique (défaut) : compile tous les scripts.
- Mode réseau (--live) : dry-run des orchestrateurs (nécessite réseau, pas d'écriture BDD).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRAPING_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRAPING_DIR.parent
if str(SCRAPING_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPING_DIR))

from scraper_manifest import ScraperCheck, ScraperEntry, get_manifest, manifest_names


def get_nested(d: dict, path: list[str]) -> object:
    cur: object = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def check_value(value: object, check: ScraperCheck) -> tuple[bool, str]:
    if check.keys_present:
        if not isinstance(value, dict):
            return False, f"Attendu dict à {check.path}, reçu {type(value).__name__}"
        missing = [k for k in check.keys_present if k not in value]
        if missing:
            return False, f"Clés manquantes: {missing}"
        return True, f"{len(check.keys_present)} clés présentes"

    if check.min_rows is not None:
        try:
            n = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False, f"rows invalide: {value!r}"
        if n >= check.min_rows:
            return True, f"rows={n} >= {check.min_rows}"
        return False, f"rows={n} < {check.min_rows}"

    if check.year_current:
        cy = datetime.now().year
        try:
            y = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False, f"Année invalide: {value!r}"
        if cy - 1 <= y <= cy + 1:
            return True, f"année {y} OK"
        return False, f"Année {y} hors [{cy - 1}, {cy + 1}]"

    if check.not_null and value is None:
        return False, f"Valeur absente ({check.path})"

    if check.min is not None or check.max is not None:
        if value is None:
            return False, f"Valeur absente ({check.path})"
        try:
            fval = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False, f"Valeur non numérique: {value!r}"
        lo = check.min if check.min is not None else float("-inf")
        hi = check.max if check.max is not None else float("inf")
        if lo <= fval <= hi:
            return True, f"{fval} ∈ [{lo}, {hi}]"
        return False, f"{fval} HORS [{lo}, {hi}]"

    if check.not_null:
        return True, "présent"
    return True, "OK"


def compile_all_scripts() -> list[str]:
    errors: list[str] = []
    for py in SCRAPING_DIR.rglob("*.py"):
        if "anciens_scrapings" in str(py):
            continue
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(py)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            errors.append(f"{py.relative_to(SCRAPING_DIR)}: {r.stderr.strip()}")
    return errors


def build_env(*, dry_run: bool, no_ai: bool) -> dict[str, str]:
    env = os.environ.copy()
    if dry_run:
        env["EYWAI_SCRAPING_DRY_RUN"] = "1"
    if no_ai:
        env["EYWAI_SCRAPING_DISABLE_AI"] = "1"
    return env


def run_orchestrator(entry: ScraperEntry, *, env: dict[str, str]) -> dict:
    script = SCRAPING_DIR / entry.dir / entry.orchestrator
    cmd = [sys.executable, str(script)]
    if entry.dry_run:
        cmd.append("--dry-run")
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=entry.timeout,
            cwd=str(BACKEND_DIR),
            env=env,
        )
        duration_s = round(time.monotonic() - t0, 1)
        for line in reversed(proc.stdout.strip().splitlines()):
            try:
                data = json.loads(line)
                return {
                    "success": proc.returncode == 0,
                    "data": data,
                    "stderr": proc.stderr[-800:],
                    "stdout": proc.stdout[-800:],
                    "duration_s": duration_s,
                }
            except json.JSONDecodeError:
                continue
        return {
            "success": False,
            "data": {},
            "stderr": proc.stderr[-800:],
            "stdout": proc.stdout[-800:],
            "duration_s": duration_s,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "data": {},
            "stderr": f"TIMEOUT {entry.timeout}s",
            "duration_s": entry.timeout,
        }


_NETWORK_FAILURE_MARKERS = (
    "ConnectTimeout",
    "Connection timed out",
    "Max retries exceeded",
    "Impossible d'accéder",
    "TIMEOUT ",
)


def is_network_failure(result: dict) -> bool:
    blob = " ".join(
        str(result.get(k, "")) for k in ("stderr", "stdout", "data")
    )
    payload = result.get("data") or {}
    if payload.get("success") is False and not payload.get("sources_used"):
        return True
    return any(marker in blob for marker in _NETWORK_FAILURE_MARKERS)


def evaluate_entry(entry: ScraperEntry, result: dict) -> tuple[bool, list[dict]]:
    """Retourne (ok, détail checks). Les tier static en échec = warn seulement."""
    check_results: list[dict] = []
    payload = result.get("data") or {}
    if not result.get("success") or not payload.get("success", False):
        return False, check_results

    scraper_ok = True
    for check in entry.checks:
        val = get_nested(payload, check.path)
        ok, msg = check_value(val, check)
        check_results.append({"path": check.path, "ok": ok, "message": msg})
        if not ok:
            scraper_ok = False

    return scraper_ok, check_results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harness scraping EYWAI")
    parser.add_argument("--live", action="store_true", help="Dry-run live (réseau)")
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Désactive les scripts *_AI.py (OPENROUTER non requis)",
    )
    parser.add_argument(
        "--tier",
        choices=["critical", "standard", "static"],
        help="Filtrer par tier",
    )
    parser.add_argument(
        "--only",
        help="Liste séparée par virgules (ex: SMIC,PSS,CSG)",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    entries = get_manifest(
        tier=args.tier,
        only={n.strip() for n in args.only.split(",") if n.strip()} if args.only else None,
    )

    print(f"\n{'='*60}")
    print(
        f"AUTO-TEST SCRAPERS — {datetime.now():%Y-%m-%d %H:%M} — "
        f"live={args.live} no_ai={args.no_ai} count={len(entries)}"
    )
    print(f"{'='*60}\n")

    compile_errors = compile_all_scripts()
    if compile_errors:
        print("✗ Erreurs de compilation:")
        for e in compile_errors[:20]:
            print(f"  {e}")
        if not args.live:
            return 1

    if not args.live:
        if compile_errors:
            return 1
        print(f"Mode hermétique: compilation OK ({len(manifest_names())} orchestrateurs).")
        print("Live dry-run: python scraping/test_scrapers.py --live --no-ai")
        return 0

    env = build_env(dry_run=True, no_ai=args.no_ai)
    total_ok = 0
    total_ko = 0
    total_warn = 0
    results: list[dict] = []

    for entry in entries:
        print(f"▶ {entry.name}...", end=" ", flush=True)
        result = run_orchestrator(entry, env=env)
        scraper_ok, check_results = evaluate_entry(entry, result)

        if scraper_ok:
            status = "OK"
            print("✓ OK")
            total_ok += 1
        elif entry.tier == "static" or (
            entry.network_flaky and is_network_failure(result)
        ):
            status = "WARN"
            total_warn += 1
            print("⚠ WARN (réseau)" if entry.network_flaky else "⚠ WARN")
        else:
            status = "FAIL"
            total_ko += 1
            print("✗ ÉCHEC")
            print(result.get("stderr", "")[:200])

        payload = result.get("data") or {}
        results.append(
            {
                "name": entry.name,
                "tier": entry.tier,
                "status": status,
                "duration_s": result.get("duration_s"),
                "sources_used": payload.get("sources_used"),
                "checks": check_results,
            }
        )

    critical_ko = sum(1 for r in results if r["status"] == "FAIL" and r["tier"] == "critical")
    standard_ko = sum(1 for r in results if r["status"] == "FAIL" and r["tier"] != "critical")

    summary = {
        "total_ok": total_ok,
        "total_ko": total_ko,
        "total_warn": total_warn,
        "skipped_ai": args.no_ai,
        "critical_failures": critical_ko,
        "scrapers": results,
    }
    print(f"\nRÉSULTAT : {total_ok} OK / {total_ko} ÉCHECS / {total_warn} WARN")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if critical_ko > 0:
        return 1
    if standard_ko > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
