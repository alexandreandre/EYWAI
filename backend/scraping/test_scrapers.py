#!/usr/bin/env python3
"""
Auto-test des scrapers EYWAI.
Lance chaque orchestrateur et vérifie la cohérence
des données retournées contre les valeurs connues.
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

SCRAPING_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRAPING_DIR.parent

# Liste des scrapers à tester avec valeurs de référence
# (fourchettes acceptables pour les taux actuels)
SCRAPERS = [
    {
        "name": "SMIC",
        "dir": "SMIC",
        "orchestrator": "orchestrator.py",
        "timeout": 120,
        "checks": [
            # Vérifie que le SMIC horaire est entre 10 et 15€
            {
                "path": ["data", "smic_horaire_brut"],
                "min": 10.0, "max": 15.0,
                "description": "SMIC horaire brut"
            }
        ]
    },
    {
        "name": "PSS",
        "dir": "PSS",
        "orchestrator": "orchestrator.py",
        "timeout": 180,  # Selenium peut être lent
        "checks": [
            {
                "path": ["data", "plafond_annuel"],
                "min": 40000, "max": 60000,
                "description": "Plafond SS annuel"
            }
        ]
    },
    {
        "name": "CSG",
        "dir": "CSG",
        "orchestrator": "orchestrator.py",
        "timeout": 120,
        "checks": [
            {
                "path": ["data", "taux_csg_imposable"],
                "min": 0.05, "max": 0.15,
                "description": "Taux CSG déductible"
            }
        ]
    },
    {
        "name": "AGS",
        "dir": "AGS",
        "orchestrator": "orchestrator.py",
        "timeout": 120,
        "checks": [
            {
                "path": ["data", "taux_ags"],
                "min": 0.001, "max": 0.01,
                "description": "Taux AGS"
            }
        ]
    },
    {
        "name": "AGIRC-ARRCO",
        "dir": "AGIRC-ARRCO",
        "orchestrator": "orchestrator.py",
        "timeout": 120,
        "checks": [
            {
                "path": ["data",
                         "tranche_1_taux_salarial"],
                "min": 0.03, "max": 0.08,
                "description": "Taux salarial T1 AGIRC"
            }
        ]
    },
]

def get_nested(d: dict, path: list):
    """Accède à une valeur imbriquée via une liste de clés."""
    current = d
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current

def run_orchestrator(scraper: dict) -> dict:
    """Lance l'orchestrateur et retourne son résultat."""
    script = (SCRAPING_DIR / scraper["dir"]
              / scraper["orchestrator"])
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True,
            timeout=scraper["timeout"],
            cwd=str(BACKEND_DIR)
        )
        # Cherche la dernière ligne JSON valide
        for line in reversed(
            result.stdout.strip().splitlines()
        ):
            try:
                return {
                    "success": result.returncode == 0,
                    "data": json.loads(line),
                    "stderr": result.stderr[-500:]
                }
            except json.JSONDecodeError:
                continue
        return {
            "success": False,
            "data": {},
            "stderr": result.stderr[-500:],
            "stdout": result.stdout[-500:]
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "data": {},
            "stderr": f"TIMEOUT après {scraper['timeout']}s"
        }

def check_value(value, check: dict) -> tuple[bool, str]:
    """Vérifie qu'une valeur est dans la fourchette."""
    if value is None:
        return False, f"Valeur absente ({check['path']})"
    try:
        fval = float(value)
        if check["min"] <= fval <= check["max"]:
            return True, f"{fval} ∈ [{check['min']}, {check['max']}]"
        return False, (
            f"{fval} HORS fourchette "
            f"[{check['min']}, {check['max']}]"
        )
    except (TypeError, ValueError):
        return False, f"Valeur non numérique : {value}"

def main():
    print(f"\n{'='*60}")
    print(f"AUTO-TEST SCRAPERS EYWAI — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*60}\n")

    results = []
    total_ok = 0
    total_ko = 0

    for scraper in SCRAPERS:
        print(f"▶ {scraper['name']}...", end=" ", flush=True)
        result = run_orchestrator(scraper)

        scraper_ok = True
        check_results = []

        if not result["success"] and not result["data"]:
            print(f"✗ ÉCHEC (orchestrateur)")
            print(f"  stderr: {result.get('stderr', '')[:200]}")
            total_ko += 1
            results.append({
                "name": scraper["name"],
                "status": "FAIL",
                "reason": "Orchestrateur en échec"
            })
            continue

        for check in scraper.get("checks", []):
            value = get_nested(result["data"], check["path"])
            ok, msg = check_value(value, check)
            check_results.append({
                "description": check["description"],
                "ok": ok,
                "message": msg
            })
            if not ok:
                scraper_ok = False

        if scraper_ok:
            print(f"✓ OK")
            total_ok += 1
        else:
            print(f"✗ DONNÉES INVALIDES")
            total_ko += 1

        for cr in check_results:
            status = "  ✓" if cr["ok"] else "  ✗"
            print(f"{status} {cr['description']}: {cr['message']}")

        results.append({
            "name": scraper["name"],
            "status": "OK" if scraper_ok else "FAIL",
            "checks": check_results
        })

    print(f"\n{'='*60}")
    print(f"RÉSULTAT : {total_ok} OK / {total_ko} ÉCHECS")
    print(f"{'='*60}\n")

    # Sortie JSON pour intégration CI
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_ok": total_ok,
        "total_ko": total_ko,
        "scrapers": results
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    sys.exit(0 if total_ko == 0 else 1)

if __name__ == "__main__":
    main()
