# scripts/alloc/orchestrator.py

#!/usr/bin/env python3

import json
import os
import sys
import subprocess
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional
from supabase import create_client, Client, PostgrestAPIResponse
from dotenv import load_dotenv

# --- Configuration ---

# Clé de configuration ciblée dans la table 'payroll_config'
CONFIG_KEY_TO_UPDATE = "cotisations"
# ID de l'item spécifique que ce script met à jour DANS le JSONB
ITEM_ID_TO_PATCH = "allocations_familiales"

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Trouver la racine du projet
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Charger les variables d'environnement
dotenv_path = os.path.join(REPO_ROOT, ".env")
if not os.path.exists(dotenv_path):
    logging.critical(f"Fichier .env non trouvé à: {dotenv_path}")
    sys.exit(1)
load_dotenv(dotenv_path=dotenv_path)

# Liste des scrapers à exécuter
SCRIPTS_TO_RUN: List[Tuple[str, str]] = [
    ("alloc.py", os.path.join(os.path.dirname(__file__), "alloc.py")),
    # ("alloc_AI.py", os.path.join(os.path.dirname(__file__), "alloc_AI.py")),
    (
        "alloc_LegiSocial.py",
        os.path.join(os.path.dirname(__file__), "alloc_LegiSocial.py"),
    ),
]


# --- 1. Fonctions de Scraping & Validation (Standardisées) ---


def iso_now() -> str:
    """Retourne la date/heure actuelle au format ISO UTC."""
    return datetime.now(timezone.utc).isoformat()


def run_script(label: str, path: str) -> Dict[str, Any]:
    """Exécute un scraper et récupère son JSON depuis stdout."""
    logging.info(f"Exécution du scraper: {label}...")
    try:
        proc = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=os.environ.copy(),
            timeout=60,
            check=True,
        )
        payload = json.loads(proc.stdout.strip())
        payload["__script"] = label
        return payload
    except subprocess.CalledProcessError as e:
        logging.error(f"Échec du scraper {label}. stderr: {e.stderr.strip()}")
        raise SystemExit(f"Échec du script {label}")
    except json.JSONDecodeError:
        logging.error(f"Sortie non-JSON de {label}. stdout: {proc.stdout[:200]}...")
        raise SystemExit(f"Sortie invalide du script {label}")
    except Exception as e:
        logging.error(f"Erreur inattendue avec {label}: {e}")
        raise


def core_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise le payload en une signature comparable pour les allocations familiales."""
    if payload.get("id") != ITEM_ID_TO_PATCH:
        raise ValueError(f"ID '{ITEM_ID_TO_PATCH}' attendu, reçu '{payload.get('id')}'")

    vals = payload.get("valeurs", {}) or {}
    plein = vals.get("patronal_plein", None)
    reduit = vals.get("patronal_reduit", None)

    try:
        plein_norm = None if plein is None else round(float(plein), 6)
        reduit_norm = None if reduit is None else round(float(reduit), 6)
    except (ValueError, TypeError):
        logging.warning(
            f"Valeurs non numériques (plein='{plein}', reduit='{reduit}') reçues de {payload.get('__script')}."
        )
        plein_norm, reduit_norm = None, None

    return {
        "id": payload.get("id"),
        "type": payload.get("type"),
        "libelle": payload.get("libelle"),
        "base": payload.get("base"),
        "valeurs": {
            "salarial": None,
            "patronal_plein": plein_norm,
            "patronal_reduit": reduit_norm,
        },
    }


def validate_sig(sig: Dict[str, Any]) -> bool:
    """Vérifie que les deux taux (plein et réduit) sont présents."""
    v = sig.get("valeurs", {})
    return v.get("patronal_plein") is not None and v.get("patronal_reduit") is not None


def equal_core(a: Dict[str, Any], b: Dict[str, Any], tol: float = 1e-9) -> bool:
    """Compare deux signatures 'allocations_familiales'."""
    for k in ("id", "type", "libelle", "base"):
        if a.get(k) != b.get(k):
            return False

    ap, ar = a["valeurs"]["patronal_plein"], a["valeurs"]["patronal_reduit"]
    bp, br = b["valeurs"]["patronal_plein"], b["valeurs"]["patronal_reduit"]

    # Les deux taux doivent être présents (validé par validate_sig, mais double-check)
    if ap is None or bp is None or ar is None or br is None:
        return False

    return compare_floats(ap, bp, tol) and compare_floats(ar, br, tol)


def compare_floats(a: float | None, b: float | None, tol: float = 1e-9) -> bool:
    """Compare deux floats (ou None) avec une tolérance."""
    if a is None or b is None:
        return a is b
    try:
        return math.isclose(float(a), float(b), abs_tol=tol)
    except (ValueError, TypeError):
        return False


def merge_sources(payloads: List[Dict[str, Any]]) -> List[str]:
    """Fusionne les URL sources uniques depuis les métadonnées."""
    seen_urls = set()
    source_links = []
    for p in payloads:
        for s in p.get("meta", {}).get("source", []):
            if not isinstance(s, dict):
                continue
            url = s.get("url")
            if url and isinstance(url, str) and url.strip() not in seen_urls:
                url = url.strip()
                seen_urls.add(url)
                source_links.append(url)
    return source_links


def debug_comparison(
    payloads: List[Dict[str, Any]], sigs: List[Dict[str, Any]]
) -> None:
    """Logge une comparaison détaillée des valeurs scrapées."""
    logging.info("--- Début Comparaison Détaillée (Alloc. Familiales) ---")
    for p, s in zip(payloads, sigs):
        label = p.get("__script", "inconnu")
        v = s["valeurs"]
        plein = v.get("patronal_plein", "N/A")
        reduit = v.get("patronal_reduit", "N/A")
        srcs = p.get("meta", {}).get("source", [])
        src_str = srcs[0].get("url") if srcs else "N/A"
        logging.info(
            f"  - {label:>20} -> plein={plein} | réduit={reduit} | source={src_str}"
        )
    logging.info("--- Fin Comparaison ---")


# --- 2. Fonctions Supabase (Standardisées) ---


def init_supabase_client() -> Client:
    """Initialise et retourne le client Supabase."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        logging.critical("Variables SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes.")
        logging.critical(
            "Assurez-vous que .env contient SUPABASE_SERVICE_KEY (la clé 'service_role')."
        )
        raise EnvironmentError(
            "Variables Supabase non définies ou clé de service manquante."
        )

    try:
        client: Client = create_client(supabase_url, supabase_key)
        logging.info("Connexion Supabase établie.")
        return client
    except Exception as e:
        logging.critical(f"Échec de l'initialisation du client Supabase: {e}")
        raise


def fetch_active_config(supabase: Client, config_key: str) -> Optional[Dict[str, Any]]:
    """Récupère la configuration active (ou None si 'cold start')."""
    logging.info(f"Lecture de la config active pour: '{config_key}'...")
    try:
        response: Optional[PostgrestAPIResponse] = (
            supabase.table("payroll_config")
            .select("*")
            .eq("config_key", config_key)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if response is None:
            logging.error(
                "La requête execute() a retourné 'None'. Problème de connexion ou permission (406)."
            )
            return None
        return response.data
    except Exception as e:
        logging.error(
            f"Impossible de récupérer la config active '{config_key}'. Erreur: {e}"
        )
        raise


def apply_patch_in_memory(
    current_config_data: Optional[Dict[str, Any]],
    patch_core: Dict[str, Any],  # La sortie de core_signature
) -> Dict[str, Any]:
    """
    Met à jour le bloc 'cotisations' complet avec le patch 'allocations_familiales'.
    """
    logging.info(f"Application du patch '{ITEM_ID_TO_PATCH}' en mémoire...")

    if current_config_data:
        new_config_data = json.loads(json.dumps(current_config_data))
    else:
        logging.warning(
            f"Aucune config '{CONFIG_KEY_TO_UPDATE}' trouvée. Création d'un nouveau bloc."
        )
        new_config_data = {"cotisations": []}

    cotisations_list = new_config_data.get("cotisations", [])

    # ✅ TRADUCTION IMPORTANTE :
    # Convertit le format de `core_signature` (avec "valeurs": {...})
    # au format plat de `cotisations.json`.
    patch_data = {
        "id": patch_core["id"],
        "libelle": patch_core["libelle"],
        "base": patch_core["base"],
        "salarial": patch_core["valeurs"]["salarial"],
        "patronal_plein": patch_core["valeurs"]["patronal_plein"],
        "patronal_reduit": patch_core["valeurs"]["patronal_reduit"],
    }

    found = False
    for i, item in enumerate(cotisations_list):
        if isinstance(item, dict) and item.get("id") == ITEM_ID_TO_PATCH:
            # Fusionne (met à jour) l'item existant
            updated_item = {**item, **patch_data}
            cotisations_list[i] = updated_item
            found = True
            logging.info(f"Item '{ITEM_ID_TO_PATCH}' trouvé et mis à jour.")
            break

    if not found:
        logging.warning(
            f"Item '{ITEM_ID_TO_PATCH}' non trouvé. Ajout au bloc de cotisations."
        )
        cotisations_list.append(patch_data)

    new_config_data["cotisations"] = cotisations_list
    return new_config_data


def update_config_in_supabase(
    supabase: Client,
    current_row: Optional[Dict[str, Any]],
    new_config_data: Dict[str, Any],
    source_links: List[str],
) -> None:
    """
    Compare l'ancienne et la nouvelle config et exécute la bonne action BDD :
    - Scénario 0 (Cold Start) : Insère la v1.
    - Scénario 1 (Identique) : Met à jour 'last_checked_at'.
    - Scénario 2 (Différent) : Crée une nouvelle version.
    """
    comment = f"Mise à jour automatique: {ITEM_ID_TO_PATCH}"

    # Scénario 0 (Cold Start) : current_row est None
    if current_row is None:
        logging.info(
            f"Aucune config existante. Insertion de la v1 pour '{CONFIG_KEY_TO_UPDATE}'."
        )
        new_row = {
            "config_key": CONFIG_KEY_TO_UPDATE,
            "config_data": new_config_data,
            "version": 1,
            "is_active": True,
            "comment": comment,
            "last_checked_at": iso_now(),
            "source_links": source_links,
        }
        try:
            supabase.table("payroll_config").insert(new_row).execute()
            logging.info(f"✅ Succès: '{CONFIG_KEY_TO_UPDATE}' v1 créée.")
        except Exception as e:
            logging.error(f"Échec de l'insertion initiale. Erreur: {e}")
            raise
        return

    # --- Les scénarios 1 et 2 ne s'exécutent que si une ligne existe ---
    current_config_data = current_row["config_data"]
    current_id = current_row["id"]
    current_version = current_row["version"]

    # --- SCÉNARIO 1 : IDENTIQUE ---
    if current_config_data == new_config_data:
        logging.info(
            f"Les données '{ITEM_ID_TO_PATCH}' sont inchangées. Mise à jour de 'last_checked_at'."
        )
        try:
            supabase.table("payroll_config").update(
                {
                    "last_checked_at": iso_now(),
                    "source_links": source_links,
                }
            ).eq("id", current_id).execute()
            logging.info("✅ Succès: 'last_checked_at' mis à jour.")
        except Exception as e:
            logging.error(
                f"Échec de la mise à jour 'last_checked_at' pour ID {current_id}. Erreur: {e}"
            )
            raise

    # --- SCÉNARIO 2 : DIFFÉRENT ---
    else:
        logging.warning(
            f"Différence détectée pour '{ITEM_ID_TO_PATCH}'. Création de la version {current_version + 1}..."
        )

        new_row = {
            "config_key": CONFIG_KEY_TO_UPDATE,
            "config_data": new_config_data,
            "version": current_version + 1,
            "is_active": True,
            "comment": comment,
            "last_checked_at": iso_now(),
            "source_links": source_links,
        }

        try:
            logging.info(
                f"Désactivation de la version {current_version} (ID: {current_id})..."
            )
            supabase.table("payroll_config").update({"is_active": False}).eq(
                "id", current_id
            ).execute()

            logging.info(f"Insertion de la version {current_version + 1}...")
            supabase.table("payroll_config").insert(new_row).execute()

            logging.info(
                f"✅ Succès: '{CONFIG_KEY_TO_UPDATE}' mis à jour vers v{current_version + 1}."
            )

        except Exception as e:
            logging.error(f"Échec de la transaction de versioning. Erreur: {e}")
            try:
                logging.warning(
                    f"Tentative de rollback: Réactivation de la v{current_version} (ID: {current_id})..."
                )
                supabase.table("payroll_config").update({"is_active": True}).eq(
                    "id", current_id
                ).execute()
            except Exception as rollback_e:
                logging.critical(
                    f"ÉCHEC CRITIQUE DU ROLLBACK. BDD en état instable. Erreur: {rollback_e}"
                )
            raise


# --- 3. Fonction Principale ---


def main() -> None:
    """Orchestre l'ensemble du processus de mise à jour des Allocations Familiales."""
    logging.info("--- DÉBUT Orchestrateur Allocations Familiales ---")

    try:
        # 1. Lancer tous les scrapers
        payloads: List[Dict[str, Any]] = []
        labels: List[str] = []
        for label, path in SCRIPTS_TO_RUN:
            payloads.append(run_script(label, path))
            labels.append(label)

        # 2. Normaliser les signatures
        sigs: List[Dict[str, Any]] = []
        for i, p in enumerate(payloads):
            try:
                sigs.append(core_signature(p))
            except (ValueError, SystemExit) as e:
                logging.error(f"Normalisation échouée pour {labels[i]}: {e}")
                sys.exit(2)

        # 3. Afficher la comparaison
        debug_comparison(payloads, sigs)

        # 4. Valider la complétude (non-null)
        for i, sig in enumerate(sigs):
            if not validate_sig(sig):
                logging.error(
                    f"Valeurs manquantes dans {labels[i]}: {json.dumps(sig, ensure_ascii=False)}"
                )
                sys.exit(2)

        # 5. Valider la concordance
        all_equal = all(equal_core(sigs[i], sigs[i + 1]) for i in range(len(sigs) - 1))

        if not all_equal:
            logging.error("Divergence entre les sources de scraping. Arrêt.")
            sys.exit(2)

        logging.info("Concordance des taux (plein/réduit) validée.")

        # Le patch validé et les sources
        final_patch_data = sigs[0]
        source_links = merge_sources(payloads)

        # 6. Initialiser la BDD
        supabase = init_supabase_client()

        # 7. Lire l'état actuel (peut être None)
        current_row = fetch_active_config(supabase, CONFIG_KEY_TO_UPDATE)

        # 8. Appliquer le patch en mémoire
        new_config_data_blob = apply_patch_in_memory(
            current_row["config_data"] if current_row else None, final_patch_data
        )

        # 9. Comparer et écrire dans Supabase
        update_config_in_supabase(
            supabase, current_row, new_config_data_blob, source_links
        )

        logging.info("--- FIN Orchestrateur Allocations Familiales ---")

    except SystemExit as e:
        logging.error(f"Arrêt contrôlé: {e}")
        sys.exit(int(str(e).split()[-1]) if str(e).split()[-1].isdigit() else 1)
    except Exception as e:
        logging.critical(f"Une erreur fatale est survenue: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
