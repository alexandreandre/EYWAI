from pathlib import Path
from datetime import datetime
from typing import Any, Callable, List, Tuple
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import json
import subprocess
import sys

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
