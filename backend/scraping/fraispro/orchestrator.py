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
CONFIG_KEY_TO_UPDATE = "frais_pro"
# ID de l'item (non utilisé pour patcher, mais pour valider le payload)
ITEM_ID_TO_VALIDATE = "frais_pro"

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
    ("fraispro.py", os.path.join(os.path.dirname(__file__), "fraispro.py")),
    # ("fraispro_LegiSocial.py", os.path.join(os.path.dirname(__file__), "fraispro_LegiSocial.py")),
    # ("fraispro_AI.py", os.path.join(os.path.dirname(__file__), "fraispro_AI.py")),  
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

# --- Logique de normalisation (Conservée) ---

def _f(v: Any) -> Optional[float]:
    if v is None: return None
    try: return round(float(v), 6)
    except Exception: return None

def _norm_repas(d: Dict[str, Any]) -> Dict[str, Optional[float]]:
    d = d or {}
    return {
        "sur_lieu_travail": _f(d.get("sur_lieu_travail")),
        "hors_locaux_avec_restaurant": _f(d.get("hors_locaux_avec_restaurant")),
        "hors_locaux_sans_restaurant": _f(d.get("hors_locaux_sans_restaurant")),
    }

def _norm_petit_dep(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for x in lst or []:
        out.append({"km_min": int(x.get("km_min")), "km_max": int(x.get("km_max")), "montant": _f(x.get("montant"))})
    out.sort(key=lambda z: (z["km_min"], z["km_max"]))
    return out

def _norm_metropole(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for x in lst or []:
        out.append({
            "periode_sejour": str(x.get("periode_sejour", "")).strip().lower(),
            "repas": _f(x.get("repas")),
            "logement_paris_banlieue": _f(x.get("logement_paris_banlieue")),
            "logement_province": _f(x.get("logement_province")),
        })
    out.sort(key=lambda z: z["periode_sejour"])
    return out

def _norm_outre_mer(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for x in lst or []:
        out.append({
            "periode_sejour": str(x.get("periode_sejour", "")).strip().lower(),
            "hebergement": _f(x.get("hebergement")),
            "repas": _f(x.get("repas")),
        })
    out.sort(key=lambda z: z["periode_sejour"])
    return out

def _norm_mutation(d: Dict[str, Any]) -> Dict[str, Any]:
    d = d or {}
    hp = (d.get("hebergement_provisoire") or {})
    hd = (d.get("hebergement_definitif") or {})
    return {
        "hebergement_provisoire": {"montant_par_jour": _f(hp.get("montant_par_jour"))},
        "hebergement_definitif": {
            "frais_installation": _f(hd.get("frais_installation")),
            "majoration_par_enfant": _f(hd.get("majoration_par_enfant")),
            "plafond_total": _f(hd.get("plafond_total")),
        },
    }

def _norm_mobilite(d: Dict[str, Any]) -> Dict[str, Any]:
    d = d or {}
    priv = d.get("employeurs_prives") or {}
    pubs = []
    for x in d.get("employeurs_publics") or []:
        pubs.append({
            "jours_utilises": str(x.get("jours_utilises", "")).strip().lower(),
            "montant_annuel": _f(x.get("montant_annuel")),
        })
    pubs.sort(key=lambda z: z["jours_utilises"])
    return {
        "employeurs_prives": {
            "limite_base": _f(priv.get("limite_base")),
            "limite_cumul_transport_public": _f(priv.get("limite_cumul_transport_public")),
            "limite_cumul_carburant_total": _f(priv.get("limite_cumul_carburant_total")),
            "limite_cumul_carburant_part_carburant": _f(priv.get("limite_cumul_carburant_part_carburant")),
        },
        "employeurs_publics": pubs,
    }

def _norm_teletravail(d: Dict[str, Any]) -> Dict[str, Any]:
    d = d or {}
    sans = d.get("indemnite_sans_accord") or {}
    avec = d.get("indemnite_avec_accord") or {}
    mat = d.get("materiel_informatique_perso") or {}
    return {
        "indemnite_sans_accord": {
            "par_jour": _f(sans.get("par_jour")),
            "limite_mensuelle": _f(sans.get("limite_mensuelle")),
            "par_mois_pour_1_jour_semaine": _f(sans.get("par_mois_pour_1_jour_semaine")),
        },
        "indemnite_avec_accord": {k: _f(v) for k, v in avec.items()} if isinstance(avec, dict) else {},
        "materiel_informatique_perso": {"montant_mensuel": _f(mat.get("montant_mensuel"))},
    }

def core_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise le payload complet de frais_pro."""
    if payload.get("id") != ITEM_ID_TO_VALIDATE:
        raise ValueError(f"ID '{ITEM_ID_TO_VALIDATE}' attendu, reçu '{payload.get('id')}'")
    
    sections = payload.get("sections", {}) or {}
    return {
        "id": ITEM_ID_TO_VALIDATE,
        "libelle": payload.get("libelle", "Frais professionnels"),
        "sections": {
            "repas": _norm_repas(sections.get("repas")),
            "petit_deplacement": _norm_petit_dep(sections.get("petit_deplacement")),
            "grand_deplacement": {
                "metropole": _norm_metropole((sections.get("grand_deplacement") or {}).get("metropole")),
                "outre_mer_groupe1": _norm_outre_mer((sections.get("grand_deplacement") or {}).get("outre_mer_groupe1")),
                "outre_mer_groupe2": _norm_outre_mer((sections.get("grand_deplacement") or {}).get("outre_mer_groupe2")),
            },
            "mutation_professionnelle": _norm_mutation(sections.get("mutation_professionnelle")),
            "mobilite_durable": _norm_mobilite(sections.get("mobilite_durable")),
            "teletravail": _norm_teletravail(sections.get("teletravail")),
        },
    }

# --- Logique de comparaison (Conservée) ---

def _eq_float(a: Optional[float], b: Optional[float], tol: float = 1e-6) -> bool:
    if a is None or b is None: return a is b
    return abs(float(a) - float(b)) <= tol

def _eq_repas(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return all(_eq_float(a.get(k), b.get(k)) for k in ("sur_lieu_travail", "hors_locaux_avec_restaurant", "hors_locaux_sans_restaurant"))

def _eq_petit_dep(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b): return False
    for x, y in zip(a, b):
        if x["km_min"] != y["km_min"] or x["km_max"] != y["km_max"]: return False
        if not _eq_float(x["montant"], y["montant"]): return False
    return True

def _eq_metropole(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b): return False
    for x, y in zip(a, b):
        if x["periode_sejour"] != y["periode_sejour"]: return False
        if not (_eq_float(x["repas"], y["repas"]) and _eq_float(x["logement_paris_banlieue"], y["logement_paris_banlieue"]) and _eq_float(x["logement_province"], y["logement_province"])): return False
    return True

def _eq_outre_mer(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b): return False
    for x, y in zip(a, b):
        if x["periode_sejour"] != y["periode_sejour"]: return False
        if not (_eq_float(x["hebergement"], y["hebergement"]) and _eq_float(x["repas"], y["repas"])): return False
    return True

def _eq_mutation(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return (
        _eq_float(a["hebergement_provisoire"].get("montant_par_jour"), b["hebergement_provisoire"].get("montant_par_jour"))
        and _eq_float(a["hebergement_definitif"].get("frais_installation"), b["hebergement_definitif"].get("frais_installation"))
        and _eq_float(a["hebergement_definitif"].get("majoration_par_enfant"), b["hebergement_definitif"].get("majoration_par_enfant"))
        and _eq_float(a["hebergement_definitif"].get("plafond_total"), b["hebergement_definitif"].get("plafond_total"))
    )

def _eq_mobilite(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    pa, pb = a["employeurs_prives"], b["employeurs_prives"]
    if not all(_eq_float(pa.get(k), pb.get(k)) for k in ("limite_base", "limite_cumul_transport_public", "limite_cumul_carburant_total", "limite_cumul_carburant_part_carburant")): return False
    la, lb = a["employeurs_publics"], b["employeurs_publics"]
    if len(la) != len(lb): return False
    for x, y in zip(la, lb):
        if x["jours_utilises"] != y["jours_utilises"]: return False
        if not _eq_float(x["montant_annuel"], y["montant_annuel"]): return False
    return True

def _eq_teletravail(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    sa, sb = a["indemnite_sans_accord"], b["indemnite_sans_accord"]
    if not all(_eq_float(sa.get(k), sb.get(k)) for k in ("par_jour", "limite_mensuelle", "par_mois_pour_1_jour_semaine")): return False
    aa, ab = a.get("indemnite_avec_accord", {}), b.get("indemnite_avec_accord", {})
    if set(aa.keys()) != set(ab.keys()): return False
    for k in aa.keys():
        if not _eq_float(_f(aa[k]), _f(ab[k])): return False
    ma, mb = a["materiel_informatique_perso"], b["materiel_informatique_perso"]
    return _eq_float(ma.get("montant_mensuel"), mb.get("montant_mensuel"))

def equal_core(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Compare deux signatures 'frais_pro' complètes."""
    sa, sb = a["sections"], b["sections"]
    return (
        _eq_repas(sa["repas"], sb["repas"]) and
        _eq_petit_dep(sa["petit_deplacement"], sb["petit_deplacement"]) and
        _eq_metropole(sa["grand_deplacement"]["metropole"], sb["grand_deplacement"]["metropole"]) and
        _eq_outre_mer(sa["grand_deplacement"]["outre_mer_groupe1"], sb["grand_deplacement"]["outre_mer_groupe1"]) and
        _eq_outre_mer(sa["grand_deplacement"]["outre_mer_groupe2"], sb["grand_deplacement"]["outre_mer_groupe2"]) and
        _eq_mutation(sa["mutation_professionnelle"], sb["mutation_professionnelle"]) and
        _eq_mobilite(sa["mobilite_durable"], sb["mobilite_durable"]) and
        _eq_teletravail(sa["teletravail"], sb["teletravail"])
    )


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


def _head_repas(s: Dict[str, Any]) -> str:
    r = s["sections"]["repas"]
    return f"repas[site={r.get('sur_lieu_travail')}, resto={r.get('hors_locaux_avec_restaurant')}, hors_locaux={r.get('hors_locaux_sans_restaurant')}]"

def debug_mismatch(payloads: List[Dict[str, Any]], sigs: List[Dict[str, Any]]) -> None:
    logging.warning("DISCORDANCE entre les sources pour Frais Pro:")
    for p, s in zip(payloads, sigs):
        script = p.get("__script", "?")
        logging.warning(f"  - {script}: {_head_repas(s)}")

def debug_success(sigs: List[Dict[str, Any]]) -> None:
    logging.info(f"Concordance des taux Frais Pro trouvée => {_head_repas(sigs[0])}")


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
    new_config_data: Dict[str, Any], # ✅ Le bloc {"FRAIS_PRO": [...]}
    source_links: List[str],
) -> None:
    """
    Compare l'ancien et le nouveau 'core' et exécute la bonne action BDD.
    """
    comment = f"Mise à jour automatique: {CONFIG_KEY_TO_UPDATE}"
    
    # Scénario 0 (Cold Start) : current_row est None
    if current_row is None:
        logging.info(f"Aucune config existante. Insertion de la v1 pour '{CONFIG_KEY_TO_UPDATE}'.")
        new_row = {
            "config_key": CONFIG_KEY_TO_UPDATE,
            "config_data": new_config_data, # ✅ On stocke le bloc complet
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
    # Comparaison directe du bloc JSON complet
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
            "config_data": new_config_data, # Le nouveau bloc {"FRAIS_PRO": [...]}
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
    """Orchestre l'ensemble du processus de mise à jour des Frais Professionnels."""
    logging.info(f"--- DÉBUT Orchestrateur Frais Professionnels ---")
    
    try:
        # 1. Lancer tous les scrapers
        payloads: List[Dict[str, Any]] = []
        labels: List[str] = []
        
        for label, path in SCRIPTS_TO_RUN:
            payloads.append(run_script(label, path))
            labels.append(label)
        
        if not payloads:
            logging.critical("Aucun scraper n'a retourné de données. Arrêt.")
            sys.exit(1)

        # 2. Normaliser les signatures
        sigs: List[Dict[str, Any]] = []
        for i, p in enumerate(payloads):
            try:
                sigs.append(core_signature(p))
            except (ValueError, SystemExit) as e:
                logging.error(f"Normalisation échouée pour {labels[i]}: {e}")
                sys.exit(2)

        # 3. Valider la concordance
        ok = True
        for i in range(len(sigs) - 1):
            if not equal_core(sigs[i], sigs[i + 1]):
                ok = False
                break

        if not ok:
            debug_mismatch(payloads, sigs)
            logging.error("Divergence entre les sources de scraping. Arrêt.")
            sys.exit(2)

        debug_success(sigs)
        
        # Le 'core' validé et les sources
        final_core_data = sigs[0]
        
        # ✅ CORRECTION: Reconstruire le format de fichier d'origine pour le stockage
        final_data_to_store = {
            "FRAIS_PRO": [final_core_data]
        }
        
        source_links = merge_sources(payloads)

        # 4. Initialiser la BDD
        supabase = init_supabase_client()
        
        # 5. Lire l'état actuel (peut être None)
        current_row = fetch_active_config(supabase, CONFIG_KEY_TO_UPDATE)
        
        # 6. Comparer et écrire dans Supabase
        update_config_in_supabase(
            supabase, 
            current_row, 
            final_data_to_store, # On stocke le bloc complet {"FRAIS_PRO": [...]}
            source_links
        )
        
        logging.info(f"--- FIN Orchestrateur Frais Professionnels ---")
        
    except SystemExit as e:
        logging.error(f"Arrêt contrôlé: {e}")
        sys.exit(int(str(e).split()[-1]) if str(e).split()[-1].isdigit() else 1)
    except Exception as e:
        logging.critical(f"Une erreur fatale est survenue: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()