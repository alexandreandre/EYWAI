#!/usr/bin/env python3
"""
Scheduler EYWAI — exécute automatiquement les scrapers
dont next_run_at est dépassé.
"""

import sys
import json
import time
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHEDULER] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).parent / "scheduler.log",
            encoding="utf-8"
        )
    ]
)
logger = logging.getLogger(__name__)

SCRAPING_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRAPING_DIR.parent

# Mapping source_key → dossier orchestrateur
SOURCE_KEY_MAP = {
    "smic": "SMIC",
    "pss": "PSS",
    "csg": "CSG",
    "ags": "AGS",
    "agirc_arrco": "AGIRC-ARRCO",
    "avantages": "Avantages",
    "cfp": "CFP",
    "csa": "CSA",
    "fnal": "FNAL",
    "ij_maladie": "IJmaladie",
    "mmid_patronal": "MMIDpatronal",
    "mmid_salarial": "MMIDsalarial",
    "pas": "PAS",
    "alloc": "alloc",
    "assurance_chomage": "assurancechomage",
    "baremes_km": "bareme-indemnite-kilometrique",
    "dialogue_social": "dialoguesocial",
    "frais_pro": "fraispro",
    "taxe_apprentissage": "taxeapprentissage",
    "vieillesse_patronal": "vieillessepatronal",
    "vieillesse_salarial": "vieillessesalarial",
}

DEFAULT_TIMEOUT = 300  # 5 minutes par scraper


def load_env_and_supabase():
    """
    Charge .env et retourne le client supabase.
    Cherche dans backend/.env puis racine monorepo.
    """
    from dotenv import load_dotenv
    import os

    for candidate in [
        BACKEND_DIR / ".env",
        BACKEND_DIR.parent / ".env",
    ]:
        if candidate.exists():
            load_dotenv(candidate)
            logger.info(f"ENV chargé depuis {candidate}")
            break

    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or \
          os.environ.get("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants")
        sys.exit(1)
    return create_client(url, key)


def get_due_schedules(supabase) -> list:
    """
    Retourne les schedules dont next_run_at <= now()
    et is_active = True.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        r = (supabase.table("scraping_schedules")
             .select("*")
             .eq("is_active", True)
             .lte("next_run_at", now_iso)
             .execute())
        return r.data or []
    except Exception as e:
        logger.error(f"Erreur lecture schedules : {e}")
        return []


def compute_next_run(frequency: str) -> str:
    """
    Calcule le prochain next_run_at selon la fréquence.
    Fréquences supportées : daily, weekly, monthly
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    if frequency == "daily":
        delta = timedelta(days=1)
    elif frequency == "weekly":
        delta = timedelta(weeks=1)
    elif frequency == "monthly":
        delta = timedelta(days=30)
    else:
        delta = timedelta(days=1)  # défaut : quotidien
    return (now + delta).isoformat()


def run_scraper(source_key: str) -> dict:
    """Lance l'orchestrateur correspondant à source_key."""
    folder = SOURCE_KEY_MAP.get(source_key)
    if not folder:
        return {
            "success": False,
            "error": f"source_key inconnu : {source_key}"
        }

    orchestrator = SCRAPING_DIR / folder / "orchestrator.py"
    if not orchestrator.exists():
        return {
            "success": False,
            "error": f"orchestrator.py introuvable : {orchestrator}"
        }

    try:
        result = subprocess.run(
            [sys.executable, str(orchestrator)],
            capture_output=True, text=True,
            timeout=DEFAULT_TIMEOUT,
            cwd=str(BACKEND_DIR)
        )
        # Cherche la dernière ligne JSON valide
        for line in reversed(
            result.stdout.strip().splitlines()
        ):
            try:
                data = json.loads(line)
                data["returncode"] = result.returncode
                return data
            except json.JSONDecodeError:
                continue
        return {
            "success": result.returncode == 0,
            "error": result.stderr[-1000:]
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Timeout après {DEFAULT_TIMEOUT}s"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_schedule(supabase, schedule_id: str,
                    frequency: str,
                    success: bool,
                    result: dict) -> None:
    """Met à jour next_run_at et last_run_result."""
    next_run = compute_next_run(frequency)
    try:
        supabase.table("scraping_schedules").update({
            "next_run_at": next_run,
            "last_run_at": datetime.now(
                timezone.utc).isoformat(),
            "last_run_success": success,
            "last_run_result": json.dumps(
                result, ensure_ascii=False)[:5000],
        }).eq("id", schedule_id).execute()
    except Exception as e:
        logger.error(f"Erreur MAJ schedule {schedule_id}: {e}")


def create_job_record(supabase, source_key: str,
                      result: dict) -> None:
    """Enregistre l'exécution dans scraping_jobs."""
    try:
        supabase.table("scraping_jobs").insert({
            "source_key": source_key,
            "status": "success" if result.get("success")
                      else "error",
            "started_at": datetime.now(
                timezone.utc).isoformat(),
            "result_data": json.dumps(
                result, ensure_ascii=False)[:10000],
            "error_message": result.get("error"),
        }).execute()
    except Exception as e:
        logger.error(f"Erreur création job {source_key}: {e}")


def run_once(supabase) -> int:
    """
    Exécute un cycle : vérifie les schedules dus
    et lance les scrapers correspondants.
    Retourne le nombre de scrapers exécutés.
    """
    schedules = get_due_schedules(supabase)
    if not schedules:
        logger.info("Aucun scraper à exécuter.")
        return 0

    logger.info(f"{len(schedules)} scraper(s) à exécuter.")

    for schedule in schedules:
        source_key = schedule.get("source_key", "?")
        frequency = schedule.get("frequency", "weekly")
        schedule_id = schedule["id"]

        logger.info(f"▶ Lancement : {source_key}")
        result = run_scraper(source_key)

        success = result.get("success", False)
        status = "✓" if success else "✗"
        logger.info(
            f"{status} {source_key} — "
            f"{'OK' if success else result.get('error', '?')}"
        )

        update_schedule(supabase, schedule_id,
                        frequency, success, result)
        create_job_record(supabase, source_key, result)

    return len(schedules)


def main():
    """
    Mode daemon : vérifie toutes les 15 minutes.
    Passer --once pour un seul cycle (mode cron).
    """
    supabase = load_env_and_supabase()

    if "--once" in sys.argv:
        logger.info("Mode --once : cycle unique")
        count = run_once(supabase)
        logger.info(f"Terminé : {count} scraper(s) exécutés")
        sys.exit(0)

    # Mode daemon
    logger.info("Scheduler démarré (vérification toutes les 15min)")
    while True:
        try:
            run_once(supabase)
        except Exception as e:
            logger.error(f"Erreur cycle scheduler : {e}")
        logger.info("Prochain cycle dans 15 minutes...")
        time.sleep(15 * 60)


if __name__ == "__main__":
    main()
