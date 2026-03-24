import json
import sys
import os
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, List
from supabase import create_client, Client


def ChargerContexte(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    baremes: Dict[str, Any],
) -> "ContextePaie":
    """
    Construit un ContextePaie à partir de dictionnaires en mémoire (simulation, calcul inverse).
    Crée des fichiers temporaires puis instancie ContextePaie.
    Les barèmes passés ne sont pas utilisés ici : ContextePaie charge les barèmes depuis Supabase.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="payroll_ctx_"))
    try:
        # Contrat minimal à partir des données employé (Supabase ou manuelles)
        contrat = {
            "contrat": {
                "statut": employee_data.get("statut", "Non-Cadre"),
                "temps_travail": {"duree_hebdomadaire": float(employee_data.get("duree_hebdomadaire", 35))},
                "emploi": employee_data.get("emploi", ""),
                "date_entree": employee_data.get("date_entree", ""),
            },
            "remuneration": {
                "salaire_de_base": {"valeur": float(employee_data.get("salaire_base", 0))},
                "avantages_en_nature": employee_data.get("avantages_en_nature") or {},
                "convention_collective": employee_data.get("convention_collective") or {},
                "classification_conventionnelle": employee_data.get("classification_conventionnelle") or {},
            },
            "salarie": {
                "prenom": employee_data.get("first_name", ""),
                "nom": employee_data.get("last_name", ""),
                "nir": employee_data.get("nir", ""),
            },
            "saisie_du_mois": {},
            "specificites_paie": {
                "prevoyance": employee_data.get("prevoyance", "NON"),
                "prelevement_a_la_source": {"taux": float(employee_data.get("taux_prelevement_source", 0))},
                "mutuelle": employee_data.get("mutuelle") or {},
                "titres_restaurant": employee_data.get("titres_restaurant") or {},
                "transport": employee_data.get("transport") or {},
                "is_alsace_moselle": bool(employee_data.get("is_alsace_moselle", False)),
            },
        }
        chemin_contrat = temp_dir / "contrat.json"
        chemin_contrat.write_text(json.dumps(contrat), encoding="utf-8")

        # Entreprise : wrapper si nécessaire
        entreprise_wrapper = (
            company_data if "entreprise" in company_data else {"entreprise": company_data}
        )
        chemin_entreprise = temp_dir / "entreprise.json"
        chemin_entreprise.write_text(json.dumps(entreprise_wrapper), encoding="utf-8")

        cumuls = {"cumuls": {}}
        chemin_cumuls = temp_dir / "cumuls.json"
        chemin_cumuls.write_text(json.dumps(cumuls), encoding="utf-8")

        ctx = ContextePaie(
            chemin_contrat=str(chemin_contrat),
            chemin_entreprise=str(chemin_entreprise),
            chemin_cumuls=str(chemin_cumuls),
            chemin_data_dir=str(temp_dir),
        )
        return ctx
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


class ContextePaie:
    def __init__(self, chemin_contrat: str, chemin_entreprise: str, chemin_cumuls: str, chemin_data_dir: str = 'data'):
        """
        Initialise le contexte en chargeant les données statiques (contrat, entreprise)
        puis en les surchargeant avec les barèmes dynamiques de Supabase.
        """
        # ✅ CORRECTION: Tous les 'print' sont redirigés vers sys.stderr
        print("INFO: Initialisation du contexte de paie (Mode Supabase)...", file=sys.stderr)
        
        print("\n--- 🔍 DEBUG CONTEXTE: Chargement des fichiers initiaux ---", file=sys.stderr)
        print(f"  -> Chemin contrat: {chemin_contrat}", file=sys.stderr)
        data_dir = Path(chemin_data_dir)

        # --- ÉTAPE 1 : Chargement des fichiers locaux (Contrat, Cumuls, Fichier Entreprise) ---
        entreprise_data = self._load_json(chemin_entreprise)
        self.entreprise = (entreprise_data or {}).get('entreprise', {})
        
        contrat_brut = self._load_json(chemin_contrat)
        if contrat_brut is None:
            print("ERREUR: Le fichier contrat.json est vide ou contient 'null'. Vérifiez les données employé en base.", file=sys.stderr)
            raise ValueError(
                "Le fichier contrat.json est vide ou contient 'null'. "
                "Vérifiez que les données de l'employé (employees) sont complètes en production."
            )
        self.contrat = contrat_brut
        
        cumuls_data = self._load_json(chemin_cumuls)
        # S'assurer que cumuls est toujours un dictionnaire, même vide
        self.cumuls = cumuls_data if cumuls_data is not None else {}
        
        # DEBUG SPÉCIFIQUE PRÉVOYANCE
        prevoyance_data = self.contrat.get('specificites_paie', {}).get('prevoyance', 'NON TROUVÉE')
        print(f"  -> Données 'prevoyance' lues du contrat: {json.dumps(prevoyance_data)}", file=sys.stderr)
        print("--- FIN DEBUG CONTEXTE ---\n", file=sys.stderr)
        # --- ÉTAPE 2 : Connexion à Supabase ---
        try:
            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_SERVICE_KEY"] # Doit être la clé de service
            if not supabase_url or not supabase_key:
                raise KeyError
            supabase: Client = create_client(supabase_url, supabase_key)
        except KeyError:
            # ✅ CORRECTION: Redirigé vers sys.stderr
            print("ERREUR: Variables SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes.", file=sys.stderr)
            raise RuntimeError("Variables d'environnement Supabase non configurées.")
        except Exception as e:
            # ✅ CORRECTION: Redirigé vers sys.stderr
            print(f"ERREUR: Échec de l'initialisation du client Supabase: {e}", file=sys.stderr)
            raise
            
        # ✅ CORRECTION: Redirigé vers sys.stderr
        print("INFO: Connexion Supabase établie. Chargement des barèmes...", file=sys.stderr)

        # --- ÉTAPE 3 : Chargement des barèmes depuis Supabase ---
        try:
            configs = supabase.table('payroll_config') \
                .select('config_key, config_data') \
                .eq('is_active', True) \
                .execute()
                
            if not configs.data:
                 raise RuntimeError("Aucune configuration de paie active trouvée dans Supabase.")
                 
            def _ensure_dict(val: Any) -> Dict[str, Any]:
                """Si config_data est renvoyé comme chaîne JSON (ex. par le client), le parser."""
                if val is None:
                    return {}
                if isinstance(val, str):
                    try:
                        return json.loads(val)
                    except json.JSONDecodeError:
                        return {}
                return val if isinstance(val, dict) else {}

            db_baremes = {c['config_key']: _ensure_dict(c.get('config_data')) for c in configs.data}
            
        except Exception as e:
            # ✅ CORRECTION: Redirigé vers sys.stderr
            print(f"ERREUR CRITIQUE: Impossible de lire 'payroll_config' depuis Supabase. {e}", file=sys.stderr)
            raise

        # --- ÉTAPE 3b : Chargement des règles par convention collective (table convention_collective_rules) ---
        conventions_collectives = {}
        try:
            cc_rules_resp = supabase.table('convention_collective_rules').select('idcc, rules').execute()
            if cc_rules_resp.data:
                for row in cc_rules_resp.data:
                    idcc = row.get('idcc')
                    rules = _ensure_dict(row.get('rules'))
                    if idcc:
                        conventions_collectives[f"idcc_{idcc}"] = rules
        except Exception as e:
            print(f"WARN: Impossible de lire 'convention_collective_rules' depuis Supabase: {e}. Règles CC vides.", file=sys.stderr)

        # --- ÉTAPE 4 : Assignation à self.baremes ---
        # 'pas' stocke un objet avec clé 'baremes' ; les autres config_data sont des dicts
        pas_data = db_baremes.get('pas', {})
        if isinstance(pas_data, dict):
            pas_baremes = pas_data.get('baremes', [])
        else:
            pas_baremes = []

        # 'primes' : catalogue depuis payroll_config (config_key='primes')
        primes_data = db_baremes.get('primes', {})
        if isinstance(primes_data, dict):
            primes_list = primes_data.get('primes', [])
        elif isinstance(primes_data, list):
            primes_list = primes_data
        else:
            primes_list = []
        if not isinstance(primes_list, list):
            primes_list = []

        self.baremes = {
            "cotisations": db_baremes.get('cotisations', {}),
            "pas": pas_baremes,
            "smic": db_baremes.get('smic', {}),
            "pss": db_baremes.get('pss', {}),
            "frais_pro": db_baremes.get('frais_pro', {}),
            "heures_supp": db_baremes.get('heures_supp', {}),
            "primes": primes_list,
            "conventions_collectives": conventions_collectives
        }
        if not self.baremes["heures_supp"]:
            print("WARN: 'heures_supp' absent de payroll_config. Exécutez le seed ou la migration pour insérer les règles heures supplémentaires.", file=sys.stderr)
        if not self.baremes["primes"]:
            print("WARN: 'primes' absent de payroll_config. Exécutez le seed ou la migration pour insérer le catalogue des primes.", file=sys.stderr)
        if not self.baremes["conventions_collectives"]:
            print("WARN: Aucune règle dans convention_collective_rules. Exécutez la migration 66 pour insérer les règles par IDCC.", file=sys.stderr)

        # --- ÉTAPE 5 : Surcharge des Avantages en Nature ---
        avantages_db = db_baremes.get('avantages_en_nature')
        if avantages_db:
            paie_params = self.entreprise.setdefault('parametres_paie', {})
            avantages_local = paie_params.setdefault('avantages_en_nature', {})
            
            avantages_surcharges = {
                "repas_valeur_forfaitaire": avantages_db.get("repas"),
                "titre_restaurant_exoneration_max_patronale": avantages_db.get("titre"),
                "logement_bareme_forfaitaire": [
                    {
                        "remuneration_max": row.get("remuneration_max_eur"),
                        "valeur_1_piece": row.get("valeur_1_piece_eur"),
                        "valeur_par_piece": row.get("valeur_par_piece_suppl_eur"),
                    } for row in avantages_db.get("logement", [])
                ]
            }
            
            avantages_local.update(avantages_surcharges)
            # ✅ CORRECTION: Redirigé vers sys.stderr
            print("INFO: Surcharge des 'avantages_en_nature' depuis Supabase effectuée.", file=sys.stderr)
        else:
            # ✅ CORRECTION: Redirigé vers sys.stderr
            print("WARN: 'avantages_en_nature' non trouvés dans Supabase, utilisation des valeurs du fichier entreprise.json local.", file=sys.stderr)

        # ✅ CORRECTION: Redirigé vers sys.stderr
        print("INFO: Contexte chargé avec succès (Mode Supabase).", file=sys.stderr)


    def _load_json(self, file_path: Path | str) -> Dict[str, Any] | None:
        """Fonction utilitaire pour charger un fichier JSON en gérant les erreurs."""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                print(f"AVERTISSEMENT: Le fichier JSON '{file_path}' est introuvable. Retour de None.", file=sys.stderr)
                return None
            with open(file_path_obj, 'r', encoding='utf-8') as f:
                content = json.load(f)
                # Si le fichier est vide ou contient null, retourner None
                if content is None:
                    return None
                return content
        except FileNotFoundError:
            # ✅ CORRECTION: Redirigé vers sys.stderr
            print(f"AVERTISSEMENT: Le fichier JSON '{file_path}' est introuvable. Retour de None.", file=sys.stderr)
            return None
        except json.JSONDecodeError as e:
            # ✅ CORRECTION: Redirigé vers sys.stderr
            print(f"ERREUR: Le fichier JSON '{file_path}' est mal formaté. Détails: {e}", file=sys.stderr)
            raise

    # --- Propriétés d'accès rapide (Données "statiques") ---
    
    @property
    def effectif(self) -> int:
        """Retourne l'effectif de l'entreprise."""
        return self.entreprise.get('parametres_paie', {}).get('effectif', 0)

    @property
    def statut_salarie(self) -> str:
        """Retourne le statut du salarié ('Cadre' ou 'Non-Cadre')."""
        return self.contrat.get('contrat', {}).get('statut', 'Non-Cadre')

    @property
    def salaire_base_mensuel(self) -> float:
        """Retourne le salaire de base brut mensuel."""
        return self.contrat.get('remuneration', {}).get('salaire_de_base', {}).get('valeur', 0.0)

    @property
    def duree_hebdo_contrat(self) -> float:
        """Retourne la durée hebdomadaire de travail du contrat."""
        return self.contrat.get('contrat', {}).get('temps_travail', {}).get('duree_hebdomadaire', 35)

    @property
    def is_alsace_moselle(self) -> bool:
        """Indique si le salarié dépend du régime Alsace-Moselle."""
        return self.contrat.get('specificites_paie', {}).get('is_alsace_moselle', False)

    @property
    def is_forfait_jour(self) -> bool:
        """
        Indique si le salarié est en forfait jour.
        La détection se fait via le statut qui doit contenir "forfait jour" (insensible à la casse).
        """
        statut = self.statut_salarie
        if not statut:
            return False
        return 'forfait jour' in statut.lower()

    # --- Propriétés d'accès rapide (Données "variables" du mois) ---

    @property
    def saisie_du_mois(self) -> dict:
        """Retourne le dictionnaire des variables mensuelles."""
        return self.contrat.get('saisie_du_mois', {})

    @property
    def heures_sup_du_mois(self) -> float:
        """Retourne les heures supplémentaires conjoncturelles du mois."""
        return self.saisie_du_mois.get('heures_supplementaires_conjoncturelles', 0.0)

    @property
    def heures_absence_du_mois(self) -> float:
        """Retourne les heures d'absence non maintenues du mois."""
        return self.saisie_du_mois.get('heures_absence_non_maintenues', 0.0)
    
    @property
    def primes_du_mois(self) -> dict:
        """Retourne les primes exceptionnelles du mois."""
        return self.saisie_du_mois.get('primes_saisies', {})
    

    @property
    def cumuls_annee_precedente(self) -> dict:
        """Retourne le dictionnaire des cumuls arrêtés à la fin du mois précédent."""
        return self.cumuls.get('cumuls', {})

    # --- Fonctions utilitaires ---

    def get_cotisation_by_id(self, coti_id: str) -> Dict[str, Any] | None:
        """Récupère une ligne de cotisation par son ID depuis self.baremes."""
        
        cotisations_data = self.baremes.get('cotisations', {})
        
        root_key = next((k for k, v in cotisations_data.items() if isinstance(v, list)), None)
        
        cotisations_list = []
        if not root_key:
             if isinstance(cotisations_data, list):
                 cotisations_list = cotisations_data
             else:
                # ✅ CORRECTION: Redirigé vers sys.stderr
                 print(f"WARN: Structure 'cotisations' non reconnue dans self.baremes pour get_cotisation_by_id.", file=sys.stderr)
                 return None
        else:
            cotisations_list = cotisations_data.get(root_key, [])
            
        for coti in cotisations_list:
            if coti.get('id') == coti_id:
                return coti
        return None