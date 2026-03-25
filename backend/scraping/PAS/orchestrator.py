# scripts/PAS/orchestrator.py

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
CONFIG_KEY_TO_UPDATE = "pas"

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Trouver la racine du projet
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Charger les variables d'environnement
dotenv_path = os.path.join(REPO_ROOT, '.env')
if not os.path.exists(dotenv_path):
    logging.critical(f"Fichier .env non trouvé à: {dotenv_path}")
    sys.exit(1)
load_dotenv(dotenv_path=dotenv_path)

# Liste des scrapers à exécuter
SCRIPTS_TO_RUN: List[Tuple[str, str]] = [
    ("PAS.py", os.path.join(os.path.dirname(__file__), "PAS.py")),
    ("PAS_AI.py", os.path.join(os.path.dirname(__file__), "PAS_AI.py")),
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
        logging.error(f"Échec du scraper {label}. stderr: {e.stderr.strip()}")
        raise SystemExit(f"Échec du script {label}")
    except json.JSONDecodeError:
        logging.error(f"Sortie non-JSON de {label}. stdout: {proc.stdout[:200]}...")
        raise SystemExit(f"Sortie invalide du script {label}")
    except Exception as e:
        logging.error(f"Erreur inattendue avec {label}: {e}")
        raise


def core_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extrait et normalise la section des données pour la comparaison."""
    # Le payload brut contient {"id": "pas", "sections": {"metropole": [...], ...}}
    sections = payload.get("sections", {})
    
    # Transformation des données scrapées vers la structure cible
    # (identique à celle de 'pas.json')
    baremes_list = []
    for zone, tranches in sections.items():
        if isinstance(tranches, list):
            # S'assure que les tranches sont triées pour une comparaison stable
            tranches.sort(key=lambda x: (float('inf') if x.get("plafond") is None else x["plafond"]))
            baremes_list.append({
                "periode": "mensuel_2025", # Période déduite du contexte
                "zone": zone,
                "tranches": tranches
            })
    
    # Trie la liste des zones pour une comparaison stable
    baremes_list.sort(key=lambda x: x["zone"])
    return {"baremes": baremes_list}


def compare_floats(a: Optional[float], b: Optional[float], tol: float = 1e-6) -> bool:
    """Compare deux floats (ou None) avec une tolérance."""
    if a is None and b is None: return True
    if a is None or b is None: return False
    try:
        return math.isclose(float(a), float(b), abs_tol=tol)
    except (ValueError, TypeError):
        return False


def equal_core(sig_a: Dict, sig_b: Dict) -> Tuple[bool, Optional[str]]:
    """Compare deux signatures de données PAS (structures 'baremes')."""
    
    baremes_a = sig_a.get("baremes", [])
    baremes_b = sig_b.get("baremes", [])
    
    if len(baremes_a) != len(baremes_b):
        return False, f"Le nombre de zones de barème diffère ({len(baremes_a)} vs {len(baremes_b)})"

    # Les listes 'baremes' sont déjà triées par 'zone' par core_signature
    for zone_a, zone_b in zip(baremes_a, baremes_b):
        if zone_a.get("zone") != zone_b.get("zone"):
            return False, f"Zones de barème non alignées: {zone_a.get('zone')} vs {zone_b.get('zone')}"
        
        zone_name = zone_a.get("zone")
        tranches_a, tranches_b = zone_a.get("tranches", []), zone_b.get("tranches", [])
        
        if len(tranches_a) != len(tranches_b):
            return False, f"Mismatch dans '{zone_name}': le nombre de tranches diffère ({len(tranches_a)} vs {len(tranches_b)})"

        # Les listes 'tranches' sont déjà triées par 'plafond'
        for i, (tranche_a, tranche_b) in enumerate(zip(tranches_a, tranches_b)):
            if not compare_floats(tranche_a.get("plafond"), tranche_b.get("plafond")):
                return False, f"Mismatch dans '{zone_name}[{i}].plafond': {tranche_a.get('plafond')} != {tranche_b.get('plafond')}"
            if not compare_floats(tranche_a.get("taux"), tranche_b.get("taux")):
                return False, f"Mismatch dans '{zone_name}[{i}].taux': {tranche_a.get('taux')} != {tranche_b.get('taux')}"
                
    return True, None


def merge_sources(payloads: List[Dict[str, Any]]) -> List[str]:
    """Fusionne les URL sources uniques depuis les métadonnées."""
    seen_urls = set()
    source_links = []
    for p in payloads:
        for s in p.get("meta", {}).get("source", []):
            if not isinstance(s, dict): continue
            url = s.get("url")
            if url and isinstance(url, str) and url.strip() not in seen_urls:
                url = url.strip()
                seen_urls.add(url)
                source_links.append(url)
    return source_links


def debug_mismatch(script_a: str, script_b: str, details: str) -> None:
    """Affiche un message d'erreur clair."""
    logging.warning("DISCORDANCE entre les sources pour PAS:")
    logging.warning(f"  Comparaison entre '{script_a}' et '{script_b}'.")
    logging.warning(f"  ► Détail: {details}")


def debug_success(payloads: List[Dict[str, Any]]) -> None:
    """Logge les détails d'une concordance de taux."""
    scripts = [p.get("__script", "?") for p in payloads]
    logging.info(f"Concordance des barèmes PAS trouvée entre: {', '.join(scripts)}")


# --- 2. Fonctions Supabase (Standardisées) ---

def init_supabase_client() -> Client:
    """Initialise et retourne le client Supabase."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        logging.critical("Variables SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes.")
        logging.critical("Assurez-vous que .env contient SUPABASE_SERVICE_KEY (la clé 'service_role').")
        raise EnvironmentError("Variables Supabase non définies ou clé de service manquante.")
    
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
            logging.error("La requête execute() a retourné 'None'. Problème de connexion ou permission (406).")
            return None
        return response.data
    except Exception as e:
        logging.error(f"Impossible de récupérer la config active '{config_key}'. Erreur: {e}")
        raise


def update_config_in_supabase(
    supabase: Client,
    current_row: Optional[Dict[str, Any]],
    new_config_data: Dict[str, Any], # Le dict {"baremes": [...]}
    source_links: List[str],
) -> None:
    """
    Compare l'ancien et le nouveau bloc 'pas' et exécute la bonne action BDD.
    """
    comment = f"Mise à jour automatique: {CONFIG_KEY_TO_UPDATE}"

    # Scénario 0 (Cold Start) : current_row est None
    if current_row is None:
        logging.info(f"Aucune config existante. Insertion de la v1 pour '{CONFIG_KEY_TO_UPDATE}'.")
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
    # La comparaison se fait directement sur les blocs, qui sont déjà
    # normalisés et triés par core_signature.
    if current_config_data == new_config_data:
        logging.info(f"Les données '{CONFIG_KEY_TO_UPDATE}' sont inchangées. Mise à jour de 'last_checked_at'.")
        try:
            supabase.table("payroll_config").update(
                {
                    "last_checked_at": iso_now(),
                    "source_links": source_links,
                }
            ).eq("id", current_id).execute()
            logging.info("✅ Succès: 'last_checked_at' mis à jour.")
        except Exception as e:
            logging.error(f"Échec de la mise à jour 'last_checked_at' pour ID {current_id}. Erreur: {e}")
            raise
    
    # --- SCÉNARIO 2 : DIFFÉRENT ---
    else:
        logging.warning(f"Différence détectée pour '{CONFIG_KEY_TO_UPDATE}'. Création de la version {current_version + 1}...")
        
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
            logging.info(f"Désactivation de la version {current_version} (ID: {current_id})...")
            supabase.table("payroll_config").update(
                {"is_active": False}
            ).eq("id", current_id).execute()
            
            logging.info(f"Insertion de la version {current_version + 1}...")
            supabase.table("payroll_config").insert(new_row).execute()
            
            logging.info(f"✅ Succès: '{CONFIG_KEY_TO_UPDATE}' mis à jour vers v{current_version + 1}.")
            
        except Exception as e:
            logging.error(f"Échec de la transaction de versioning. Erreur: {e}")
            try:
                logging.warning(f"Tentative de rollback: Réactivation de la v{current_version} (ID: {current_id})...")
                supabase.table("payroll_config").update(
                    {"is_active": True}
                ).eq("id", current_id).execute()
            except Exception as rollback_e:
                logging.critical(f"ÉCHEC CRITIQUE DU ROLLBACK. BDD en état instable. Erreur: {rollback_e}")
            raise


# --- 3. Fonction Principale ---

def main() -> None:
    """Orchestre l'ensemble du processus de mise à jour du barème PAS."""
    logging.info("--- DÉBUT Orchestrateur PAS ---")
    
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

        # 3. Valider la concordance
        all_equal = True
        for i in range(len(sigs) - 1):
            are_equal, details = equal_core(sigs[i], sigs[i+1])
            if not are_equal:
                all_equal = False
                debug_mismatch(payloads[i]['__script'], payloads[i+1]['__script'], details)
                break

        if not all_equal:
            logging.error("Divergence entre les sources de scraping. Arrêt.")
            sys.exit(2)
        
        debug_success(payloads)
        
        # Le bloc de données validé et les sources
        # sigs[0] contient {"baremes": [...]}
        final_data_to_store = sigs[0]
        source_links = merge_sources(payloads)

        # 4. Initialiser la BDD
        supabase = init_supabase_client()
        
        # 5. Lire l'état actuel (peut être None)
        current_row = fetch_active_config(supabase, CONFIG_KEY_TO_UPDATE)
        
        # 6. Comparer et écrire dans Supabase
        update_config_in_supabase(
            supabase, 
            current_row, 
            final_data_to_store, 
            source_links
        )
        
        logging.info("--- FIN Orchestrateur PAS ---")
        
    except SystemExit as e:
        logging.error(f"Arrêt contrôlé: {e}")
        sys.exit(int(str(e).split()[-1]) if str(e).split()[-1].isdigit() else 1)
    except Exception as e:
        logging.critical(f"Une erreur fatale est survenue: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()