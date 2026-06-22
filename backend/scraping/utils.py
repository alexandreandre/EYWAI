from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging
import os
import re
import subprocess
import sys
import threading
import time
import requests
from dotenv import load_dotenv
import json

# --- Chargement .env robuste ---
def load_env() -> None:
    """Charge le .env depuis backend/ ou racine monorepo."""
    script_dir = Path(__file__).resolve().parent
    for candidate in [
        script_dir / ".." / ".env",
        script_dir / ".." / ".." / ".env",
        Path.cwd() / ".env",
    ]:
        env_path = candidate.resolve()
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[ENV] Chargé depuis : {env_path}",
                  file=sys.stderr)
            return
    print("[ENV] AVERTISSEMENT : aucun .env trouvé",
          file=sys.stderr)

# --- Fetch LegiSocial avec fallback année ---
def fetch_legisocial(url_template: str,
                     timeout: int = 15) -> requests.Response:
    """
    Essaie l'année courante puis N-1.
    url_template doit contenir {year}.
    """
    year = datetime.now().year
    for y in [year, year - 1]:
        url = url_template.format(year=y)
        try:
            resp = requests.get(
                url, timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code == 200:
                return resp
        except requests.RequestException:
            continue
    raise RuntimeError(
        f"URL LegiSocial inaccessible pour {year}"
        f" et {year - 1}: {url_template}"
    )

# --- Fetch générique avec retry ---
def fetch_url(url: str,
              timeout: int = 15,
              retries: int = 2) -> requests.Response:
    """Fetch avec retry automatique."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                url, timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_exc = e
            if attempt < retries:
                import time
                time.sleep(2 ** attempt)
    raise RuntimeError(
        f"Fetch échoué après {retries + 1} tentatives"
        f" : {url} — {last_exc}"
    )

# --- Runner de sous-script ---
def run_script(script_path: str,
               cwd: str,
               timeout: int = 120) -> dict:
    """
    Lance un script Python et retourne son stdout parsé en JSON.
    Retourne {"success": False, "error": ...} si échec.
    """
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True,
            timeout=timeout, cwd=cwd
        )
        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr[-2000:]
            }
        # Cherche la dernière ligne JSON valide sur stdout
        for line in reversed(result.stdout.strip()
                              .splitlines()):
            try:
                data = json.loads(line)
                data["success"] = True
                return data
            except json.JSONDecodeError:
                continue
        return {
            "success": False,
            "error": "Aucune sortie JSON trouvée"
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Timeout après {timeout}s"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Comparaison de signatures ---
def equal_core(sig_a: dict, sig_b: dict,
               tolerance: float = 0.01) -> bool:
    """
    Compare deux signatures numériques.
    Tolère une différence relative de tolerance (1% par défaut).
    """
    if set(sig_a.keys()) != set(sig_b.keys()):
        return False
    for key in sig_a:
        a, b = sig_a[key], sig_b[key]
        try:
            fa, fb = float(a), float(b)
            if fa == 0 and fb == 0:
                continue
            if abs(fa - fb) / max(abs(fa), abs(fb)) > tolerance:
                return False
        except (TypeError, ValueError):
            if str(a).strip() != str(b).strip():
                return False
    return True


def is_ai_scraper_label(label: str) -> bool:
    """True si le scraper est un script IA (*_AI.py ou libellé « AI »)."""
    u = (label or "").upper()
    if "_AI.PY" in u:
        return True
    if u.endswith("_AI"):
        return True
    if u == "AI":
        return True
    return False


def is_non_blocking_scraper_label(label: str) -> bool:
    """Scrapers secondaires : échec ignoré si une autre source a réussi."""
    if is_ai_scraper_label(label):
        return True
    return "legisocial" in (label or "").lower()


_CHILD_LOG_PREFIX = re.compile(
    r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\[\w+\]\s+-\s+"
)


def _shorten_child_log(line: str) -> str:
    """Retire le préfixe horodaté Python logging pour des logs plus lisibles."""
    return _CHILD_LOG_PREFIX.sub("", line).strip() or line.strip()


def run_labeled_script(
    label: str,
    path: str,
    *,
    cwd: str,
    timeout: int = 120,
) -> Optional[Dict[str, Any]]:
    """
    Lance un scraper en streaming : chaque ligne remonte immédiatement dans les logs.
    Retourne le payload JSON ou None si scraper IA ignoré. SystemExit si échec bloquant.
    """
    logging.info("▶ Scraper %s — démarrage", label)
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    stdout_lines: list[str] = []

    proc = subprocess.Popen(
        [sys.executable, "-u", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        env=env,
        bufsize=1,
    )

    assert proc.stdout is not None
    read_done = threading.Event()

    def _read_stdout() -> None:
        try:
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                stdout_lines.append(line)
                logging.info("  · [%s] %s", label, _shorten_child_log(line))
        finally:
            read_done.set()

    reader = threading.Thread(target=_read_stdout, daemon=True)
    reader.start()
    try:
        return_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        read_done.wait(timeout=2)
        elapsed = time.monotonic() - started
        logging.error("✗ Scraper %s — timeout après %0.0fs", label, elapsed)
        if is_ai_scraper_label(label):
            logging.warning("Scraper IA %s ignoré — poursuite avec les autres sources.", label)
            return None
        raise SystemExit(f"Timeout du script {label}")
    read_done.wait(timeout=2)

    elapsed = time.monotonic() - started

    if return_code != 0:
        tail = "\n".join(stdout_lines[-6:])
        logging.error(
            "✗ Scraper %s — échec (code %s, %0.1fs)%s",
            label,
            return_code,
            elapsed,
            f" — {tail[-400:]}" if tail else "",
        )
        if is_ai_scraper_label(label):
            logging.warning("Scraper IA %s ignoré — poursuite avec les autres sources.", label)
            return None
        raise SystemExit(f"Échec du script {label}")

    payload: Optional[Dict[str, Any]] = None
    for line in reversed(stdout_lines):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
            break
        except json.JSONDecodeError:
            continue

    if payload is None:
        preview = next((line for line in reversed(stdout_lines) if line.strip()), "")
        logging.error(
            "✗ Scraper %s — sortie non-JSON (%0.1fs). Dernière ligne : %s",
            label,
            elapsed,
            preview[:200],
        )
        if is_ai_scraper_label(label):
            logging.warning("Scraper IA %s ignoré — poursuite avec les autres sources.", label)
            return None
        raise SystemExit(f"Sortie invalide du script {label}")

    payload["__script"] = label
    logging.info("✓ Scraper %s — terminé (%0.1fs)", label, elapsed)
    return payload


def consensus_satisfied(
    sigs: List[Any],
    pair_equal: Callable[[Any, Any], bool],
) -> Tuple[bool, int]:
    """
    Valide la concordance entre sources :
    - 0 source : échec
    - 1 source : accepté (warning à logger côté appelant)
    - 2 sources : les deux doivent concorder
    - 3+ sources : au moins une paire doit concorder (2/3 ou plus)
    Retourne (ok, index_de_référence) pour choisir la signature canonique.
    """
    n = len(sigs)
    if n == 0:
        return False, 0
    if n == 1:
        return True, 0
    if n == 2:
        if pair_equal(sigs[0], sigs[1]):
            return True, 0
        return False, 0
    for i in range(n):
        for j in range(i + 1, n):
            if pair_equal(sigs[i], sigs[j]):
                return True, min(i, j)
    return False, 0


def prefer_primary_on_divergence(
    ok: bool,
    ref_idx: int,
    labels: List[str],
    sigs: List[Any],
    primary_label: str,
    sig_valid: Callable[[Any], bool],
) -> Tuple[bool, int]:
    """
    Si les sources secondaires divergent, retomber sur le scraper principal (ex. URSSAF).
    """
    if ok:
        return ok, ref_idx
    try:
        i = labels.index(primary_label)
    except ValueError:
        return ok, ref_idx
    if sig_valid(sigs[i]):
        return True, i
    return ok, ref_idx
