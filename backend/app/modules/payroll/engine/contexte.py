from app.core.logging import get_logger, log_payroll_debug

logger = get_logger("modules.payroll.engine.contexte")
import json
import os
import tempfile
import shutil
import calendar
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from supabase import create_client, Client

from .baremes_loader import (
    assembler_baremes,
    baremes_lookup,
    charger_conventions_collectives,
    charger_db_baremes,
    controler_integrite_baremes,
)
from . import legal_constants as lc


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
                "type_contrat": employee_data.get("type_contrat")
                or employee_data.get("contract_type")
                or "",
                "temps_travail": {
                    "duree_hebdomadaire": float(
                        employee_data.get("duree_hebdomadaire", 35)
                    )
                },
                "emploi": employee_data.get("emploi", ""),
                "date_entree": employee_data.get("date_entree", ""),
                "date_conclusion_contrat": employee_data.get(
                    "date_conclusion_contrat"
                )
                or "",
                "date_debut_execution": employee_data.get("date_debut_execution")
                or "",
            },
            "remuneration": {
                "salaire_de_base": {
                    "valeur": float(employee_data.get("salaire_base", 0))
                },
                "avantages_en_nature": employee_data.get("avantages_en_nature") or {},
                "convention_collective": employee_data.get("convention_collective")
                or {},
                "classification_conventionnelle": employee_data.get(
                    "classification_conventionnelle"
                )
                or {},
            },
            "salarie": {
                "prenom": employee_data.get("first_name", ""),
                "nom": employee_data.get("last_name", ""),
                "nir": employee_data.get("nir", ""),
                "date_naissance": employee_data.get("date_naissance") or "",
            },
            "saisie_du_mois": {},
            "specificites_paie": {
                "prevoyance": employee_data.get("prevoyance", "NON"),
                "prelevement_a_la_source": {
                    "taux": float(employee_data.get("taux_prelevement_source", 0))
                },
                "mutuelle": employee_data.get("mutuelle") or {},
                "titres_restaurant": employee_data.get("titres_restaurant") or {},
                "transport": employee_data.get("transport") or {},
                "is_alsace_moselle": bool(
                    employee_data.get("is_alsace_moselle", False)
                ),
                "maintien_regime_apprenti": bool(
                    employee_data.get("maintien_regime_apprenti", False)
                ),
            },
        }
        chemin_contrat = temp_dir / "contrat.json"
        chemin_contrat.write_text(json.dumps(contrat), encoding="utf-8")

        # Entreprise : wrapper si nécessaire
        entreprise_wrapper = (
            company_data
            if "entreprise" in company_data
            else {"entreprise": company_data}
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
            baremes_override=baremes if baremes else None,
        )
        return ctx
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


class ContextePaie:
    def __init__(
        self,
        chemin_contrat: str,
        chemin_entreprise: str,
        chemin_cumuls: str,
        chemin_data_dir: str = "data",
        baremes_override: Optional[Dict[str, Any]] = None,
        supabase_client: Optional[Client] = None,
    ):
        """
        Initialise le contexte en chargeant les données statiques (contrat, entreprise)
        puis en les surchargeant avec les barèmes dynamiques de Supabase.
        Si baremes_override est fourni, aucun accès Supabase (chemin test).
        """
        # ✅ CORRECTION: Tous les 'print' sont redirigés vers sys.stderr
        log_payroll_debug(logger, 'INFO: Initialisation du contexte de paie (Mode Supabase)...')

        log_payroll_debug(logger, '\n--- 🔍 DEBUG CONTEXTE: Chargement des fichiers initiaux ---')
        log_payroll_debug(logger, f'  -> Chemin contrat: {chemin_contrat}')
        Path(chemin_data_dir)

        # --- ÉTAPE 1 : Chargement des fichiers locaux (Contrat, Cumuls, Fichier Entreprise) ---
        entreprise_data = self._load_json(chemin_entreprise)
        self.entreprise = (entreprise_data or {}).get("entreprise", {})

        contrat_brut = self._load_json(chemin_contrat)
        if contrat_brut is None:
            logger.warning("ERREUR: Le fichier contrat.json est vide ou contient 'null'. Vérifiez les données employé en base.")
            raise ValueError(
                "Le fichier contrat.json est vide ou contient 'null'. "
                "Vérifiez que les données de l'employé (employees) sont complètes en production."
            )
        self.contrat = contrat_brut

        cumuls_data = self._load_json(chemin_cumuls)
        # S'assurer que cumuls est toujours un dictionnaire, même vide
        self.cumuls = cumuls_data if cumuls_data is not None else {}

        self.exit_indemnities: dict | None = None
        self.block_iccp_cdd: bool = False

        # DEBUG SPÉCIFIQUE PRÉVOYANCE
        prevoyance_data = self.contrat.get("specificites_paie", {}).get(
            "prevoyance", "NON TROUVÉE"
        )
        log_payroll_debug(logger, f"  -> Données 'prevoyance' lues du contrat: {json.dumps(prevoyance_data)}")
        log_payroll_debug(logger, '--- FIN DEBUG CONTEXTE ---\n')

        self.alertes_baremes: List[Dict[str, Any]] = []
        # Période du bulletin (année). Posée par les run_* après construction.
        # Sert d'aiguillage Fillon (< 2026) / RGDU (>= 2026) sans threader les signatures.
        self.year: Optional[int] = None

        if baremes_override is not None:
            self.baremes = baremes_override
            self.alertes_baremes.extend(controler_integrite_baremes(self.baremes))
            log_payroll_debug(logger, 'INFO: Contexte chargé avec barèmes injectés (mode test).')
            return

        # --- ÉTAPE 2 : Connexion à Supabase ---
        try:
            if supabase_client is not None:
                supabase = supabase_client
            else:
                supabase_url = os.environ["SUPABASE_URL"]
                supabase_key = os.environ[
                    "SUPABASE_SERVICE_KEY"
                ]  # Doit être la clé de service
                if not supabase_url or not supabase_key:
                    raise KeyError
                supabase = create_client(supabase_url, supabase_key)
        except KeyError:
            logger.warning('ERREUR: Variables SUPABASE_URL ou SUPABASE_SERVICE_KEY manquantes.')
            raise RuntimeError("Variables d'environnement Supabase non configurées.")
        except Exception as e:
            logger.warning(f"ERREUR: Échec de l'initialisation du client Supabase: {e}")
            raise

        log_payroll_debug(logger, 'INFO: Connexion Supabase établie. Chargement des barèmes...')

        # --- ÉTAPE 3 : Chargement des barèmes depuis Supabase ---
        try:
            db_baremes = charger_db_baremes(supabase)
        except Exception as e:
            logger.warning(f"ERREUR CRITIQUE: Impossible de lire 'payroll_config' depuis Supabase. {e}")
            raise

        # --- ÉTAPE 3b : Conventions collectives ---
        conventions_collectives = charger_conventions_collectives(supabase)

        # --- ÉTAPE 4 : Assignation à self.baremes ---
        self.baremes = assembler_baremes(db_baremes, conventions_collectives)
        self.alertes_baremes.extend(controler_integrite_baremes(self.baremes))

        if not self.baremes["heures_supp"]:
            logger.warning("WARN: 'heures_supp' absent de payroll_config. Exécutez le seed ou la migration pour insérer les règles heures supplémentaires.")
        if not self.baremes["primes"]:
            logger.warning("WARN: 'primes' absent de payroll_config. Exécutez le seed ou la migration pour insérer le catalogue des primes.")
        if not self.baremes["conventions_collectives"]:
            logger.warning('WARN: Aucune règle dans convention_collective_rules. Exécutez la migration 66 pour insérer les règles par IDCC.')

        # --- ÉTAPE 5 : Surcharge des Avantages en Nature ---
        avantages_db = db_baremes.get("avantages_en_nature")
        if avantages_db:
            paie_params = self.entreprise.setdefault("parametres_paie", {})
            avantages_local = paie_params.setdefault("avantages_en_nature", {})

            avantages_surcharges = {
                "repas_valeur_forfaitaire": avantages_db.get("repas"),
                "titre_restaurant_exoneration_max_patronale": avantages_db.get("titre"),
                "logement_bareme_forfaitaire": [
                    {
                        "remuneration_max": row.get("remuneration_max_eur"),
                        "valeur_1_piece": row.get("valeur_1_piece_eur"),
                        "valeur_par_piece": row.get("valeur_par_piece_suppl_eur"),
                    }
                    for row in avantages_db.get("logement", [])
                ],
            }

            avantages_local.update(avantages_surcharges)
            # ✅ CORRECTION: Redirigé vers sys.stderr
            log_payroll_debug(logger, "INFO: Surcharge des 'avantages_en_nature' depuis Supabase effectuée.")
        else:
            # ✅ CORRECTION: Redirigé vers sys.stderr
            logger.warning("WARN: 'avantages_en_nature' non trouvés dans Supabase, utilisation des valeurs du fichier entreprise.json local.")

        # ✅ CORRECTION: Redirigé vers sys.stderr
        logger.info('INFO: Contexte chargé avec succès (Mode Supabase).')

    def _load_json(self, file_path: Path | str) -> Dict[str, Any] | None:
        """Fonction utilitaire pour charger un fichier JSON en gérant les erreurs."""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.warning(f"AVERTISSEMENT: Le fichier JSON '{file_path}' est introuvable. Retour de None.")
                return None
            with open(file_path_obj, "r", encoding="utf-8") as f:
                content = json.load(f)
                # Si le fichier est vide ou contient null, retourner None
                if content is None:
                    return None
                return content
        except FileNotFoundError:
            # ✅ CORRECTION: Redirigé vers sys.stderr
            logger.warning(f"AVERTISSEMENT: Le fichier JSON '{file_path}' est introuvable. Retour de None.")
            return None
        except json.JSONDecodeError as e:
            # ✅ CORRECTION: Redirigé vers sys.stderr
            logger.warning(f"ERREUR: Le fichier JSON '{file_path}' est mal formaté. Détails: {e}")
            raise

    # --- Propriétés d'accès rapide (Données "statiques") ---

    @property
    def effectif(self) -> int:
        """Retourne l'effectif de l'entreprise."""
        return self.entreprise.get("parametres_paie", {}).get("effectif", 0)

    @property
    def statut_salarie(self) -> str:
        """Retourne le statut du salarié ('Cadre' ou 'Non-Cadre')."""
        return self.contrat.get("contrat", {}).get("statut", "Non-Cadre")

    @property
    def salaire_base_mensuel(self) -> float:
        """Retourne le salaire de base brut mensuel."""
        return (
            self.contrat.get("remuneration", {})
            .get("salaire_de_base", {})
            .get("valeur", 0.0)
        )

    @property
    def duree_hebdo_contrat(self) -> float:
        """Retourne la durée hebdomadaire de travail du contrat."""
        return (
            self.contrat.get("contrat", {})
            .get("temps_travail", {})
            .get("duree_hebdomadaire", 35)
        )

    @property
    def is_alsace_moselle(self) -> bool:
        """Indique si le salarié dépend du régime Alsace-Moselle."""
        return self.contrat.get("specificites_paie", {}).get("is_alsace_moselle", False)

    @property
    def is_forfait_jour(self) -> bool:
        """
        Indique si le salarié est en forfait jour.
        La détection se fait via le statut qui doit contenir "forfait jour" (insensible à la casse).
        """
        statut = self.statut_salarie
        if not statut:
            return False
        return "forfait jour" in statut.lower()

    # --- Type de contrat / alternance ---

    @property
    def type_contrat(self) -> str:
        """Type de contrat du salarié (ex. 'Apprentissage', 'CDI')."""
        return self.contrat.get("contrat", {}).get("type_contrat") or ""

    @property
    def is_apprenti(self) -> bool:
        """Vrai si le contrat est un contrat d'apprentissage."""
        return "apprentissage" in self.type_contrat.lower()

    @property
    def is_professionnalisation(self) -> bool:
        """Vrai si le contrat est un contrat de professionnalisation."""
        return "professionnalisation" in self.type_contrat.lower()

    @property
    def is_alternant(self) -> bool:
        """Vrai pour tout contrat en alternance (apprentissage ou pro)."""
        return self.is_apprenti or self.is_professionnalisation

    @property
    def is_stagiaire(self) -> bool:
        """Vrai si le contrat est une convention de stage."""
        return "stage" in self.type_contrat.lower()

    @property
    def is_cdd(self) -> bool:
        """Vrai si le contrat est un CDD."""
        tc = self.type_contrat.lower()
        return "cdd" in tc and "cdi" not in tc

    @property
    def is_interim(self) -> bool:
        """Vrai pour un contrat de travail temporaire (intérim / mission).

        Détection : type_contrat (intérim / mission) ou flag explicite
        specificites_paie.is_interim.
        """
        spec = self.contrat.get("specificites_paie", {}) or {}
        if spec.get("is_interim"):
            return True
        tc = self.type_contrat.lower()
        return "intérim" in tc or "interim" in tc or "mission" in tc or "ctt" in tc

    @property
    def is_mandataire(self) -> bool:
        """Vrai pour un mandataire social assimilé salarié.

        Détection : flag specificites_paie.is_mandataire ou type_contrat
        contenant 'mandataire' / 'mandat social'.
        """
        spec = self.contrat.get("specificites_paie", {}) or {}
        if spec.get("is_mandataire") or spec.get("is_mandataire_social"):
            return True
        tc = self.type_contrat.lower()
        return "mandataire" in tc or "mandat social" in tc

    @property
    def is_personnel_rd_eligible_jei(self) -> bool:
        """Vrai si le salarié est marqué éligible au dispositif JEI (personnel R&D)."""
        spec = self.contrat.get("specificites_paie", {}) or {}
        return bool(
            spec.get("personnel_rd_eligible_jei")
            or spec.get("mandataire_rd")
        )

    def jei_entreprise_active(self, year: int, month: int) -> bool:
        """Vrai si l'entreprise bénéficie du statut JEI pour la période de paie."""
        jei = self.entreprise.get("parametres_paie", {}).get("jei", {}) or {}
        if not jei.get("enabled"):
            return False
        date_str = jei.get("date_creation_etablissement")
        if not date_str:
            return False
        try:
            creation = date.fromisoformat(str(date_str)[:10])
        except ValueError:
            return False

        duree = int(
            (self.baremes.get("jei", {}) or {}).get("duree_annees", 7) or 7
        )
        last_eligible = date(creation.year + duree, 12, 31)
        _, num_days = calendar.monthrange(year, month)
        period_end = date(year, month, num_days)
        if period_end < creation:
            return False
        return period_end <= last_eligible

    @property
    def date_entree(self) -> str:
        return self.contrat.get("contrat", {}).get("date_entree") or ""

    @property
    def date_fin_contrat(self) -> str:
        """Date de fin prévue du contrat (CDD, stage, etc.)."""
        contrat = self.contrat.get("contrat", {}) or {}
        return contrat.get("date_fin_contrat") or contrat.get("date_sortie") or ""

    def est_dernier_mois_cdd(
        self, date_debut_periode: date, date_fin_periode: date
    ) -> bool:
        """Vrai si la période de paie couvre le dernier mois du CDD."""
        if not self.is_cdd:
            return False
        fin = self.date_fin_contrat
        if not fin:
            return False
        try:
            date_fin = date.fromisoformat(str(fin)[:10])
        except ValueError:
            return False
        return date_debut_periode <= date_fin <= date_fin_periode

    def est_dernier_mois_mission(
        self, date_debut_periode: date, date_fin_periode: date
    ) -> bool:
        """Vrai si la période couvre le dernier mois d'une mission d'intérim."""
        if not self.is_interim:
            return False
        fin = self.date_fin_contrat
        if not fin:
            return False
        try:
            date_fin = date.fromisoformat(str(fin)[:10])
        except ValueError:
            return False
        return date_debut_periode <= date_fin <= date_fin_periode

    @property
    def date_conclusion_contrat(self) -> str:
        """Date de signature/conclusion du contrat (peut différer du début)."""
        return self.contrat.get("contrat", {}).get("date_conclusion_contrat") or ""

    @property
    def date_debut_execution(self) -> str:
        """1er jour d'exécution du contrat (fait générateur du régime apprenti).

        Fallback sur la date d'entrée si non renseignée.
        """
        contrat = self.contrat.get("contrat", {})
        return (
            contrat.get("date_debut_execution")
            or contrat.get("date_entree")
            or ""
        )

    @property
    def date_naissance(self) -> str:
        """Date de naissance du salarié (utile pour les exonérations par âge)."""
        return self.contrat.get("salarie", {}).get("date_naissance") or ""

    # --- SMIC (deux notions distinctes, voir plan : anti-régression) ---

    @property
    def smic_horaire(self) -> float:
        """SMIC horaire brut (cas général) issu des barèmes dynamiques."""
        return self.baremes.get("smic", {}).get("cas_general", 0.0) or 0.0

    @property
    def smic_mensuel(self) -> float:
        """SMIC mensuel TEMPS PLEIN 35h, NON proratisé.

        Sert aux seuils légaux existants (maladie 2,5×, allocations familiales
        3,5×). Ne PAS proratiser ici : cela modifierait les bulletins des
        temps partiels.
        """
        return self.smic_horaire * lc.DUREE_LEGALE_HEBDO * 52 / 12

    def smic_mensuel_proratise(self, proratiser: bool = True) -> float:
        """SMIC mensuel proratisé selon la durée contractuelle.

        Réservé au plafond d'exonération apprenti (suit le temps partiel).
        """
        base = self.smic_mensuel
        duree = self.duree_hebdo_contrat
        if proratiser and duree and duree < lc.DUREE_LEGALE_HEBDO:
            return base * (duree / lc.DUREE_LEGALE_HEBDO)
        return base

    # --- Propriétés d'accès rapide (Données "variables" du mois) ---

    @property
    def saisie_du_mois(self) -> dict:
        """Retourne le dictionnaire des variables mensuelles."""
        return self.contrat.get("saisie_du_mois", {})

    @property
    def heures_sup_du_mois(self) -> float:
        """Retourne les heures supplémentaires conjoncturelles du mois."""
        return self.saisie_du_mois.get("heures_supplementaires_conjoncturelles", 0.0)

    @property
    def heures_absence_du_mois(self) -> float:
        """Retourne les heures d'absence non maintenues du mois."""
        return self.saisie_du_mois.get("heures_absence_non_maintenues", 0.0)

    @property
    def primes_du_mois(self) -> dict:
        """Retourne les primes exceptionnelles du mois."""
        return self.saisie_du_mois.get("primes_saisies", {})

    @property
    def cumuls_annee_precedente(self) -> dict:
        """Retourne le dictionnaire des cumuls arrêtés à la fin du mois précédent."""
        return self.cumuls.get("cumuls", {})

    # --- Fonctions utilitaires ---

    def get_cotisation_by_id(self, coti_id: str) -> Dict[str, Any] | None:
        """Récupère une ligne de cotisation par son ID depuis self.baremes."""

        cotisations_data = self.baremes.get("cotisations", {})

        root_key = next(
            (k for k, v in cotisations_data.items() if isinstance(v, list)), None
        )

        cotisations_list = []
        if not root_key:
            if isinstance(cotisations_data, list):
                cotisations_list = cotisations_data
            else:
                # ✅ CORRECTION: Redirigé vers sys.stderr
                logger.warning("WARN: Structure 'cotisations' non reconnue dans self.baremes pour get_cotisation_by_id.")
                return None
        else:
            cotisations_list = cotisations_data.get(root_key, [])

        for coti in cotisations_list:
            if coti.get("id") == coti_id:
                return coti
        return None

    def get_bareme_value(
        self,
        config_key: str,
        *chemin: str,
        critique: bool = False,
    ) -> Any:
        """Accès sécurisé aux barèmes scrapés (None + alerte si absent)."""
        return baremes_lookup(
            self.baremes,
            config_key,
            *chemin,
            alertes=self.alertes_baremes,
            critique=critique,
        )
