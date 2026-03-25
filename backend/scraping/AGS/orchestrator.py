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
ITEM_ID_TO_PATCH = "ags"

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
    ("AGS.py", os.path.join(os.path.dirname(__file__), "AGS.py")),
    ("AGS_AI.py", os.path.join(os.path.dirname(__file__), "AGS_AI.py")),
    ("AGS_LegiSocial.py", os.path.join(os.path.dirname(__file__), "AGS_LegiSocial.py")),
]


# --- 1. Fonctions de Scraping & Validation (Standardisées) ---

def iso_now() -> str:
    """Retourne la date/heure actuelle au format ISO UTC."""
    return datetime.now(timezone.utc).isoformat()


def run_script(label: str, path: str, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Exécute un scraper et récupère son JSON depuis stdout. env: env pour le subprocess (ORCHESTRATOR_EST_ETT pour AGS)."""
    run_env = env if env is not None else os.environ.copy()
    logging.info(f"Exécution du scraper: {label}...")
    try:
        proc = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=run_env,
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
    """Normalise le payload en une signature comparable pour l'AGS."""
    if payload.get("id") != ITEM_ID_TO_PATCH:
        raise ValueError(f"ID '{ITEM_ID_TO_PATCH}' attendu, reçu '{payload.get('id')}'")
    
    patro_raw = payload.get("valeurs", {}).get("patronal", None)
    patro = None
    if patro_raw is not None:
        try:
            patro = round(float(patro_raw), 6)
        except (ValueError, TypeError):
            logging.warning(f"Valeur patronale non numérique '{patro_raw}' reçue de {payload.get('__script')}. Traitée comme None.")
            
    return {
        "id": payload.get("id"),
        "libelle": payload.get("libelle"),
        "base": payload.get("base"),
        "valeurs": {"salarial": None, "patronal": patro},
    }


def compare_floats(a: float | None, b: float | None, tol: float = 1e-9) -> bool:
    """Compare deux floats (ou None) avec une tolérance."""
    if a is None or b is None:
        return a is b  # Vrai seulement si les deux sont None
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
            if not isinstance(s, dict): continue
            url = s.get("url")
            if url and isinstance(url, str) and url.strip() not in seen_urls:
                url = url.strip()
                seen_urls.add(url)
                source_links.append(url)
    return source_links


def debug_mismatch(payloads: List[Dict[str, Any]], sigs: List[Dict[str, Any]]) -> None:
    """Logge les détails d'une discordance de taux."""
    logging.warning("DISCORDANCE entre les sources pour AGS:")
    line = " | ".join(f"{p.get('__script','?')}={s.get('valeurs',{}).get('patronal', 'N/A')}" for p, s in zip(payloads, sigs))
    logging.warning(f"  ► Comparatif: {line}")


def debug_success(payloads: List[Dict[str, Any]], sigs: List[Dict[str, Any]]) -> None:
    """Logge les détails d'une concordance de taux."""
    line = " | ".join(f"{p.get('__script','?')}={s.get('valeurs',{}).get('patronal', 'N/A')}" for p, s in zip(payloads, sigs))
    logging.info(f"Concordance des taux AGS trouvée => {line}")


# --- 2. Fonctions Supabase (Standardisées et Corrigées) ---

def init_supabase_client() -> Client:
    """Initialise et retourne le client Supabase."""
    supabase_url = os.environ.get("SUPABASE_URL")
    
    # ✅ CORRECTION: S'assurer que la variable SUPABASE_SERVICE_KEY est utilisée
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") 
    
    if not supabase_url or not supabase_key:
        logging.critical("Variables SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes.")
        logging.critical("Assurez-vous que .env contient SUPABASE_SERVICE_KEY (la clé 'service_role') et non la clé 'anon'.")
        raise EnvironmentError("Variables Supabase non définies ou clé de service manquante.")
    
    try:
        client: Client = create_client(supabase_url, supabase_key)
        logging.info("Connexion Supabase établie.")
        return client
    except Exception as e:
        logging.critical(f"Échec de l'initialisation du client Supabase: {e}")
        raise


def fetch_active_config(supabase: Client, config_key: str) -> Optional[Dict[str, Any]]:
    """
    Récupère la configuration active pour une clé donnée.
    Retourne None si non trouvée.
    """
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
        
        # ✅ CORRECTION: Gérer le cas où execute() retourne None à cause d'une erreur
        if response is None:
            logging.error("La requête execute() a retourné 'None'. Problème de connexion, de permission (406) ou d'API.")
            return None
            
        # response.data sera None si 0 lignes, ou le dict si 1 ligne
        return response.data
    
    except Exception as e:
        # Intercepte les erreurs (ex: 2+ lignes actives, ce qui violerait .maybe_single())
        logging.error(f"Impossible de récupérer la config active '{config_key}'. Erreur: {e}")
        raise


def apply_patch_in_memory(
    current_config_data: Optional[Dict[str, Any]], ags_patch: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Met à jour le bloc 'cotisations' complet avec le nouveau patch AGS.
    Crée un nouveau bloc si 'current_config_data' est None.
    """
    logging.info(f"Application du patch '{ITEM_ID_TO_PATCH}' en mémoire...")
    
    if current_config_data:
        # Cas normal : copie profonde pour éviter les mutations
        new_config_data = json.loads(json.dumps(current_config_data))
    else:
        # Cas "Cold Start" : crée un bloc de cotisations vide
        logging.warning(f"Aucune config '{CONFIG_KEY_TO_UPDATE}' trouvée. Création d'un nouveau bloc.")
        new_config_data = {"cotisations": []} # Structure de base

    cotisations_list = new_config_data.get("cotisations", [])
    found = False
    
    # Prépare le patch (formaté comme dans cotisations.json)
    patch_data = {
        "id": ags_patch["id"],
        "libelle": ags_patch["libelle"],
        "base": ags_patch["base"],
        "salarial": ags_patch["valeurs"]["salarial"],
        "patronal": ags_patch["valeurs"]["patronal"],
    }

    for i, item in enumerate(cotisations_list):
        if isinstance(item, dict) and item.get("id") == ITEM_ID_TO_PATCH:
            # Fusionne le patch avec l'existant pour préserver les clés inconnues
            updated_item = {**item, **patch_data}
            cotisations_list[i] = updated_item
            found = True
            break
    
    if not found:
        logging.warning(f"Item '{ITEM_ID_TO_PATCH}' non trouvé. Ajout au bloc de cotisations.")
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
    
    # Scénario 0 (Cold Start) : current_row est None
    if current_row is None:
        logging.info(f"Aucune config existante. Insertion de la v1 pour '{CONFIG_KEY_TO_UPDATE}'.")
        new_row = {
            "config_key": CONFIG_KEY_TO_UPDATE,
            "config_data": new_config_data,
            "version": 1, # Première version
            "is_active": True,
            "comment": f"Création initiale: {ITEM_ID_TO_PATCH}",
            "last_checked_at": iso_now(),
            "source_links": source_links,
        }
        try:
            supabase.table("payroll_config").insert(new_row).execute()
            logging.info(f"✅ Succès: '{CONFIG_KEY_TO_UPDATE}' v1 créée.")
        except Exception as e:
            logging.error(f"Échec de l'insertion initiale. Erreur: {e}")
            raise
        return # Fin de la fonction ici

    # --- Les scénarios 1 et 2 ne s'exécutent que si une ligne existe ---
    current_config_data = current_row["config_data"]
    current_id = current_row["id"]
    current_version = current_row["version"]
    
    # --- SCÉNARIO 1 : IDENTIQUE ---
    if current_config_data == new_config_data:
        logging.info(f"Les données '{ITEM_ID_TO_PATCH}' sont inchangées. Mise à jour de 'last_checked_at'.")
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
        logging.warning(f"Différence détectée pour '{ITEM_ID_TO_PATCH}'. Création de la version {current_version + 1}...")
        
        new_row = {
            "config_key": CONFIG_KEY_TO_UPDATE,
            "config_data": new_config_data,
            "version": current_version + 1,
            "is_active": True,
            "comment": f"Mise à jour automatique: {ITEM_ID_TO_PATCH}",
            "last_checked_at": iso_now(),
            "source_links": source_links,
        }
        
        try:
            # Démarrer une "transaction" manuelle
            logging.info(f"Désactivation de la version {current_version} (ID: {current_id})...")
            supabase.table("payroll_config").update(
                {"is_active": False}
            ).eq("id", current_id).execute()
            
            logging.info(f"Insertion de la version {current_version + 1}...")
            supabase.table("payroll_config").insert(new_row).execute()
            
            logging.info(f"✅ Succès: '{CONFIG_KEY_TO_UPDATE}' mis à jour vers v{current_version + 1}.")
            
        except Exception as e:
            logging.error(f"Échec de la transaction de versioning. Erreur: {e}")
            # Tentative de rollback : réactiver l'ancienne version
            try:
                logging.warning(f"Tentative de rollback: Réactivation de la v{current_version} (ID: {current_id})...")
                supabase.table("payroll_config").update(
                    {"is_active": True}
                ).eq("id", current_id).execute()
            except Exception as rollback_e:
                logging.critical(f"ÉCHEC CRITIQUE DU ROLLBACK. BDD en état instable. Erreur: {rollback_e}")
            raise


# --- 3. Fonction Principale ---

def _build_run_env(supabase: Client) -> Dict[str, str]:
    """Construit l'env pour les scrapers : ORCHESTRATOR_EST_ETT depuis payroll_config si présent."""
    env = os.environ.copy()
    try:
        row = supabase.table("payroll_config").select("config_data").eq("config_key", "parametres_entreprise").eq("is_active", True).limit(1).execute()
        if row.data and len(row.data) > 0:
            data = row.data[0].get("config_data") or {}
            is_ett = bool(
                data.get("PARAMETRES_ENTREPRISE", {}).get("conditions_cotisations", {}).get("est_entreprise_travail_temporaire", False)
            )
            env["ORCHESTRATOR_EST_ETT"] = "1" if is_ett else "0"
        else:
            env["ORCHESTRATOR_EST_ETT"] = "0"
    except Exception:
        env["ORCHESTRATOR_EST_ETT"] = "0"
    return env


def main() -> None:
    """Orchestre l'ensemble du processus de mise à jour de l'AGS."""
    logging.info("--- DÉBUT Orchestrateur AGS ---")
    
    try:
        supabase = init_supabase_client()
        run_env = _build_run_env(supabase)

        # 1. Lancer tous les scrapers
        payloads: List[Dict[str, Any]] = []
        labels: List[str] = []
        for label, path in SCRIPTS_TO_RUN:
            payloads.append(run_script(label, path, env=run_env))
            labels.append(label)

        # 2. Normaliser les signatures
        sigs: List[Dict[str, Any]] = []
        for i, p in enumerate(payloads):
            try:
                sigs.append(core_signature(p))
            except ValueError as e:
                logging.error(f"Normalisation échouée pour {labels[i]}: {e}")
                raise SystemExit(f"Échec normalisation {labels[i]}")

        # 3. Valider la concordance
        all_equal = all(
            compare_floats(sigs[i]['valeurs']['patronal'], sigs[i+1]['valeurs']['patronal'])
            for i in range(len(sigs)-1)
        )

        if not all_equal:
            debug_mismatch(payloads, sigs) 
            logging.error("Divergence entre les sources de scraping. Arrêt.")
            sys.exit(2)
        
        debug_success(payloads, sigs) 
        
        # Le patch AGS validé et les sources
        ags_patch_data = sigs[0]
        source_links = merge_sources(payloads)

        # 5. Lire l'état actuel (supabase déjà initialisé) (peut être None)
        current_row = fetch_active_config(supabase, CONFIG_KEY_TO_UPDATE)
        
        # 6. Appliquer le patch en mémoire
        #    Passe current_row["config_data"] (le JSON) ou None si current_row est None
        new_config_data_blob = apply_patch_in_memory(
            current_row["config_data"] if current_row else None, 
            ags_patch_data
        )
        
        # 7. Comparer et écrire dans Supabase (même supabase)
        update_config_in_supabase(
            supabase, current_row, new_config_data_blob, source_links
        )
        
        logging.info("--- FIN Orchestrateur AGS ---")
        
    except SystemExit as e:
        logging.error(f"Arrêt contrôlé: {e}")
        sys.exit(int(str(e).split()[-1]) if str(e).split()[-1].isdigit() else 1)
    except Exception as e:
        logging.critical(f"Une erreur fatale est survenue: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()