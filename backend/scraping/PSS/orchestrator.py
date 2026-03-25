# scripts/PSS/orchestrator.py

#!/usr/bin/env python3

import json
import os
import sys
import subprocess
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional
from supabase import create_client, Client, PostgrestAPIResponse
from dotenv import load_dotenv

# --- Configuration ---

# Clé de configuration ciblée dans la table 'payroll_config'
CONFIG_KEY_TO_UPDATE = "pss"

# Clés essentielles requises pour valider un PSS
ESSENTIAL_KEYS = {"annuel", "mensuel", "journalier"}

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
    ("PSS.py", os.path.join(os.path.dirname(__file__), "PSS.py")),
    ("PSS_LegiSocial.py", os.path.join(os.path.dirname(__file__), "PSS_LegiSocial.py")),
    ("PSS_AI.py", os.path.join(os.path.dirname(__file__), "PSS_AI.py")),
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
    """Extrait la section des données (le dict des plafonds) pour la comparaison."""
    return payload.get("sections", {})


def equal_core(sig_a: Dict, sig_b: Dict) -> Tuple[bool, Optional[str]]:
    """
    Compare deux dictionnaires de plafonds sur leurs clés communes.
    """
    keys_a = set(sig_a.keys())
    keys_b = set(sig_b.keys())

    common_keys = keys_a.intersection(keys_b)

    if not ESSENTIAL_KEYS.issubset(common_keys):
        missing = ESSENTIAL_KEYS - common_keys
        return (
            False,
            f"Une ou plusieurs clés PSS essentielles sont manquantes : {missing}",
        )

    logging.info(
        f"Comparaison sur {len(common_keys)} clés communes (dont {ESSENTIAL_KEYS})..."
    )

    for key in sorted(list(common_keys)):
        val_a = sig_a.get(key)
        val_b = sig_b.get(key)

        # Comparaison simple (les valeurs PSS sont des entiers)
        if val_a != val_b:
            return False, f"Mismatch sur la clé commune '{key}': {val_a} != {val_b}"

    return True, None


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


def debug_mismatch(script_a: str, script_b: str, details: str) -> None:
    """Affiche un message d'erreur clair."""
    logging.warning("DISCORDANCE entre les sources pour PSS:")
    logging.warning(f"  Comparaison entre '{script_a}' et '{script_b}'.")
    logging.warning(f"  ► Détail: {details}")


def debug_success(payloads: List[Dict[str, Any]], sigs: List[Dict[str, Any]]) -> None:
    """Logge les détails d'une concordance de taux."""
    scripts = [p.get("__script", "?") for p in payloads]
    mensuel = sigs[0].get("mensuel", "N/A")
    annuel = sigs[0].get("annuel", "N/A")
    logging.info(f"Concordance des taux PSS trouvée entre: {', '.join(scripts)}")
    logging.info(f"  ► Valeurs clés: Annuel={annuel}, Mensuel={mensuel}")


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


def update_config_in_supabase(
    supabase: Client,
    current_row: Optional[Dict[str, Any]],
    new_config_data: Dict[str, Any],  # Le dict {"annuel": ..., "mensuel": ...}
    source_links: List[str],
) -> None:
    """
    Compare l'ancien et le nouveau bloc 'pss' et exécute la bonne action BDD.
    """
    comment = f"Mise à jour automatique: {CONFIG_KEY_TO_UPDATE}"

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
    # La comparaison se fait directement sur les blocs
    if current_config_data == new_config_data:
        logging.info(
            f"Les données '{CONFIG_KEY_TO_UPDATE}' sont inchangées. Mise à jour de 'last_checked_at'."
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
            f"Différence détectée pour '{CONFIG_KEY_TO_UPDATE}'. Création de la version {current_version + 1}..."
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
    """Orchestre l'ensemble du processus de mise à jour du PSS."""
    logging.info("--- DÉBUT Orchestrateur PSS ---")

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

        # 3. Valider la concordance (primaire vs autres)
        primary_sig = sigs[0]
        all_equal = True
        for i in range(1, len(sigs)):
            are_equal, details = equal_core(primary_sig, sigs[i])
            if not are_equal:
                all_equal = False
                debug_mismatch(
                    payloads[0]["__script"], payloads[i]["__script"], details
                )
                break

        if not all_equal:
            logging.error("Divergence entre les sources de scraping. Arrêt.")
            sys.exit(2)

        debug_success(payloads, sigs)

        # Le bloc de données validé et les sources
        # On prend la source primaire (la plus complète)
        final_data_to_store = primary_sig
        source_links = merge_sources(payloads)

        # 4. Initialiser la BDD
        supabase = init_supabase_client()

        # 5. Lire l'état actuel (peut être None)
        current_row = fetch_active_config(supabase, CONFIG_KEY_TO_UPDATE)

        # 6. Comparer et écrire dans Supabase
        update_config_in_supabase(
            supabase, current_row, final_data_to_store, source_links
        )

        logging.info("--- FIN Orchestrateur PSS ---")

    except SystemExit as e:
        logging.error(f"Arrêt contrôlé: {e}")
        sys.exit(int(str(e).split()[-1]) if str(e).split()[-1].isdigit() else 1)
    except Exception as e:
        logging.critical(f"Une erreur fatale est survenue: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
