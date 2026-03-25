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
CONFIG_KEY_TO_UPDATE = "avantages_en_nature"
# Ce script ne patche pas 'cotisations', il gère son propre bloc de config.

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
    ("URSSAF", os.path.join(os.path.dirname(__file__), "Avantages.py")),
    ("LegiSocial", os.path.join(os.path.dirname(__file__), "Avantages_LegiSocial.py")),
    # ("AI", os.path.join(os.path.dirname(__file__), "Avantages_AI.py")),
]


# --- 1. Fonctions de Scraping & Validation (Adaptées) ---


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
        # Tente de parser stdout même si le script échoue
        out = (e.stdout or "").strip()
        if out:
            try:
                logging.warning(
                    f"Le scraper {label} a échoué (code {e.returncode}) mais a produit un JSON."
                )
                payload = json.loads(out)
                payload["__script"] = label
                return payload
            except Exception:
                pass  # Échec du parsing, on log l'erreur ci-dessous

        logging.error(f"Échec du scraper {label}. stderr: {e.stderr.strip()}")
        raise SystemExit(f"Échec du script {label}")
    except json.JSONDecodeError:
        logging.error(f"Sortie non-JSON de {label}. stdout: {proc.stdout[:200]}...")
        raise SystemExit(f"Sortie invalide du script {label}")
    except Exception as e:
        logging.error(f"Erreur inattendue avec {label}: {e}")
        raise


def to_float(x: Any) -> float | None:
    """Convertit une valeur en float, en nettoyant les formats courants."""
    if x is None:
        return None
    try:
        if isinstance(x, str):
            x = (
                x.replace("\u202f", "")
                .replace("\xa0", "")
                .replace("€", "")
                .replace(" ", "")
                .replace(",", ".")
            )
        return float(x)
    except (ValueError, TypeError):
        return None


def normalize_bareme(lst: Any) -> List[Dict[str, float]]:
    """Normalise le barème de logement en un format JSON propre."""
    out: List[Dict[str, float]] = []
    if not isinstance(lst, list):
        return out
    for row in lst:
        if not isinstance(row, dict):
            continue
        # Gère les différents noms de clés vus dans tes scripts
        rmax = to_float(row.get("remuneration_max") or row.get("remuneration_max_eur"))
        v1 = to_float(row.get("valeur_1_piece") or row.get("valeur_1_piece_eur"))
        vpp = to_float(
            row.get("valeur_par_piece") or row.get("valeur_par_piece_suppl_eur")
        )

        if v1 is None or vpp is None:
            logging.warning(
                f"Ligne de barème logement ignorée (données manquantes): {row}"
            )
            continue

        out.append(
            {
                "remuneration_max_eur": rmax
                if rmax is not None
                else 9_999_999.99,  # Utilise un plafond 'infini' si non spécifié
                "valeur_1_piece_eur": v1,
                "valeur_par_piece_suppl_eur": vpp,
            }
        )
    return sorted(
        out, key=lambda x: x["remuneration_max_eur"]
    )  # Toujours trier pour la comparaison


def payload_to_core(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extrait le noyau comparable (repas, titre, logement) depuis divers formats."""
    core = {"repas": None, "titre": None, "logement": [], "__src": []}
    script_name = payload.get("__script", "unknown")

    try:
        # 1) AI payload style: {id, type:param_bundle, items:[...]}
        if isinstance(payload, dict) and payload.get("type") == "param_bundle":
            items = payload.get("items", [])
            mp = {
                it.get("key"): it.get("value") for it in items if isinstance(it, dict)
            }
            core["repas"] = to_float(
                mp.get("repas_valeur_forfaitaire_eur") or mp.get("repas")
            )
            core["titre"] = to_float(
                mp.get("titre_restaurant_exoneration_max_eur")
                or mp.get("titre_restaurant")
            )
            core["logement"] = normalize_bareme(
                mp.get("logement_bareme_forfaitaire") or mp.get("logement")
            )
            core["__src"] = payload.get("meta", {}).get("source", [])
            return core

        # 2) Direct dict style: {repas, titre_restaurant, logement}
        if isinstance(payload, dict) and {
            "repas",
            "titre_restaurant",
            "logement",
        } <= set(payload.keys()):
            core["repas"] = to_float(payload.get("repas"))
            core["titre"] = to_float(payload.get("titre_restaurant"))
            core["logement"] = normalize_bareme(payload.get("logement"))
            core["__src"] = payload.get("meta", {}).get("source", [])
            return core

        # 3) Vérifie le format de l'ancien 'entreprise.json' (pour le fallback)
        av = payload.get("PARAMETRES_ENTREPRISE", {}).get("avantages_en_nature", {})
        if not av:
            av = (
                payload.get("entreprise", {})
                .get("parametres_paie", {})
                .get("avantages_en_nature", {})
            )

        if av:  # Si on a trouvé un bloc avantages_en_nature
            core["repas"] = to_float(av.get("repas_valeur_forfaitaire"))
            core["titre"] = to_float(
                av.get("titre_restaurant_exoneration_max_patronale")
            )
            core["logement"] = normalize_bareme(av.get("logement_bareme_forfaitaire"))
            # Pas de source ici, car c'est un fallback local
            return core

        logging.warning(
            f"Format de payload non reconnu pour {script_name}. Tentative d'extraction échouée."
        )

    except Exception as e:
        logging.error(
            f"Erreur lors de la normalisation du payload pour {script_name}: {e}. Payload: {str(payload)[:200]}..."
        )

    # Retourne un core vide en cas d'échec total
    return core


def cores_equal(a: Dict[str, Any], b: Dict[str, Any], tol: float = 1e-6) -> bool:
    """Compare deux dictionnaires 'core' normalisés."""

    if not (
        compare_floats(a["repas"], b["repas"], tol)
        and compare_floats(a["titre"], b["titre"], tol)
    ):
        return False

    la, lb = a["logement"], b["logement"]
    if len(la) != len(lb):
        return False

    # Les barèmes sont triés par normalize_bareme, on peut les comparer ligne à ligne
    for r1, r2 in zip(la, lb):
        if not (
            compare_floats(r1["remuneration_max_eur"], r2["remuneration_max_eur"], tol)
            and compare_floats(r1["valeur_1_piece_eur"], r2["valeur_1_piece_eur"], tol)
            and compare_floats(
                r1["valeur_par_piece_suppl_eur"], r2["valeur_par_piece_suppl_eur"], tol
            )
        ):
            return False

    return True


def compare_floats(a: float | None, b: float | None, tol: float = 1e-9) -> bool:
    """Compare deux floats (ou None) avec une tolérance."""
    if a is None or b is None:
        return a is b
    try:
        return math.isclose(float(a), float(b), abs_tol=tol)
    except (ValueError, TypeError):
        return False


def merge_sources(
    payloads: List[Dict[str, Any]], cores: List[Dict[str, Any]]
) -> List[str]:
    """Fusionne les URL sources uniques depuis les métadonnées."""
    seen_urls = set()
    source_links = []

    # Sources extraites par payload_to_core (stockées dans __src)
    for c in cores:
        for s in c.get("__src", []):
            if not isinstance(s, dict):
                continue
            url = s.get("url")
            if url and isinstance(url, str) and url.strip() not in seen_urls:
                url = url.strip()
                seen_urls.add(url)
                source_links.append(url)

    return source_links


def debug_comparison(labels: List[str], cores: List[Dict[str, Any]]) -> None:
    """Logge une comparaison détaillée des valeurs scrapées."""
    logging.info("--- Début Comparaison Détaillée (Avantages) ---")
    for lbl, core in zip(labels, cores):
        log_line = (
            f"  - {lbl:>15} -> "
            f"repas={core['repas']} | "
            f"titre={core['titre']} | "
            f"logement_lignes={len(core['logement'])}"
        )
        logging.info(log_line)
        if core["logement"]:
            logging.info(f"    logement[0] = {core['logement'][0]}")
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


def update_config_in_supabase(
    supabase: Client,
    current_row: Optional[Dict[str, Any]],
    new_core_data: Dict[str, Any],  # Le dictionnaire normalisé (repas, titre, logement)
    source_links: List[str],
) -> None:
    """
    Compare l'ancien et le nouveau 'core' et exécute la bonne action BDD.
    N'utilise PAS apply_patch_in_memory car on remplace le bloc entier.
    """
    comment = f"Mise à jour automatique: {CONFIG_KEY_TO_UPDATE}"

    # On retire la clé __src avant de comparer ou d'écrire en BDD
    if "__src" in new_core_data:
        del new_core_data["__src"]

    # Scénario 0 (Cold Start) : current_row est None
    if current_row is None:
        logging.info(
            f"Aucune config existante. Insertion de la v1 pour '{CONFIG_KEY_TO_UPDATE}'."
        )
        new_row = {
            "config_key": CONFIG_KEY_TO_UPDATE,
            "config_data": new_core_data,  # Le core est le config_data
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
    # On compare directement le config_data (qui est notre 'core')
    if current_config_data == new_core_data:
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
            "config_data": new_core_data,  # Le nouveau core
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
    """Orchestre l'ensemble du processus de mise à jour des Avantages en Nature."""
    logging.info("--- DÉBUT Orchestrateur Avantages en Nature ---")

    try:
        # 1. Lancer tous les scrapers
        labels = [lbl for lbl, _ in SCRIPTS_TO_RUN]
        payloads: List[Dict[str, Any]] = []
        for label, path in SCRIPTS_TO_RUN:
            payload = run_script(label, path)
            if not payload:
                logging.warning(
                    f"Le script {label} n'a retourné aucun payload. Ignoré."
                )
                continue
            payloads.append(payload)

        if not payloads:
            logging.critical("Aucun scraper n'a retourné de données. Arrêt.")
            sys.exit(1)

        # S'assure qu'au moins un scraper a réussi (nécessaire s'il n'y en a qu'un)
        if all(not p for p in payloads):
            logging.critical(
                "Tous les scrapers ont échoué ou n'ont retourné aucune donnée. Arrêt."
            )
            sys.exit(1)

        # 2. Normaliser les signatures
        cores = [payload_to_core(p) for p in payloads]

        # 3. Afficher la comparaison
        debug_comparison(labels, cores)

        # 4. Valider la concordance
        all_equal = all(cores_equal(cores[0], c) for c in cores[1:])

        if not all_equal:
            logging.error("Divergence entre les sources de scraping. Arrêt.")
            sys.exit(2)

        logging.info("Concordance des taux (Avantages en Nature) validée.")

        # Le 'core' validé et les sources
        final_core_data = cores[0]
        source_links = merge_sources(payloads, cores)

        # 5. Initialiser la BDD
        supabase = init_supabase_client()

        # 6. Lire l'état actuel (peut être None)
        current_row = fetch_active_config(supabase, CONFIG_KEY_TO_UPDATE)

        # 7. Comparer et écrire dans Supabase
        update_config_in_supabase(supabase, current_row, final_core_data, source_links)

        logging.info("--- FIN Orchestrateur Avantages en Nature ---")

    except SystemExit as e:
        logging.error(f"Arrêt contrôlé: {e}")
        sys.exit(int(str(e).split()[-1]) if str(e).split()[-1].isdigit() else 1)
    except Exception as e:
        logging.critical(f"Une erreur fatale est survenue: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
