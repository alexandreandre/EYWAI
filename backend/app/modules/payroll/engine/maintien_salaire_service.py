"""
Moteur de calcul du maintien de salaire (service pur, sans FastAPI ni Supabase).

Appelé depuis le générateur de bulletins avec données déjà chargées (Ticket 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.modules.payroll.domain.baremes_maintien import (
    Bareme,
    bareme_des_reglages,
    mois_complets,
)
from app.modules.payroll.domain.ijss_deduites import (
    CLE_IJSS_DEDUITES,
    CLE_SOURCE,
    SOURCE_ESTIMEES,
    SOURCE_VALIDEES,
    alerte_ijss_au_salarie,
    est_alerte_ijss_au_salarie,
)
from app.modules.payroll.domain.paliers_affiches import (
    alertes_du_bareme,
    detail_du_bareme,
    motif_carence_du_bareme,
    motif_sans_droit,
)

from .contexte import ContextePaie
from . import legal_constants as lc
from .paliers_convention import PlanConventionnel, arrets_pour_le_plan, plan_conventionnel
from .prolongation_arret import chainer_arret

#: Réglage société (23/10/2026) : sans subrogation, déduire du maintien les
#: IJSS des jours maintenus. Absent du dict : le calcul d'avant ce réglage ;
#: `get_maintenance_settings` pose toujours la clé.
CLE_DEDUIRE_IJSS = "deduire_ijss_sans_subrogation"

#: Relevé du mois pour plusieurs arrêts : (montant validé, IJSS estimées, jours indemnisés).
ReleveIjss = Tuple[float, float, int]


def deduire_ijss_sans_subrogation(settings: Dict[str, Any]) -> bool:
    """La société déduit-elle du maintien les IJSS des jours maintenus, sans subrogation ?"""
    return bool(settings.get(CLE_DEDUIRE_IJSS, False))

# --- Dates & utilitaires ---


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value[:10])
    return None


def _date_anciennete(contexte: ContextePaie) -> Optional[date]:
    """Date d'ancienneté du salarié pour le maintien de salaire.

    La condition d'ancienneté et la durée des tranches (L1226-1, D1226-1 et
    D1226-2) s'apprécient sur l'ancienneté dans l'entreprise, qu'une
    convention ou un contrat peut reprendre. Même lecture que les fériés : la
    plus favorable de l'entrée au contrat et de la date d'ancienneté de la
    fiche (reprise, à défaut celle de la DSN) — une date postérieure à
    l'entrée ne retire jamais d'ancienneté. Jamais `prior_service_months`, qui
    porte souvent l'ancienneté totale au lieu de la reprise.
    """
    from app.shared.seniority_reference import resolve_date_anciennete_from_contrat

    contrat = getattr(contexte, "contrat", None) or {}
    bloc = contrat.get("contrat") if isinstance(contrat, dict) else None
    entree = bloc.get("date_entree") if isinstance(bloc, dict) else None
    ancres = [
        _parse_date(entree),
        _parse_date(resolve_date_anciennete_from_contrat(contrat)),
    ]
    ancres = [d for d in ancres if d]
    return min(ancres) if ancres else None


def _mois_anciennete(date_entree: date, ref: date) -> int:
    """Nombre de mois entamés entre date_entree et ref (approximation standard RH)."""
    if ref < date_entree:
        return 0
    return (ref.year - date_entree.year) * 12 + (ref.month - date_entree.month)


def _intersection_dates(
    a_debut: date, a_fin: date, b_debut: date, b_fin: date
) -> tuple[Optional[date], Optional[date]]:
    d = max(a_debut, b_debut)
    f = min(a_fin, b_fin)
    if d > f:
        return None, None
    return d, f


def _compter_jours_calendaires(d1: date, d2: date) -> int:
    """Inclusive calendar days between d1 and d2."""
    if d2 < d1:
        return 0
    return (d2 - d1).days + 1


def _extraire_pss_annuel(baremes_pss: Any) -> Optional[float]:
    """
    Extrait le plafond SS annuel depuis baremes['pss'].
    Retourne None si absent (pas de repli silencieux).
    """
    if baremes_pss is None:
        return None
    if isinstance(baremes_pss, (int, float)):
        return float(baremes_pss)
    if not isinstance(baremes_pss, dict):
        return None
    for key in ("annuel", "annuelle", "valeur_annuelle", "plafond_annuel"):
        v = baremes_pss.get(key)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    mensuel = baremes_pss.get("mensuel")
    if isinstance(mensuel, (int, float)) and mensuel > 0:
        return float(mensuel) * 12.0
    return None


def plafond_ij_pour(
    arret_type: str,
    jour_arret_1based: int,
    ij_plafonds: Optional[Dict[str, Any]],
) -> Optional[float]:
    """Plafond journalier IJSS (€/jour) selon le type d'arrêt."""
    if not ij_plafonds or not isinstance(ij_plafonds, dict):
        return None
    t = (arret_type or "maladie_simple").strip()
    types_at_mp = frozenset(
        {
            "accident_travail",
            "maladie_professionnelle",
            "accident_trajet",
            "rechute_at",
        }
    )
    if t in types_at_mp:
        key = "at_mp_majoree" if jour_arret_1based >= 29 else "at_mp"
    elif t in ("maternite", "paternite", "adoption", "maternite_paternite", "paternite_accueil_enfant"):
        key = "maternite_paternite"
    else:
        key = "maladie"
    val = ij_plafonds.get(key)
    if isinstance(val, (int, float)) and val > 0:
        return float(val)
    return None


def plafonds_ij_au(
    ij_plafonds: Optional[Dict[str, Any]], jour: Optional[date]
) -> Optional[Dict[str, Any]]:
    """Les plafonds d'IJ en vigueur pour un accident ou un arrêt du `jour`.

    Le barème porte ses paliers (`historique` : date d'effet et montants) :
    le dernier qui a pris effet au plus tard ce jour s'applique, le premier
    pour un jour d'avant. Le décret n° 2026-909 abaisse le plafond des IJ
    d'accident du travail pour les arrêts survenus à compter du 01/11/2026 :
    un arrêt d'octobre garde l'ancien, même après la mise à jour du barème.
    Sans paliers, le barème se lit tel quel.
    """
    if not isinstance(ij_plafonds, dict):
        return ij_plafonds
    paliers = []
    for palier in ij_plafonds.get("historique") or []:
        debut = _parse_date((palier or {}).get("date_debut")) if isinstance(palier, dict) else None
        if debut is not None:
            paliers.append((debut, palier))
    if not paliers or jour is None:
        return ij_plafonds
    paliers.sort(key=lambda p: p[0])
    applicable = paliers[0][1]
    for debut, palier in paliers:
        if debut <= jour:
            applicable = palier
    return {**ij_plafonds, **{k: v for k, v in applicable.items() if k != "date_debut"}}


def date_de_reference_des_plafonds(
    arret: Dict[str, Any], est_at_mp: bool, debut_arret: date
) -> date:
    """La date qui choisit le plafond : celle de l'accident quand elle est
    saisie (accident du travail, maladie professionnelle), sinon le début de
    l'arrêt, celui de l'arrêt prolongé pour une prolongation."""
    if est_at_mp:
        accident = _parse_date(arret.get("date_accident"))
        if accident is not None:
            return accident
    return _parse_date(arret.get("date_debut_chaine")) or debut_arret


# --- Bloc 1 : qualification ---


def _qualifier_arret(arret_type: str) -> Dict[str, Any]:
    t = (arret_type or "maladie_simple").strip()
    types_3j_ss = frozenset(
        {"maladie_simple", "ald", "mi_temps_therapeutique", "arret_exceptionnel"}
    )
    types_at_mp = frozenset(
        {
            "accident_travail",
            "maladie_professionnelle",
            "accident_trajet",
            "rechute_at",
        }
    )
    # Congés liés à la parentalité : régime légal DISTINCT de la maladie —
    # IJSS versées dès le 1er jour (pas de carence SS de 3 jours), et le maintien
    # employeur conventionnel est à 100 % SANS barème dégressif par ancienneté
    # (le barème D1226-1, propre à la maladie, ne s'applique PAS). Cf. Code du
    # travail L1225-17 et s. (maternité), L1225-35 (paternité/accueil de
    # l'enfant), L1225-37 (adoption) ; CCN métallurgie IDCC 3248 art. 92
    # (maintien 100 % sous condition d'ancienneté ≥ 1 an, gérée par le seuil
    # `min_seniority_months` des settings comme pour la maladie).
    types_maternite = frozenset(
        {
            "maternite",
            "paternite",
            "adoption",
            "maternite_paternite",
            "paternite_accueil_enfant",
            "conge_naissance_supplementaire",
        }
    )

    est_maternite = t in types_maternite

    if t in types_at_mp:
        carence_ss_jours = 0
        taux_ijss_base = lc.TAUX_IJSS_AT_MP_J1_28
    elif est_maternite:
        carence_ss_jours = 0  # maternité/paternité/adoption : IJSS dès le 1er jour
        taux_ijss_base = lc.TAUX_IJSS_MALADIE
    elif t in types_3j_ss:
        carence_ss_jours = 3
        taux_ijss_base = lc.TAUX_IJSS_MALADIE
    else:
        carence_ss_jours = 3
        taux_ijss_base = lc.TAUX_IJSS_MALADIE

    est_ald = t == "ald"

    return {
        "carence_ss_jours": carence_ss_jours,
        "taux_ijss_base": taux_ijss_base,
        "est_at_mp": t in types_at_mp,
        "est_ald": est_ald,
        "est_maternite": est_maternite,
    }


# --- Bloc 2 : carence ---


def _carence_employeur_deja_prise_cette_annee(
    historique: List[Dict[str, Any]], annee: int
) -> bool:
    for h in historique or []:
        if h.get("employer_carence_applied") and h.get("annee") == annee:
            return True
    return False


def _calculer_carence(
    arret: Dict[str, Any],
    qualification: Dict[str, Any],
    settings: Dict[str, Any],
    date_debut_arret: date,
    historique_arrets_annee: List[Dict[str, Any]],
) -> Dict[str, Any]:
    arret_type = str(arret.get("arret_type") or "").strip()
    if arret_type == "ald" and bool(arret.get("est_rechute_ald")):
        return {
            "carence_ss_jours": 0,
            "carence_employeur_jours": 0,
            "motif_carence": "ALD — pas de nouvelle carence sur rechute",
            "est_continuite": True,
        }

    carence_ss = int(qualification.get("carence_ss_jours") or 0)

    date_dernier = _parse_date(arret.get("date_dernier_arret"))
    est_continuite = False
    if date_dernier and date_debut_arret > date_dernier:
        if (date_debut_arret - date_dernier).days < 48:
            est_continuite = True

    if est_continuite:
        return {
            "carence_ss_jours": 0,
            "carence_employeur_jours": 0,
            "motif_carence": "Continuité d'arrêt (< 48 h depuis le dernier arrêt) : pas de nouvelle carence.",
            "est_continuite": True,
        }

    if qualification.get("est_at_mp") or carence_ss == 0:
        motif_ss = "AT/MP/trajet/rechute : pas de carence SS."
    else:
        motif_ss = f"Carence SS légale : {carence_ss} jour(s)."

    # Le délai de carence employeur (7 j) est supprimé de plein droit en cas
    # d'accident du travail / maladie professionnelle (art. L1226-1 et D1226-3),
    # « à l'exclusion des accidents de trajet » (D1226-3) : le trajet garde la
    # carence employeur, même si la Sécurité sociale l'indemnise comme un AT.
    # Il ne s'applique pas non plus aux congés de parentalité (maternité,
    # paternité, adoption) : le maintien couvre l'intégralité du congé dès le
    # 1er jour (art. L1225-17 et s.).
    if qualification.get("est_at_mp") and arret_type != "accident_trajet":
        carence_emp = 0
        motif_emp = "AT/MP : pas de carence employeur (supprimée de plein droit)."
    elif qualification.get("est_maternite"):
        carence_emp = 0
        motif_emp = "Congé de parentalité : pas de carence employeur (maintien dès le 1er jour)."
    elif settings.get("remove_employer_waiting"):
        carence_emp = 0
        motif_emp = "Carence employeur supprimée (paramétrage entreprise)."
    elif settings.get("annual_unique_waiting") and _carence_employeur_deja_prise_cette_annee(
        historique_arrets_annee, date_debut_arret.year
    ):
        carence_emp = 0
        motif_emp = "Carence employeur annuelle unique déjà consommée sur l'année."
    else:
        carence_emp = int(settings.get("employer_waiting_days") or 7)
        motif_emp = f"Carence employeur : {carence_emp} jour(s)."

    return {
        "carence_ss_jours": carence_ss,
        "carence_employeur_jours": carence_emp,
        "motif_carence": f"{motif_ss} {motif_emp}",
        "est_continuite": False,
    }


# --- Bloc 3 : IJSS ---


def _taux_ijss_pour_jour_arret(
    arret_type: str,
    jour_arret_calendaire: int,
    nombre_enfants: int,
) -> float:
    """
    jour_arret_calendaire : jour calendaire de l'arrêt (1 = 1er jour de l'arrêt).

    - AT/MP : 60 % jusqu'au 28e jour, 80 % à partir du 29e jour d'arrêt.
    - Maladie + 3 enfants à charge : majoration de 50 % à 66,66 % uniquement
      à partir du 31e jour d'arrêt continu (art. R323-5 CSS).
    """
    t = arret_type or "maladie_simple"
    at_mp = t in {
        "accident_travail",
        "maladie_professionnelle",
        "accident_trajet",
        "rechute_at",
    }
    if at_mp:
        return (
            lc.TAUX_IJSS_AT_MP_J29
            if jour_arret_calendaire >= 29
            else lc.TAUX_IJSS_AT_MP_J1_28
        )
    if t in ("maladie_simple", "ald", "arret_exceptionnel"):
        if nombre_enfants >= 3 and jour_arret_calendaire >= 31:
            return lc.TAUX_IJSS_MALADIE_3_ENFANTS
        return lc.TAUX_IJSS_MALADIE
    if t == "mi_temps_therapeutique":
        return lc.TAUX_IJSS_MI_TEMPS
    # Maternité, paternité, adoption : indemnité à 100 % du salaire journalier
    # de base, dans la limite du plafond propre (art. R323-4 et R331-5 CSS).
    # Le taux maladie (50 %) ne s'applique pas.
    if t in {
        "maternite",
        "paternite",
        "adoption",
        "maternite_paternite",
        "paternite_accueil_enfant",
    }:
        return 1.0
    return lc.TAUX_IJSS_MALADIE


def _contexte_is_forfait_jours(contexte: ContextePaie) -> bool:
    try:
        return bool(contexte.is_forfait_jour)  # type: ignore[attr-defined]
    except Exception:
        return False


def _ijss_extras_mi_temps_forfait(
    arret: Dict[str, Any], arret_type: str, contexte: ContextePaie
) -> Dict[str, Any]:
    is_mt = arret_type == "mi_temps_therapeutique"
    salaire_m = float(contexte.salaire_base_mensuel or 0.0)
    q_mt = float(arret.get("quotite_temps_partiel") or 0.5)
    salaire_partiel = round(salaire_m * q_mt, 2) if is_mt else 0.0
    return {
        "is_mi_temps_therapeutique": is_mt,
        "salaire_partiel_maintenu": salaire_partiel if is_mt else 0.0,
        "is_forfait_jours": _contexte_is_forfait_jours(contexte),
    }


#: Arrêts depuis cette date : salaire de base des IJ maladie retenu dans la
#: limite de 1,4 Smic mensuel (CSS R323-4 ; référentiel du dépôt, R05).
DEBUT_PLAFOND_SJB_SMIC = date(2025, 4, 1)


def _salaire_journalier_de_base_maladie(
    arret: Dict[str, Any],
    salaire_mensuel: float,
    plafond_mensuel: Optional[float] = None,
) -> float:
    """Salaire journalier de base des IJ maladie : trois derniers bruts ÷ 91,25.

    Les bruts sont ceux des trois bulletins qui précèdent le mois du début de
    l'arrêt (`salaires_bruts_reference`, lus par le générateur). Un mois sans
    bulletin, ou un arrêt sans bruts fournis (aperçu, simulation), compte le
    salaire de base du contrat : c'est une estimation, que le décompte de la
    caisse remplace dans le suivi IJSS.

    `plafond_mensuel`, s'il est fourni, limite chaque paie avant la somme
    (CSS R323-4 : le revenu retenu « lors de chaque paie […] dans la limite
    d'un plafond […] calculé pour un mois ») : un mois au-dessus du plafond ne
    compense pas un mois en dessous.
    """
    bruts = list(arret.get("salaires_bruts_reference") or [])[:3]
    bruts += [None] * (3 - len(bruts))
    total = 0.0
    for brut in bruts:
        try:
            valeur = float(brut) if brut is not None else None
        except (TypeError, ValueError):
            valeur = None
        paie = valeur if valeur is not None else salaire_mensuel
        if plafond_mensuel is not None:
            paie = min(paie, plafond_mensuel)
        total += paie
    return total / lc.DIVISEUR_SJB_TROIS_MOIS if total > 0 else 0.0


def _smic_horaire_au(contexte: ContextePaie, jour: date) -> Optional[float]:
    """Smic horaire en vigueur le `jour` (barème `smic` et son historique).

    Même règle que `ContextePaie.smic_horaire`, à une autre date : le palier
    le plus récent qui précède le jour, sinon la valeur courante.
    """
    baremes = getattr(contexte, "baremes", None) or {}
    smic = baremes.get("smic") if isinstance(baremes, dict) else None
    if not isinstance(smic, dict):
        return None
    applicable: Optional[tuple[date, Any]] = None
    for palier in smic.get("historique") or []:
        debut = _parse_date((palier or {}).get("date_debut"))
        if debut and debut <= jour and (applicable is None or debut > applicable[0]):
            applicable = (debut, palier.get("cas_general"))
    valeur = applicable[1] if applicable and applicable[1] else smic.get("cas_general")
    try:
        return float(valeur) if valeur else None
    except (TypeError, ValueError):
        return None


def _plafond_mensuel_sjb_maladie(
    contexte: ContextePaie, debut_arret: date
) -> Optional[float]:
    """Plafond de chaque paie retenue pour les IJ maladie, ou None.

    1,4 Smic mensuel, au Smic du dernier jour du mois civil qui précède le
    début de l'arrêt, pour les arrêts depuis le 01/04/2025. None avant cette
    date ou sans barème Smic : l'ancien plafond s'applique.
    """
    if debut_arret < DEBUT_PLAFOND_SJB_SMIC:
        return None
    smic_horaire = _smic_horaire_au(contexte, debut_arret.replace(day=1) - timedelta(days=1))
    if not smic_horaire:
        return None
    smic_mensuel = smic_horaire * lc.DUREE_LEGALE_HEBDO * 52 / 12
    return lc.COEFF_PLAFOND_SJB_SMIC * smic_mensuel


def _plafond_sjb_at_mp(pss_annuel: float, debut_arret: date) -> float:
    """Plafond du salaire journalier de base des IJ AT/MP (CSS R433-2).

    La fraction du plafond annuel de la Sécurité sociale en vigueur au début
    de l'arrêt : 0,834 %, puis 0,226 % pour les arrêts survenus depuis le
    01/11/2026 (décret n° 2026-909). Un arrêt commencé avant garde l'ancien
    plafond jusqu'à son terme.
    """
    taux = lc.TAUX_PLAFOND_SJB_AT_MP_PASS[0][1]
    for debut, taux_palier in lc.TAUX_PLAFOND_SJB_AT_MP_PASS:
        if debut_arret >= debut:
            taux = taux_palier
    return pss_annuel * taux


def _calculer_ijss(
    arret: Dict[str, Any],
    qualification: Dict[str, Any],
    carence: Dict[str, Any],
    contexte: ContextePaie,
    date_debut_periode: date,
    date_fin_periode: date,
    par_jour: Optional[Dict[date, float]] = None,
) -> Dict[str, Any]:
    """IJSS estimées de l'arrêt dans la période.

    `par_jour`, s'il est fourni, reçoit l'IJSS de chaque jour indemnisé : la
    déduction sans subrogation n'en retient que les jours maintenus.
    """
    arret_type = str(arret.get("arret_type") or "maladie_simple")
    nombre_enfants = int(arret.get("nombre_enfants") or 0)
    is_tp = bool(arret.get("is_temps_partiel"))
    quotite = float(arret.get("quotite_temps_partiel") or 1.0)
    if quotite <= 0:
        quotite = 1.0

    date_debut_arret = _parse_date(arret.get("date_debut"))
    date_fin_arret = _parse_date(arret.get("date_fin"))
    if not date_debut_arret or not date_fin_arret:
        out = {
            "ijss_theorique": 0.0,
            "ijss_journaliere": 0.0,
            "nb_jours_indemnises": 0,
            "taux_applique": 0.0,
            "salaire_journalier_base": 0.0,
            "base_plafonnee": 0.0,
        }
        out.update(_ijss_extras_mi_temps_forfait(arret, arret_type, contexte))
        return out

    # Prolongation : le rang des jours (seuils J29 et J31) et le plafond se lisent
    # depuis le début de l'arrêt prolongé.
    jours_deja = _jours_deja_en_arret(arret)
    debut_reference = _parse_date(arret.get("date_debut_chaine")) or date_debut_arret
    # Plafonds : à la date de l'accident quand elle est saisie, sinon au début.
    date_plafonds = date_de_reference_des_plafonds(
        arret, bool(qualification.get("est_at_mp")), date_debut_arret
    )

    salaire_mensuel = float(contexte.salaire_base_mensuel or 0.0)
    est_maladie = not qualification.get("est_at_mp") and not qualification.get(
        "est_maternite"
    )
    if est_maladie:
        salaire_journalier_base = _salaire_journalier_de_base_maladie(
            arret, salaire_mensuel
        )
    else:
        salaire_journalier_base = (
            salaire_mensuel / lc.DIVISEUR_JOURS_CALENDAIRES if salaire_mensuel else 0.0
        )

    plafond_mensuel_smic = (
        _plafond_mensuel_sjb_maladie(contexte, debut_reference) if est_maladie else None
    )
    pss_data = contexte.get_bareme_value("pss") if hasattr(contexte, "get_bareme_value") else contexte.baremes.get("pss")
    pss_annuel = _extraire_pss_annuel(pss_data)
    if plafond_mensuel_smic is not None:
        # Chaque paie retenue dans la limite de 1,4 Smic mensuel (R323-4).
        base_plafonnee = _salaire_journalier_de_base_maladie(
            arret, salaire_mensuel, plafond_mensuel_smic
        )
    elif pss_annuel is None:
        plafond_ss_journalier = 0.0
        base_plafonnee = 0.0
    elif qualification.get("est_at_mp"):
        base_plafonnee = min(
            salaire_journalier_base, _plafond_sjb_at_mp(pss_annuel, date_plafonds)
        )
    else:
        plafond_ss_journalier = pss_annuel / 365.0
        base_plafonnee = min(
            salaire_journalier_base,
            plafond_ss_journalier * lc.COEFF_PLAFOND_IJ_PSS,
        )

    ij_plafonds = plafonds_ij_au(
        (
            contexte.get_bareme_value("ij_plafonds")
            if hasattr(contexte, "get_bareme_value")
            else contexte.baremes.get("ij_plafonds")
        ),
        date_plafonds,
    )

    carence_ss = int(carence.get("carence_ss_jours") or 0)

    # V1 forfait jour : le décompte IJSS repose déjà sur des jours calendaires
    # (boucle jour par jour sur l'intervalle d'arrêt), pas sur des jours ouvrés —
    # comportement attendu aligné forfait jours.

    # Jours calendaires de l'arrêt dans la période de paie, après carence SS
    inter_d, inter_f = _intersection_dates(
        date_debut_arret, date_fin_arret, date_debut_periode, date_fin_periode
    )
    if inter_d is None or inter_f is None:
        out = {
            "ijss_theorique": 0.0,
            "ijss_journaliere": 0.0,
            "nb_jours_indemnises": 0,
            "taux_applique": 0.0,
            "salaire_journalier_base": round(salaire_journalier_base, 4),
            "base_plafonnee": round(base_plafonnee, 4),
        }
        out.update(_ijss_extras_mi_temps_forfait(arret, arret_type, contexte))
        return out

    ijss_total = 0.0
    nb_indem = 0
    somme_taux = 0.0

    d = date_debut_arret
    while d <= date_fin_arret:
        offset = (d - date_debut_arret).days
        if inter_d <= d <= inter_f:
            if offset >= carence_ss:
                # Jour calendaire de l'arrêt (1 = 1er jour) : sert aux seuils
                # AT/MP (J29) et majoration maladie 3 enfants (J31).
                jour_arret_calendaire = jours_deja + offset + 1
                taux_j = _taux_ijss_pour_jour_arret(
                    arret_type, jour_arret_calendaire, nombre_enfants
                )
                ijss_j = base_plafonnee * taux_j
                plafond_j = plafond_ij_pour(
                    arret_type, jour_arret_calendaire, ij_plafonds
                )
                if plafond_j is not None:
                    ijss_j = min(ijss_j, plafond_j)
                if is_tp:
                    ijss_j *= quotite
                if par_jour is not None:
                    par_jour[d] = ijss_j
                ijss_total += ijss_j
                nb_indem += 1
                somme_taux += taux_j
        d += timedelta(days=1)

    taux_moyen = (somme_taux / nb_indem) if nb_indem else 0.0
    ijss_journaliere = (ijss_total / nb_indem) if nb_indem else 0.0

    out = {
        "ijss_theorique": round(ijss_total, 2),
        "ijss_journaliere": round(ijss_journaliere, 4),
        "nb_jours_indemnises": nb_indem,
        "taux_applique": round(taux_moyen, 4),
        "salaire_journalier_base": round(salaire_journalier_base, 4),
        "base_plafonnee": round(base_plafonnee, 4),
    }
    out.update(_ijss_extras_mi_temps_forfait(arret, arret_type, contexte))
    return out


# --- Bloc 4 : maintien employeur ---

MOTIF_PARENTALITE_SANS_MAINTIEN = (
    "Pas de maintien de salaire pendant les congés de maternité, de paternité "
    "et d'adoption : réglage de la société."
)


def duree_maintien_par_taux(anciennete_mois: int) -> int:
    """
    Durée (en jours) de CHAQUE tranche du maintien légal (90 % puis 66,66 %)
    selon l'ancienneté, conformément au barème de l'article D1226-1 du Code du
    travail :

    - 1 à 5 ans      → 30 jours par tranche (30 j à 90 % + 30 j à 66,66 %)
    - + 10 jours par période entière de 5 ans d'ancienneté au-delà de la 1re année
    - plafonné à 90 jours par tranche (soit 180 jours au total à partir de 31 ans).

    | Ancienneté | par tranche | total |
    |-----------|-------------|-------|
    | 1-5 ans   | 30 j        | 60 j  |
    | 6-10 ans  | 40 j        | 80 j  |
    | 11-15 ans | 50 j        | 100 j |
    | 16-20 ans | 60 j        | 120 j |
    | 21-25 ans | 70 j        | 140 j |
    | 26-30 ans | 80 j        | 160 j |
    | 31 ans +  | 90 j        | 180 j |
    """
    tranches_5_ans = max(0, (anciennete_mois - 12) // 60)
    return min(90, 30 + 10 * tranches_5_ans)


def _taux_legal_pour_jour_maintien(
    jour_maintien_1based: int,
    duree_par_taux: int,
) -> float:
    """
    jour_maintien_1based : rang du jour indemnisé au titre du maintien
    (1 = premier jour maintenu, après le délai de carence employeur).

    Tranche 1 (90 %) puis tranche 2 (66,66 %), chacune d'une durée
    ``duree_par_taux`` fonction de l'ancienneté.
    """
    if jour_maintien_1based < 1:
        return 0.0
    if jour_maintien_1based <= duree_par_taux:
        return lc.TRANCHE_MAINTIEN_90
    if jour_maintien_1based <= 2 * duree_par_taux:
        return lc.TRANCHE_MAINTIEN_66
    return 0.0


def _taux_conventionnel(settings: Dict[str, Any], est_at_mp: bool) -> Optional[float]:
    """
    Taux de maintien conventionnel/entreprise applicable (None = règle légale seule).

    Priorité : taux explicite > 100 % global > 100 % AT/MP différencié.
    """
    explicite = settings.get("taux_maintien_conventionnel")
    if isinstance(explicite, (int, float)):
        return float(explicite)
    if settings.get("maintain_100_percent"):
        return 1.0
    if settings.get("differentiated_at_illness") and est_at_mp:
        return 1.0
    # maintain_by_category : V1 ignoré
    return None


def _min_seniority_months_for_arret(
    settings: Dict[str, Any], est_at_mp: bool
) -> int:
    """Seuil d'ancienneté pour le maintien (AM vs AT/MP)."""
    if est_at_mp:
        return int(
            settings.get("min_seniority_months_at_mp")
            or settings.get("min_seniority_months")
            or 0
        )
    return int(settings.get("min_seniority_months") or 0)


def _est_maintien_eligible_seniority(
    settings: Dict[str, Any],
    qualification: Dict[str, Any],
    anciennete_mois: int,
) -> bool:
    """True si l'ancienneté permet le maintien employeur (hors chevauchement période)."""
    if bool(settings.get("no_seniority_condition")):
        return True
    est_at_mp = bool(qualification.get("est_at_mp"))
    min_senior = _min_seniority_months_for_arret(settings, est_at_mp)
    return anciennete_mois >= min_senior


def _ijss_des_jours_maintenus(
    jours_maintenus: set,
    ijss: Dict[str, Any],
    ijss_par_jour: Dict[date, float],
    releve_du_mois: Optional[ReleveIjss],
) -> tuple[float, str]:
    """IJSS que la CPAM verse pour les jours que l'employeur maintient.

    Estimées : la somme des IJSS de ces jours. Montant validé au suivi IJSS :
    sa part pour ces jours, au prorata des IJSS estimées de l'arrêt (du mois
    pour plusieurs arrêts), ou des jours indemnisés si rien n'a pu être estimé.
    """
    jours = [d for d in ijss_par_jour if d in jours_maintenus]
    estimees = sum(ijss_par_jour[d] for d in jours)
    if releve_du_mois is None and not ijss.get("ijss_brut_override"):
        return estimees, SOURCE_ESTIMEES
    if releve_du_mois is not None:
        valide, estime_total, nb_total = releve_du_mois
    else:
        valide = float(ijss.get("ijss_theorique") or 0.0)
        estime_total = sum(ijss_par_jour.values())
        nb_total = len(ijss_par_jour)
    if estime_total > 0:
        part = estimees / estime_total
    elif nb_total > 0:
        part = len(jours) / nb_total
    else:
        part = 0.0
    return valide * part, SOURCE_VALIDEES


def _verse_sans_subrogation(
    maintien_cible: float,
    settings: Dict[str, Any],
    jours_maintenus: set,
    ijss: Dict[str, Any],
    ijss_par_jour: Optional[Dict[date, float]],
    releve_du_mois: Optional[ReleveIjss],
) -> tuple[float, Dict[str, Any]]:
    """Le maintien versé sans subrogation, et la déduction quand elle joue.

    Réglage éteint : le garanti en entier. Allumé : le garanti moins les IJSS
    des jours maintenus et indemnisés, plancher à 0 (D1226-5). Les IJSS des
    jours que l'employeur ne maintient pas restent au salarié.
    """
    if ijss_par_jour is None or not deduire_ijss_sans_subrogation(settings):
        return maintien_cible, {}
    retenues, source = _ijss_des_jours_maintenus(
        jours_maintenus, ijss, ijss_par_jour, releve_du_mois
    )
    retenues = round(retenues, 2)
    if retenues <= 0 or maintien_cible <= 0:
        return maintien_cible, {}
    verse = max(0.0, maintien_cible - retenues)
    deduites = round(round(maintien_cible, 2) - round(verse, 2), 2)
    if deduites <= 0:
        return maintien_cible, {}
    return verse, {CLE_IJSS_DEDUITES: deduites, CLE_SOURCE: source}


def _verse_avec_subrogation(
    maintien_cible: float,
    arret: Dict[str, Any],
    jours_maintenus: set,
    ijss: Dict[str, Any],
    ijss_par_jour: Optional[Dict[date, float]],
    releve_du_mois: Optional[ReleveIjss],
) -> float:
    """Le maintien versé avec subrogation : le garanti moins les IJSS des jours maintenus.

    L'employeur reçoit de la CPAM les IJSS de tout l'arrêt et les reverse au
    salarié (« IJSS subrogées » au bulletin). Sur les jours qu'il maintient,
    elles font partie du garanti : il n'en verse que le complément, plancher à 0
    (D1226-5). Celles des jours qu'il ne maintient pas (carence employeur, J4 à
    J7 en maintien légal) ne se déduisent jamais : le salarié les reçoit en plus
    du garanti. Même règle, et même prorata d'un montant validé, que sans
    subrogation.

    Reconstitution d'un bulletin Cegid (saisie « IJSS override » : maintien en
    jours ouvrés, IJSS hors bulletin) : le montant saisi est la retenue relevée
    sur ce bulletin (absence à 100 % moins maintien), pas les IJSS de l'arrêt.
    Il se déduit en entier, comme avant.
    """
    ijss_arret = float(ijss.get("ijss_theorique") or 0.0)
    reconstitution = bool(arret.get("maintien_base_ouvree")) and bool(
        ijss.get("ijss_brut_override")
    )
    if ijss_par_jour is None or reconstitution:
        return maintien_cible - ijss_arret
    retenues, _source = _ijss_des_jours_maintenus(
        jours_maintenus, ijss, ijss_par_jour, releve_du_mois
    )
    return max(0.0, maintien_cible - round(retenues, 2))


def _calculer_maintien_employeur(
    arret: Dict[str, Any],
    qualification: Dict[str, Any],
    carence: Dict[str, Any],
    ijss: Dict[str, Any],
    contexte: ContextePaie,
    settings: Dict[str, Any],
    date_debut_arret: date,
    anciennete_mois: int,
    date_debut_periode: date,
    date_fin_periode: date,
    jours_carence_payes: frozenset[date] = frozenset(),
    ijss_par_jour: Optional[Dict[date, float]] = None,
    releve_du_mois: Optional[ReleveIjss] = None,
) -> Dict[str, Any]:
    motif_non_maintien: Optional[str] = None
    conflit_convention = False

    est_at_mp = bool(qualification.get("est_at_mp"))
    min_senior = _min_seniority_months_for_arret(settings, est_at_mp)
    no_seniority = bool(settings.get("no_seniority_condition"))
    if not no_seniority and anciennete_mois < min_senior:
        return {
            "maintien_applicable": False,
            "taux_maintien": 0.0,
            "maintien_cible": 0.0,
            "maintien_verse": 0.0,
            "nb_jours_maintien": 0,
            "complement_employeur": 0.0,
            "conflit_convention": False,
            "motif_non_maintien": "Ancienneté inférieure au minimum requis pour le maintien.",
            "proratisation_temps_partiel": False,
        }

    date_fin_arret = _parse_date(arret.get("date_fin")) or date_debut_arret
    inter_d, inter_f = _intersection_dates(
        date_debut_arret, date_fin_arret, date_debut_periode, date_fin_periode
    )
    if inter_d is None or inter_f is None:
        return {
            "maintien_applicable": True,
            "taux_maintien": 0.0,
            "maintien_cible": 0.0,
            "maintien_verse": 0.0,
            "nb_jours_maintien": 0,
            "complement_employeur": 0.0,
            "conflit_convention": False,
            "motif_non_maintien": "Aucun chevauchement arrêt / période de paie.",
            "proratisation_temps_partiel": False,
        }

    salaire_mensuel = float(contexte.salaire_base_mensuel or 0.0)
    # Mode « jours ouvrés » (opt-in par arrêt) : le maintien est calculé sur le
    # salaire journalier RÉEL des jours ouvrés (taux horaire de base × 7 h légales),
    # décompté sur les seuls jours ouvrés (samedi/dimanche exclus), conformément à
    # la pratique Cegid (le maintien couvre l'absence déduite jour ouvré par jour
    # ouvré). Par défaut (flag absent) : ancien modèle salaire mensuel / 30,42 j
    # calendaires, préservé pour la compatibilité (tests + autres clients).
    maintien_base_ouvree = bool(arret.get("maintien_base_ouvree"))
    if maintien_base_ouvree:
        duree_hebdo = float(contexte.duree_hebdo_contrat or 0.0)
        try:
            from .calcul_brut import _get_salaire_horaire_base

            taux_horaire_base = _get_salaire_horaire_base(contexte, duree_hebdo)
        except Exception:
            taux_horaire_base = (
                salaire_mensuel / lc.DIVISEUR_JOURS_CALENDAIRES
                if salaire_mensuel
                else 0.0
            )
        # Une journée maintenue restitue ce que l'absence a retiré : la base
        # légale ET la quote-part d'heures sup structurelles de la journée. Sans
        # elle, un salarié à 39 h perd ses heures structurelles sur un jour
        # pourtant maintenu. salarié 140 (Colorplast, mars 2026) : le cabinet
        # maintient 103,59 € par jour, soit 7 h à 12,9492 (90,64) plus 0,80 h à
        # 16,1865 (12,95) — la valeur exacte d'une de ses journées de congé payé.
        brut_journalier = taux_horaire_base * (lc.DUREE_LEGALE_HEBDO / 5.0)
        brut_journalier += _quote_part_hs_structurelles_journaliere(
            contexte, duree_hebdo, taux_horaire_base
        )
    else:
        brut_journalier = (
            salaire_mensuel / lc.DIVISEUR_JOURS_CALENDAIRES if salaire_mensuel else 0.0
        )

    apply_legal = bool(settings.get("apply_legal_maintenance"))

    # Durée légale du maintien selon l'ancienneté (barème D1226-1).
    duree_par_taux = duree_maintien_par_taux(anciennete_mois) if apply_legal else 0
    duree_legale_totale = 2 * duree_par_taux

    # Délai de carence employeur : les premiers jours de l'arrêt ne sont pas
    # maintenus (sauf AT/MP ou suppression conventionnelle → carence = 0).
    # Prolongation : le rang se compte depuis le début de l'arrêt prolongé, et
    # sa carence (celle de l'arrêt, pas ce qu'il en reste) s'y applique.
    carence_emp = int(carence.get("carence_employeur_jours") or 0)
    carence_emp_arret = int(carence.get("carence_employeur_jours_arret", carence_emp) or 0)
    jours_deja = _jours_deja_en_arret(arret)

    # Durée conventionnelle : durée custom si paramétrée, sinon durée légale.
    custom_d = int(settings.get("custom_duration_days") or 0)
    cap_conv = custom_d if custom_d > 0 else duree_legale_totale

    est_at_mp = bool(qualification.get("est_at_mp"))
    taux_conv = _taux_conventionnel(settings, est_at_mp)

    jours_intersection = _compter_jours_calendaires(inter_d, inter_f)
    offset = (inter_d - date_debut_arret).days

    # --- Congé de parentalité (maternité / paternité / adoption) : maintien à
    # 100 % du salaire, INCONDITIONNEL sur toute la durée du congé, sans barème
    # dégressif D1226-1 (propre à la maladie) et sans carence employeur. Le brut
    # reconstruit = salaire plein (l'absence déduite est exactement compensée par
    # le maintien). Les IJSS maternité, versées dès J1 et récupérées par
    # l'employeur via subrogation, n'apparaissent PAS séparément au brut (le
    # maintien affiché EST le salaire plein) : on ne les soustrait donc pas du
    # maintien versé, contrairement au régime maladie. La condition d'ancienneté
    # conventionnelle (métallurgie : ≥ 1 an) est déjà appliquée en amont via le
    # seuil `min_seniority_months` (return anticipé si non éligible).
    # Réf. : Code du travail L1225-17 et s. ; CCN métallurgie IDCC 3248 art. 92.
    if bool(qualification.get("est_maternite")) and not settings.get(
        "maintain_parental_leave"
    ):
        return {
            "maintien_applicable": False,
            "taux_maintien": 0.0,
            "maintien_cible": 0.0,
            "maintien_verse": 0.0,
            "nb_jours_maintien": 0,
            "complement_employeur": 0.0,
            "conflit_convention": False,
            "motif_non_maintien": MOTIF_PARENTALITE_SANS_MAINTIEN,
            "proratisation_temps_partiel": False,
            "carence_employeur_jours": 0,
            "duree_par_taux_jours": 0,
            "duree_maintien_legale_jours": 0,
            "est_maternite": True,
        }
    if bool(qualification.get("est_maternite")):
        jours_maintien_mat = 0
        for k in range(jours_intersection):
            if maintien_base_ouvree and (inter_d + timedelta(days=k)).weekday() >= 5:
                continue  # mode jours ouvrés : week-ends non maintenus
            jours_maintien_mat += 1
        maintien_cible_mat = brut_journalier * jours_maintien_mat  # taux 100 %

        prorat_tp_mat = False
        if bool(arret.get("is_temps_partiel")):
            qtp = float(arret.get("quotite_temps_partiel") or 1.0)
            if qtp > 0:
                maintien_cible_mat *= qtp
                prorat_tp_mat = True

        if bool(arret.get("subrogation_active")):
            maintien_verse_mat, deduction_mat = maintien_cible_mat, {}
        else:
            # Tout le congé est maintenu, en jours calendaires.
            jours_mat = {inter_d + timedelta(days=k) for k in range(jours_intersection)}
            maintien_verse_mat, deduction_mat = _verse_sans_subrogation(
                maintien_cible_mat, settings, jours_mat, ijss, ijss_par_jour, releve_du_mois
            )

        salaire_reel_mat = float(arret.get("salaire_periode_reelle") or 0.0)
        return {
            "maintien_applicable": True,
            "taux_maintien": 1.0,
            "maintien_cible": round(maintien_cible_mat, 2),
            "maintien_verse": round(maintien_verse_mat, 2),
            "nb_jours_maintien": jours_maintien_mat,
            "complement_employeur": round(maintien_verse_mat - salaire_reel_mat, 2),
            "conflit_convention": False,
            "motif_non_maintien": None,
            "proratisation_temps_partiel": prorat_tp_mat,
            "carence_employeur_jours": 0,
            "duree_par_taux_jours": 0,
            "duree_maintien_legale_jours": 0,
            "est_maternite": True,
            **deduction_mat,
        }

    maintien_total_legal = 0.0
    maintien_total_conv = 0.0
    #: Jours de carence payés par l'employeur (crédit annuel), à 100 %.
    nb_jours_carence_payes = 0
    nb_jours_maintien = 0
    # Jours maintenus en jours calendaires (week-ends compris en jours ouvrés) :
    # ceux dont la CPAM déduit les IJSS sans subrogation, si la société le veut.
    jours_payes: set = set()
    jours_leg: set = set()
    jours_conv: set = set()
    for k in range(jours_intersection):
        jour = inter_d + timedelta(days=k)
        if jour in jours_carence_payes:
            nb_jours_carence_payes += 1
            nb_jours_maintien += 1
            jours_payes.add(jour)
            continue
        rang_maintien = jours_deja + offset + k + 1 - carence_emp_arret
        if rang_maintien >= 1:
            if apply_legal and _taux_legal_pour_jour_maintien(rang_maintien, duree_par_taux) > 0:
                jours_leg.add(jour)
            if taux_conv is not None and rang_maintien <= cap_conv and float(taux_conv) > 0:
                jours_conv.add(jour)
        if maintien_base_ouvree and (inter_d + timedelta(days=k)).weekday() >= 5:
            continue  # mode jours ouvrés : week-ends non maintenus
        jour_arret = jours_deja + offset + k + 1  # rang calendaire dans l'arrêt
        jour_maintien = jour_arret - carence_emp_arret  # rang après carence employeur
        if jour_maintien < 1:
            continue  # jour couvert par la carence employeur : pas de maintien

        t_leg = (
            _taux_legal_pour_jour_maintien(jour_maintien, duree_par_taux)
            if apply_legal
            else 0.0
        )
        m_leg_jour = brut_journalier * t_leg

        if taux_conv is not None and jour_maintien <= cap_conv:
            m_conv_jour = brut_journalier * float(taux_conv)
        else:
            m_conv_jour = 0.0

        maintien_total_legal += m_leg_jour
        maintien_total_conv += m_conv_jour

        if m_leg_jour > 0 or m_conv_jour > 0:
            nb_jours_maintien += 1

    if taux_conv is not None and apply_legal:
        if maintien_total_conv < maintien_total_legal - 1e-6:
            conflit_convention = True
            maintien_cible = maintien_total_legal
        else:
            maintien_cible = max(maintien_total_legal, maintien_total_conv)
    elif taux_conv is not None:
        maintien_cible = maintien_total_conv
    else:
        maintien_cible = maintien_total_legal
    if nb_jours_carence_payes:
        maintien_cible += (
            _valeur_de_jours_ouvres(
                contexte,
                float(contexte.duree_hebdo_contrat or 0.0),
                taux_horaire_base,
                nb_jours_carence_payes,
            )
            if maintien_base_ouvree
            else brut_journalier * nb_jours_carence_payes
        )

    prorat_tp = False
    if bool(arret.get("is_temps_partiel")):
        qtp = float(arret.get("quotite_temps_partiel") or 1.0)
        if qtp > 0:
            maintien_cible *= qtp
            prorat_tp = True

    taux_moyen = (
        (maintien_cible / (brut_journalier * nb_jours_maintien))
        if nb_jours_maintien and brut_journalier
        else 0.0
    )

    # Les jours maintenus, ceux de la règle retenue pour la cible.
    if taux_conv is not None and (
        not apply_legal or maintien_total_conv >= maintien_total_legal - 1e-6
    ):
        jours_maintenus = jours_conv | jours_payes
    else:
        jours_maintenus = jours_leg | jours_payes

    subrogation_active = bool(arret.get("subrogation_active"))
    deduction: Dict[str, Any] = {}
    if subrogation_active:
        maintien_verse = _verse_avec_subrogation(
            maintien_cible, arret, jours_maintenus, ijss, ijss_par_jour, releve_du_mois
        )
    else:
        maintien_verse, deduction = _verse_sans_subrogation(
            maintien_cible, settings, jours_maintenus, ijss, ijss_par_jour, releve_du_mois
        )

    salaire_reel = float(arret.get("salaire_periode_reelle") or 0.0)
    complement = maintien_verse - salaire_reel

    return {
        "maintien_applicable": True,
        "taux_maintien": round(min(taux_moyen, 1.0), 4),
        "maintien_cible": round(maintien_cible, 2),
        "maintien_verse": round(maintien_verse, 2),
        "nb_jours_maintien": nb_jours_maintien,
        "complement_employeur": round(complement, 2),
        "conflit_convention": conflit_convention,
        "motif_non_maintien": motif_non_maintien,
        "proratisation_temps_partiel": prorat_tp,
        "carence_employeur_jours": carence_emp,
        "duree_par_taux_jours": duree_par_taux,
        "duree_maintien_legale_jours": duree_legale_totale,
        **deduction,
    }


# --- Bloc 5 : prévoyance ---


def _statut_est_cadre(statut: Optional[str]) -> bool:
    """Vrai si le statut correspond à un cadre / assimilé cadre (et non « Non-Cadre »)."""
    s = (statut or "").strip().lower()
    if not s:
        return False
    if "non cadre" in s or "non-cadre" in s:
        return False
    return "cadre" in s


def _verifier_prevoyance_relais(
    nb_jours_arret_total: int, settings: Dict[str, Any]
) -> Dict[str, Any]:
    seuil = settings.get("provident_relay_days")
    if seuil is None:
        return {"prevoyance_declenchee": False, "seuil_jours": None}
    try:
        seuil_int = int(seuil)
    except (TypeError, ValueError):
        return {"prevoyance_declenchee": False, "seuil_jours": None}
    if seuil_int <= 0:
        return {"prevoyance_declenchee": False, "seuil_jours": seuil_int}
    decl = nb_jours_arret_total >= seuil_int
    return {"prevoyance_declenchee": decl, "seuil_jours": seuil_int}


def _calculer_prevoyance_complement(
    arret: Dict[str, Any],
    qualification: Dict[str, Any],
    settings: Dict[str, Any],
    *,
    est_cadre: bool,
    anciennete_mois: int,
    brut_journalier: float,
    base_plafonnee: float,
    ij_plafonds: Optional[Dict[str, Any]],
    carence_ss: int,
    carence_emp: int,
    duree_par_taux: int,
    cap_conv: int,
    taux_conv: Optional[float],
    apply_legal: bool,
    nb_jours_arret_total: int,
    date_debut_arret: date,
    date_fin_arret: date,
    date_debut_periode: date,
    date_fin_periode: date,
    jours_deja_en_arret: int = 0,
    taux_maintien_par_jour: Optional[Dict[date, float]] = None,
) -> Dict[str, Any]:
    """
    Complément de prévoyance (relais), paramétré par l'entreprise via les settings :

    - ``provident_maintenance_rate`` : taux net de remplacement garanti (% du brut),
      par exemple 0,80 pour 80 %.
    - ``provident_relay_days`` : franchise — jour de l'arrêt à partir duquel la
      prévoyance intervient (par défaut, fin du maintien employeur légal).
    - ``provident_cadre_only`` : la garantie ne concerne que les cadres (défaut : True,
      conformément à l'obligation de prévoyance cadre — ANI 2017 / CCN 1947).

    La prévoyance ne fait que combler l'écart par rapport au taux cible, déduction
    faite des IJSS et du maintien employeur déjà versés (pas de double indemnisation).
    Montant informatif : il est versé par l'organisme assureur, pas directement par
    l'employeur.
    """
    base = {
        "prevoyance_declenchee": False,
        "seuil_jours": settings.get("provident_relay_days"),
        "eligible": False,
        "taux_cible": None,
        "franchise_jours": None,
        "montant": 0.0,
        "nb_jours": 0,
        "motif": None,
    }

    relais_flag = _verifier_prevoyance_relais(nb_jours_arret_total, settings)
    base["prevoyance_declenchee"] = relais_flag["prevoyance_declenchee"]
    base["seuil_jours"] = relais_flag["seuil_jours"]

    rate = settings.get("provident_maintenance_rate")
    if not isinstance(rate, (int, float)) or rate <= 0:
        base["motif"] = "Aucun taux de prévoyance paramétré."
        return base

    cadre_only = settings.get("provident_cadre_only")
    cadre_only = True if cadre_only is None else bool(cadre_only)
    if cadre_only and not est_cadre:
        base["motif"] = "Garantie prévoyance réservée aux cadres (non applicable)."
        return base

    taux_cible = float(rate)
    base["eligible"] = True
    base["taux_cible"] = round(taux_cible, 4)

    franchise = settings.get("provident_relay_days")
    if franchise is None:
        franchise = (2 * duree_par_taux) if apply_legal else 0
    else:
        try:
            franchise = int(franchise)
        except (TypeError, ValueError):
            franchise = 0
    base["franchise_jours"] = franchise

    inter_d, inter_f = _intersection_dates(
        date_debut_arret, date_fin_arret, date_debut_periode, date_fin_periode
    )
    if inter_d is None or inter_f is None:
        return base

    montant = 0.0
    nb_jours = 0
    d = date_debut_arret
    while d <= date_fin_arret:
        offset = (d - date_debut_arret).days
        if inter_d <= d <= inter_f:
            jour_arret = jours_deja_en_arret + offset + 1
            if jour_arret >= max(1, franchise):
                # IJSS du jour
                if offset >= carence_ss:
                    taux_ij = _taux_ijss_pour_jour_arret(
                        str(arret.get("arret_type") or "maladie_simple"),
                        jour_arret,
                        int(arret.get("nombre_enfants") or 0),
                    )
                    ijss_jour = base_plafonnee * taux_ij
                    plafond_j = plafond_ij_pour(
                        str(arret.get("arret_type") or "maladie_simple"),
                        jour_arret,
                        ij_plafonds,
                    )
                    if plafond_j is not None:
                        ijss_jour = min(ijss_jour, plafond_j)
                else:
                    ijss_jour = 0.0

                # Maintien employeur du jour (le plus favorable légal / conventionnel).
                # Sous le barème : le taux du jour dans la règle retenue.
                if taux_maintien_par_jour is not None:
                    maintien_jour = brut_journalier * taux_maintien_par_jour.get(d, 0.0)
                else:
                    jour_maintien = jour_arret - carence_emp
                    m_leg = (
                        brut_journalier
                        * _taux_legal_pour_jour_maintien(jour_maintien, duree_par_taux)
                        if apply_legal
                        else 0.0
                    )
                    m_conv = (
                        brut_journalier * float(taux_conv)
                        if (taux_conv is not None and 1 <= jour_maintien <= cap_conv)
                        else 0.0
                    )
                    maintien_jour = max(m_leg, m_conv)

                complement = taux_cible * brut_journalier - ijss_jour - maintien_jour
                if complement > 0:
                    montant += complement
                    nb_jours += 1
        d += timedelta(days=1)

    base["montant"] = round(montant, 2)
    base["nb_jours"] = nb_jours
    if montant > 0:
        base["prevoyance_declenchee"] = True
    return base


# --- Subrogation ---

_AT_MP_TYPES = frozenset(
    {
        "accident_travail",
        "maladie_professionnelle",
        "accident_trajet",
        "rechute_at",
    }
)


def _jours_de_carence_payes_de_l_arret(
    arret: Dict[str, Any],
    settings: Dict[str, Any],
    *,
    date_entree: Optional[date],
    date_debut_arret: date,
    date_fin_arret: date,
    arret_type: str,
    est_cadre: bool,
) -> frozenset[date]:
    """Les jours de carence de cet arrêt que l'employeur paie (crédit annuel).

    Le crédit se lit sur les arrêts de l'année (`arrets_annee`, reconstitués
    depuis les calendriers), dans l'ordre. Les cadres en sont exclus : chez
    Gaëlle, « les cadres n'ont pas de carence », règle encore à préciser.
    """
    from app.modules.payroll.engine.carence_payee import (
        ArretDeLAnnee,
        jours_de_carence_payes,
    )

    jours_par_an = int(settings.get("paid_waiting_days_per_year") or 0)
    if jours_par_an <= 0 or est_cadre:
        return frozenset()
    courant = ArretDeLAnnee(date_debut_arret, date_fin_arret, arret_type)
    arrets: list[ArretDeLAnnee] = []
    for autre in arret.get("arrets_annee") or []:
        debut = _parse_date((autre or {}).get("debut"))
        fin = _parse_date((autre or {}).get("fin")) or debut
        if debut is None:
            continue
        arrets.append(ArretDeLAnnee(debut, fin, str(autre.get("type") or "maladie")))
    # L'arrêt calculé s'ajoute s'il n'est pas déjà lu aux calendriers. Ses jours
    # payés sont ceux du plan qui tombent dans ses dates : un arrêt du bulletin
    # qui en réunit plusieurs (demandes qui se recouvrent) garde leur carence.
    if not any(a.debut <= courant.fin and courant.debut <= a.fin for a in arrets):
        arrets.append(courant)
    plan = jours_de_carence_payes(
        arrets,
        jours_par_an=jours_par_an,
        date_entree=date_entree,
        anciennete_min_mois=int(settings.get("paid_waiting_min_seniority_months") or 12),
    )
    return frozenset(
        jour
        for jours in plan.values()
        for jour in jours
        if courant.debut <= jour <= courant.fin
    )


def resolve_subrogation_active(
    settings: Dict[str, Any],
    arret_type: str,
    maintien_eligible: bool,
    override: Optional[bool] = None,
) -> bool:
    """
    Détermine si la subrogation IJSS est active pour cet arrêt.

    :param maintien_eligible: True si l'ancienneté permet le maintien employeur.
    """
    if override is not None:
        return bool(override)
    mode = settings.get("subrogation_mode") or "when_maintien"
    if mode == "never":
        return False
    if mode == "automatic":
        mode = "when_maintien"
    t = (arret_type or "maladie_simple").strip()
    if mode == "at_mp_only":
        return t in _AT_MP_TYPES and maintien_eligible
    if mode == "per_case":
        return maintien_eligible
    return maintien_eligible


def _quote_part_hs_structurelles_journaliere(
    contexte: ContextePaie, duree_hebdo: float, taux_horaire_base: float
) -> float:
    """Heures sup structurelles d'une journée, valorisées à leur taux majoré.

    Les 17,33 h mensuelles d'un contrat de 39 h sont réparties sur les jours
    ouvrés légaux du mois (151,67 / 7 = 21,67) : 0,80 h par journée.
    Vaut zéro à 35 h ou moins.
    """
    heures_jour, majoration = _heures_sup_structurelles_par_jour(contexte, duree_hebdo)
    return heures_jour * taux_horaire_base * (1 + majoration)


def _heures_sup_structurelles_par_jour(
    contexte: ContextePaie, duree_hebdo: float
) -> tuple[float, float]:
    """(heures sup structurelles d'une journée, majoration) ; (0, 0) à 35 h."""
    if not duree_hebdo or duree_hebdo <= lc.DUREE_LEGALE_HEBDO:
        return 0.0, 0.0
    try:
        from .calcul_brut import (
            _taux_majoration_hs,
            compute_hs_structurelles_mensuelles,
            heures_mensuelles_legales,
        )

        heures_mois = compute_hs_structurelles_mensuelles(duree_hebdo)
        jours_legaux = heures_mensuelles_legales() / (lc.DUREE_LEGALE_HEBDO / 5.0)
        if not jours_legaux:
            return 0.0, 0.0
        majoration = _taux_majoration_hs(contexte, 0) or 0.0
    except Exception:
        return 0.0, 0.0
    return heures_mois / jours_legaux, majoration


def _valeur_de_jours_ouvres(
    contexte: ContextePaie, duree_hebdo: float, taux_horaire_base: float, nb_jours: int
) -> float:
    """La valeur de journées maintenues, comptée comme le cabinet : les heures de
    base puis les heures sup structurelles, chacune arrondie une fois.

    Colorplast, mars 2026 : 3 jours = 21,00 h à 12,9492 (271,93) + 2,40 h à
    16,1865 (38,85) = 310,78 ; la somme de trois journées non arrondies donnait
    310,77.
    """
    heures_jour, majoration = _heures_sup_structurelles_par_jour(contexte, duree_hebdo)
    heures_base = nb_jours * (lc.DUREE_LEGALE_HEBDO / 5.0)
    heures_sup = round(nb_jours * heures_jour, 2)
    return round(heures_base * taux_horaire_base, 2) + round(
        heures_sup * taux_horaire_base * (1 + majoration), 2
    )


# --- Barème de la convention : la valeur des jours maintenus ---


def _salaire_du_mois(
    contexte: ContextePaie, duree_hebdo: float, taux_horaire_base: float
) -> float:
    """Le salaire d'un mois entièrement travaillé : la base et ses heures sup
    structurelles, comme les lignes du bulletin. Comitech, juin 2026 : 1 952,60
    de base et 17,33 h à 16,0925, soit 2 231,48."""
    from .salaire_contractuel import salaire_hors_hs_structurelles

    base = round(float(contexte.salaire_base_mensuel or 0.0), 2)
    heures_jour, majoration = _heures_sup_structurelles_par_jour(contexte, duree_hebdo)
    if not heures_jour or not salaire_hors_hs_structurelles(contexte.contrat):
        return base
    from .calcul_brut import compute_hs_structurelles_mensuelles

    heures = compute_hs_structurelles_mensuelles(duree_hebdo)
    return round(base + round(heures * taux_horaire_base * (1 + majoration), 2), 2)


@dataclass
class BaseDesJours:
    """Ce que vaut un jour maintenu sous le barème (conception du 24/10, §3.3).

    Mois entier en arrêt : le salaire du mois, réparti au prorata des jours
    (ouvrés en jours ouvrés). Sinon, la journée : en jours ouvrés, 7 h et la
    quote-part d'heures sup structurelles, comptées par bloc comme le cabinet ;
    sinon salaire / 30,42 par jour calendaire. La quotité d'un temps partiel ne
    s'applique qu'à la journée : le salaire du mois est déjà au temps partiel.
    """

    contexte: Any
    jours_ouvres: bool
    mois_entier: bool
    jours_du_mois: int
    salaire_du_mois: float
    taux_horaire_base: float
    duree_hebdo: float
    quotite: float

    def compte(self, jour: date) -> bool:
        return not self.jours_ouvres or jour.weekday() < 5

    def valeur(self, nb_jours: int) -> float:
        if nb_jours <= 0:
            return 0.0
        if self.mois_entier and self.jours_du_mois > 0:
            return round(self.salaire_du_mois * nb_jours / self.jours_du_mois, 2)
        if self.jours_ouvres:
            brut = _valeur_de_jours_ouvres(
                self.contexte, self.duree_hebdo, self.taux_horaire_base, nb_jours
            )
        else:
            salaire = float(self.contexte.salaire_base_mensuel or 0.0)
            brut = salaire / lc.DIVISEUR_JOURS_CALENDAIRES * nb_jours
        return round(brut * self.quotite, 2)


def _base_des_jours(
    arret: Dict[str, Any],
    contexte: ContextePaie,
    date_debut_periode: date,
    date_fin_periode: date,
) -> BaseDesJours:
    jours_ouvres = bool(arret.get("maintien_base_ouvree"))
    duree_hebdo = float(contexte.duree_hebdo_contrat or 0.0)
    try:
        from .calcul_brut import _get_salaire_horaire_base

        taux_horaire_base = _get_salaire_horaire_base(contexte, duree_hebdo)
    except Exception:
        taux_horaire_base = 0.0
    mois_entier = arret.get("mois_entier_en_arret")
    if mois_entier is None:
        debut = _parse_date(arret.get("date_debut"))
        fin = _parse_date(arret.get("date_fin")) or debut
        mois_entier = bool(
            debut and fin and debut <= date_debut_periode and fin >= date_fin_periode
        )
    jours_du_mois = sum(
        1
        for k in range(_compter_jours_calendaires(date_debut_periode, date_fin_periode))
        if not jours_ouvres or (date_debut_periode + timedelta(days=k)).weekday() < 5
    )
    salaire = (
        _salaire_du_mois(contexte, duree_hebdo, taux_horaire_base)
        if jours_ouvres
        else round(float(contexte.salaire_base_mensuel or 0.0), 2)
    )
    quotite = 1.0
    if bool(arret.get("is_temps_partiel")):
        q = float(arret.get("quotite_temps_partiel") or 1.0)
        if q > 0:
            quotite = q
    return BaseDesJours(
        contexte=contexte,
        jours_ouvres=jours_ouvres,
        mois_entier=bool(mois_entier),
        jours_du_mois=jours_du_mois,
        salaire_du_mois=salaire,
        taux_horaire_base=taux_horaire_base,
        duree_hebdo=duree_hebdo,
        quotite=quotite,
    )


# --- Barème de la convention : plan, plancher légal, maintien ---

#: Plancher légal sous le barème : 7 jours de carence, comme le moteur
#: aujourd'hui (MSS, `_calculer_carence`), 0 en accident du travail et maladie
#: professionnelle hors trajet.
CARENCE_LEGALE_EMPLOYEUR_JOURS = 7
#: Plancher légal sous le barème : une année d'ancienneté (L1226-1).
ANCIENNETE_LEGALE_MOIS = 12


def _est_cadre(contexte: ContextePaie) -> bool:
    try:
        return _statut_est_cadre(str(contexte.statut_salarie or ""))
    except Exception:
        return False


def _plan_au_bareme(
    arret: Dict[str, Any],
    contexte: ContextePaie,
    bareme: Bareme,
    arret_type: str,
    date_debut_arret: date,
    date_fin_arret: date,
) -> PlanConventionnel:
    """Les arrêts connus du salarié, rejoués avec le barème de la société."""
    return plan_conventionnel(
        arrets_pour_le_plan(
            arret.get("arrets_connus") or [], date_debut_arret, date_fin_arret, arret_type
        ),
        bareme=bareme,
        est_cadre=_est_cadre(contexte),
        date_anciennete=_date_anciennete(contexte),
    )


def _carence_au_bareme(
    carence: Dict[str, Any],
    plan: PlanConventionnel,
    bareme: Bareme,
    date_debut_arret: date,
    date_fin_arret: date,
) -> Dict[str, Any]:
    """La carence employeur du barème, à la place de celle des réglages manuels."""
    rejoue = plan.arret_du_jour(date_debut_arret)
    jours = [
        j for j in (rejoue.jours_de_carence if rejoue else ())
        if date_debut_arret <= j <= date_fin_arret
    ]
    sortie = {
        **carence,
        "carence_employeur_jours": len(jours),
        "carence_employeur_jours_arret": rejoue.carence_jours if rejoue else 0,
    }
    if rejoue is not None and not carence.get("prolongation_de"):
        ss = int(carence.get("carence_ss_jours") or 0)
        sortie["motif_carence"] = (
            f"Carence SS : {_jours_fr(ss)}. {motif_carence_du_bareme(bareme, rejoue)}"
        )
    return sortie


def _anciennete_legale_atteinte(
    arret: Dict[str, Any], contexte: ContextePaie, date_debut_arret: date
) -> bool:
    date_anc = _date_anciennete(contexte)
    debut_chaine = _parse_date(arret.get("date_debut_chaine")) or date_debut_arret
    return date_anc is not None and mois_complets(date_anc, debut_chaine) >= ANCIENNETE_LEGALE_MOIS


def _taux_legaux_au_bareme(
    arret: Dict[str, Any],
    qualification: Dict[str, Any],
    contexte: ContextePaie,
    anciennete_mois: int,
    date_debut_arret: date,
    jours: List[date],
) -> Dict[date, float]:
    """Le maintien légal sous le barème, sans aucun réglage de la société."""
    if not _anciennete_legale_atteinte(arret, contexte, date_debut_arret):
        return {}
    trajet = str(arret.get("arret_type") or "").strip() == "accident_trajet"
    carence = 0 if (qualification.get("est_at_mp") and not trajet) else CARENCE_LEGALE_EMPLOYEUR_JOURS
    duree = duree_maintien_par_taux(anciennete_mois)
    jours_deja = _jours_deja_en_arret(arret)
    taux: Dict[date, float] = {}
    for jour in jours:
        rang = jours_deja + (jour - date_debut_arret).days + 1 - carence
        t = _taux_legal_pour_jour_maintien(rang, duree)
        if t > 0:
            taux[jour] = t
    return taux


def _repartir_les_ijss(
    paliers: List[Dict[str, Any]],
    retenues: float,
    ijss: Dict[str, Any],
    ijss_par_jour: Optional[Dict[date, float]],
    releve_du_mois: Optional[ReleveIjss],
) -> None:
    """Les IJSS déduites, palier par palier ; le dernier prend l'arrondi."""
    if retenues > 0 and ijss_par_jour is not None and paliers:
        parts = [
            _ijss_des_jours_maintenus(set(p["_jours"]), ijss, ijss_par_jour, releve_du_mois)[0]
            for p in paliers
        ]
        total = sum(parts)
        reste = round(retenues, 2)
        for rang, palier in enumerate(paliers):
            if rang == len(paliers) - 1:
                part = reste
            else:
                part = round(retenues * parts[rang] / total, 2) if total > 0 else 0.0
            palier["ijss_deduites"] = round(part, 2)
            reste = round(reste - part, 2)
    for palier in paliers:
        palier.pop("_jours", None)


def _option_au_bareme(
    taux_par_jour: Dict[date, float],
    *,
    base: BaseDesJours,
    arret: Dict[str, Any],
    settings: Dict[str, Any],
    ijss: Dict[str, Any],
    ijss_par_jour: Optional[Dict[date, float]],
    releve_du_mois: Optional[ReleveIjss],
) -> Dict[str, Any]:
    """Une règle (barème ou légal) : ses paliers du mois, son garanti, son versé."""
    paliers: List[Dict[str, Any]] = []
    for taux in set(taux_par_jour.values()):
        jours = sorted(j for j, t in taux_par_jour.items() if t == taux)
        nb = sum(1 for j in jours if base.compte(j))
        valeur = base.valeur(nb)
        paliers.append(
            {
                "taux": round(taux, 4),
                "du": jours[0].isoformat(),
                "au": jours[-1].isoformat(),
                "jours": nb,
                "jours_calendaires": len(jours),
                "valeur": valeur,
                "garanti": round(valeur * taux, 2),
                "_jours": jours,
            }
        )
    paliers.sort(key=lambda p: p["du"])
    cible = round(sum(p["garanti"] for p in paliers), 2)
    jours_maintenus = set(taux_par_jour)
    deduction: Dict[str, Any] = {}
    if bool(arret.get("subrogation_active")):
        verse = _verse_avec_subrogation(
            cible, arret, jours_maintenus, ijss, ijss_par_jour, releve_du_mois
        )
        retenues = round(cible - verse, 2)
    else:
        verse, deduction = _verse_sans_subrogation(
            cible, settings, jours_maintenus, ijss, ijss_par_jour, releve_du_mois
        )
        retenues = float(deduction.get(CLE_IJSS_DEDUITES) or 0.0)
    _repartir_les_ijss(paliers, retenues, ijss, ijss_par_jour, releve_du_mois)
    return {
        "cible": cible,
        "verse": round(verse, 2),
        "paliers": paliers,
        "deduction": deduction,
        "taux_par_jour": dict(taux_par_jour),
    }


def _calculer_maintien_au_bareme(
    arret: Dict[str, Any],
    qualification: Dict[str, Any],
    carence: Dict[str, Any],
    ijss: Dict[str, Any],
    contexte: ContextePaie,
    settings: Dict[str, Any],
    date_debut_arret: date,
    anciennete_mois: int,
    date_debut_periode: date,
    date_fin_periode: date,
    *,
    plan: PlanConventionnel,
    bareme: Bareme,
    ijss_par_jour: Optional[Dict[date, float]],
    releve_du_mois: Optional[ReleveIjss],
) -> Tuple[Dict[str, Any], Dict[date, float]]:
    """Le maintien sous le barème, et le taux de chaque jour retenu.

    Le barème et le maintien légal valorisent les jours de la même façon
    (`BaseDesJours`) ; Martine verse le plus favorable des deux, jugé sur ce
    que l'employeur verse (garanti moins les IJSS de ses jours), pas sur le
    garanti seul (conception du 24/10, §3.4).
    """
    date_fin_arret = _parse_date(arret.get("date_fin")) or date_debut_arret
    rejoue = plan.arret_du_jour(date_debut_arret)
    duree_par_taux = duree_maintien_par_taux(anciennete_mois)
    commun: Dict[str, Any] = {
        "carence_employeur_jours": int(carence.get("carence_employeur_jours") or 0),
        "duree_par_taux_jours": duree_par_taux,
        "duree_maintien_legale_jours": 2 * duree_par_taux,
        "bareme": bareme.code,
        "bareme_detail": detail_du_bareme(bareme, _est_cadre(contexte), rejoue),
    }
    convention_ouverte = rejoue is not None and rejoue.tranche is not None
    if not convention_ouverte and not _anciennete_legale_atteinte(arret, contexte, date_debut_arret):
        return (
            {
                **commun,
                "maintien_applicable": False,
                "taux_maintien": 0.0,
                "maintien_cible": 0.0,
                "maintien_verse": 0.0,
                "nb_jours_maintien": 0,
                "complement_employeur": 0.0,
                "conflit_convention": False,
                "motif_non_maintien": motif_sans_droit(bareme, rejoue),
                "proratisation_temps_partiel": False,
                "regle_retenue": "convention",
                "paliers": [],
            },
            {},
        )
    inter_d, inter_f = _intersection_dates(
        date_debut_arret, date_fin_arret, date_debut_periode, date_fin_periode
    )
    jours: List[date] = (
        []
        if inter_d is None or inter_f is None
        else [inter_d + timedelta(days=k) for k in range(_compter_jours_calendaires(inter_d, inter_f))]
    )
    base = _base_des_jours(arret, contexte, date_debut_periode, date_fin_periode)
    options = dict(
        base=base, arret=arret, settings=settings, ijss=ijss,
        ijss_par_jour=ijss_par_jour, releve_du_mois=releve_du_mois,
    )
    convention = _option_au_bareme(
        {j: plan.taux_par_jour[j] for j in jours if j in plan.taux_par_jour}, **options
    )
    legal = _option_au_bareme(
        _taux_legaux_au_bareme(arret, qualification, contexte, anciennete_mois, date_debut_arret, jours),
        **options,
    )
    legal_retenu = legal["verse"] > convention["verse"] + 1e-9
    retenue = legal if legal_retenu else convention
    total_valeur = sum(p["valeur"] for p in retenue["paliers"])
    salaire_reel = float(arret.get("salaire_periode_reelle") or 0.0)
    return (
        {
            **commun,
            "maintien_applicable": True,
            "taux_maintien": (
                round(min(retenue["cible"] / total_valeur, 1.0), 4) if total_valeur else 0.0
            ),
            "maintien_cible": retenue["cible"],
            "maintien_verse": retenue["verse"],
            "nb_jours_maintien": sum(p["jours"] for p in retenue["paliers"]),
            "complement_employeur": round(retenue["verse"] - salaire_reel, 2),
            "conflit_convention": legal_retenu,
            "motif_non_maintien": None,
            "proratisation_temps_partiel": base.quotite != 1.0 and not base.mois_entier,
            "regle_retenue": "legal" if legal_retenu else "convention",
            "paliers": retenue["paliers"],
            "paliers_en_jours_ouvres": base.jours_ouvres,
            **retenue["deduction"],
        },
        retenue["taux_par_jour"],
    )


# --- Prolongation et arrêts du mois ---


def _jours_deja_en_arret(arret: Dict[str, Any]) -> int:
    try:
        return max(0, int(arret.get("jours_deja_en_arret") or 0))
    except (TypeError, ValueError):
        return 0


def _poser_la_chaine(
    arret: Dict[str, Any], debut: date, fin: Optional[date], arret_type: str
) -> Dict[str, Any]:
    """L'arrêt, avec le début de l'arrêt qu'il prolonge et ses jours déjà passés.

    Lu dans `arrets_connus` (les arrêts du salarié lus aux calendriers, comme au
    bulletin, ou par l'aperçu de la demande) ; sans eux, l'arrêt est seul.
    """
    if arret.get("jours_deja_en_arret") is not None or not arret.get("arrets_connus"):
        return arret
    debut_chaine, jours_deja = chainer_arret(
        debut, fin or debut, arret_type, arret.get("arrets_connus") or []
    )
    if debut_chaine is None:
        return arret
    return {
        **arret,
        "date_debut_chaine": debut_chaine.isoformat(),
        "jours_deja_en_arret": jours_deja,
    }


def _jours_fr(n: int) -> str:
    return f"{n} jour{'s' if n > 1 else ''}"


def _carence_d_une_prolongation(
    carence: Dict[str, Any], jours_deja: int, debut_chaine: date
) -> Dict[str, Any]:
    """Ce qu'il reste de la carence de l'arrêt prolongé : rien, le plus souvent."""
    ss = int(carence.get("carence_ss_jours") or 0)
    emp = int(carence.get("carence_employeur_jours") or 0)
    reste_ss, reste_emp = max(0, ss - jours_deja), max(0, emp - jours_deja)
    debut = debut_chaine.strftime("%d/%m/%Y")
    if reste_ss or reste_emp:
        restes = []
        if reste_ss:
            restes.append(f"{_jours_fr(reste_ss)} de Sécurité sociale")
        if reste_emp:
            restes.append(f"{_jours_fr(reste_emp)} employeur")
        motif = (
            f"Prolongation de l'arrêt commencé le {debut} : sa carence se poursuit "
            f"({', '.join(restes)})."
        )
    else:
        motif = f"Prolongation de l'arrêt commencé le {debut} : pas de nouvelle carence."
    return {
        **carence,
        "carence_ss_jours": reste_ss,
        "carence_employeur_jours": reste_emp,
        "carence_employeur_jours_arret": emp,
        "jours_deja_en_arret": jours_deja,
        "prolongation_de": debut_chaine.isoformat(),
        "motif_carence": motif,
        "est_continuite": True,
    }


def _arret_du_segment(arret: Dict[str, Any], segment: Dict[str, Any]) -> Dict[str, Any]:
    sous = {**arret, **segment}
    sous.pop("arrets_du_mois", None)
    return sous


def _releve_ijss_du_mois(
    arret: Dict[str, Any],
    segments: List[Dict[str, Any]],
    contexte: ContextePaie,
    settings: Dict[str, Any],
    date_debut_periode: date,
    date_fin_periode: date,
) -> Optional[ReleveIjss]:
    """Le relevé validé du mois et ce que Martine estime pour tous les arrêts.

    Quand un arrêt du mois est subrogé, ou que la déduction sans subrogation
    est allumée : chaque arrêt en déduit alors sa part. Sinon le relevé reste
    porté par le premier arrêt, comme avant. Les estimations viennent d'un
    premier calcul de chaque arrêt, sans le relevé.
    """
    override = arret.get("ijss_brut_override")
    subroge = settings.get("subrogation_mode") != "never" and any(
        _arret_du_segment(arret, segment).get("subrogation_active") for segment in segments
    )
    if override is None or not (subroge or deduire_ijss_sans_subrogation(settings)):
        return None
    try:
        valide = float(override)
    except (TypeError, ValueError):
        return None
    if valide < 0:
        return None
    estimes = []
    for segment in segments:
        sous = _arret_du_segment(arret, segment)
        sous.pop("ijss_brut_override", None)
        estimes.append(
            calculer_maintien(sous, contexte, settings, date_debut_periode, date_fin_periode)
        )
    return (
        valide,
        sum(float((r.get("ijss") or {}).get("ijss_theorique") or 0.0) for r in estimes),
        sum(int((r.get("ijss") or {}).get("nb_jours_indemnises") or 0) for r in estimes),
    )


def _periode_couverte(
    segments: List[Dict[str, Any]],
    arret: Dict[str, Any],
    date_debut_periode: date,
    date_fin_periode: date,
) -> bool:
    """Tous les jours de la période sont-ils en arrêt, d'un arrêt ou d'un autre ?"""
    couverts: set = set()
    for segment in segments:
        sous = _arret_du_segment(arret, segment)
        debut = _parse_date(sous.get("date_debut"))
        fin = _parse_date(sous.get("date_fin")) or debut
        if debut is None or fin is None:
            continue
        jour = max(debut, date_debut_periode)
        while jour <= min(fin, date_fin_periode):
            couverts.add(jour)
            jour += timedelta(days=1)
    return len(couverts) == _compter_jours_calendaires(date_debut_periode, date_fin_periode)


def _calculer_maintien_des_arrets_du_mois(
    arret: Dict[str, Any],
    segments: List[Dict[str, Any]],
    contexte: ContextePaie,
    settings: Dict[str, Any],
    date_debut_periode: date,
    date_fin_periode: date,
) -> Dict[str, Any]:
    """Plusieurs arrêts dans la période : chacun se calcule seul, puis s'additionne.

    Avant, ils étaient fusionnés du premier jour du premier au dernier jour du
    dernier : les jours travaillés entre eux comptaient comme jours d'arrêt, et
    la carence payée était perdue ([F11-bis], enquête F du 10/10/2026). Un
    relevé d'IJSS saisi pour le mois (`ijss_brut_override`) vaut pour le mois
    entier : il est porté par le premier arrêt, les autres à zéro. Avec
    subrogation, ou sans quand la société déduit les IJSS, chaque arrêt en
    déduit sa part, au prorata des IJSS estimées du mois.
    """
    override = arret.get("ijss_brut_override")
    releve = _releve_ijss_du_mois(
        arret, segments, contexte, settings, date_debut_periode, date_fin_periode
    )
    mois_entier: Optional[bool] = None
    if bareme_des_reglages(settings) is not None:
        mois_entier = _periode_couverte(segments, arret, date_debut_periode, date_fin_periode)
    resultats: List[Dict[str, Any]] = []
    for rang, segment in enumerate(segments):
        sous = _arret_du_segment(arret, segment)
        if mois_entier is not None:
            sous["mois_entier_en_arret"] = mois_entier
        if override is not None:
            sous["ijss_brut_override"] = override if rang == 0 else 0.0
        resultats.append(
            calculer_maintien(
                sous, contexte, settings, date_debut_periode, date_fin_periode,
                releve_ijss_du_mois=releve,
            )
        )

    def _somme(bloc: str, cle: str) -> float:
        return round(sum(float((r.get(bloc) or {}).get(cle) or 0.0) for r in resultats), 2)

    def _somme_entiere(bloc: str, cle: str) -> int:
        return sum(int((r.get(bloc) or {}).get(cle) or 0) for r in resultats)

    fusion: Dict[str, Any] = {**resultats[0]}
    ijss = dict(resultats[0].get("ijss") or {})
    ijss["ijss_theorique"] = _somme("ijss", "ijss_theorique")
    ijss["nb_jours_indemnises"] = _somme_entiere("ijss", "nb_jours_indemnises")
    ijss["ijss_journaliere"] = (
        round(ijss["ijss_theorique"] / ijss["nb_jours_indemnises"], 4)
        if ijss["nb_jours_indemnises"]
        else 0.0
    )
    if any((r.get("ijss") or {}).get("ijss_brut_override") for r in resultats):
        ijss["ijss_brut_override"] = True
    maintien = dict(resultats[0].get("maintien") or {})
    for cle in ("maintien_cible", "maintien_verse", "complement_employeur"):
        maintien[cle] = _somme("maintien", cle)
    maintien["nb_jours_maintien"] = _somme_entiere("maintien", "nb_jours_maintien")
    deduites = _somme("maintien", CLE_IJSS_DEDUITES)
    maintien.pop(CLE_IJSS_DEDUITES, None)
    maintien.pop(CLE_SOURCE, None)
    if deduites > 0:
        maintien[CLE_IJSS_DEDUITES] = deduites
        maintien[CLE_SOURCE] = (
            SOURCE_VALIDEES
            if any((r.get("maintien") or {}).get(CLE_SOURCE) == SOURCE_VALIDEES for r in resultats)
            else SOURCE_ESTIMEES
        )
    maintien["maintien_applicable"] = any(
        (r.get("maintien") or {}).get("maintien_applicable", True) for r in resultats
    )
    if any("paliers" in (r.get("maintien") or {}) for r in resultats):
        maintien["paliers"] = [
            p for r in resultats for p in ((r.get("maintien") or {}).get("paliers") or [])
        ]
        legal = any((r.get("maintien") or {}).get("regle_retenue") == "legal" for r in resultats)
        maintien["regle_retenue"] = "legal" if legal else "convention"
        maintien["conflit_convention"] = legal
    carence = dict(resultats[0].get("carence") or {})
    carence["carence_ss_jours"] = _somme_entiere("carence", "carence_ss_jours")
    carence["carence_employeur_jours"] = _somme_entiere("carence", "carence_employeur_jours")
    carence["motif_carence"] = " ".join(
        str((r.get("carence") or {}).get("motif_carence") or "").strip() for r in resultats
    ).strip()
    dates_payees = sorted(
        d for r in resultats for d in (r.get("carence") or {}).get("carence_payee_dates") or []
    )
    if dates_payees:
        carence["carence_payee_dates"] = dates_payees
        carence["carence_payee_jours"] = len(dates_payees)
    prevoyance = dict(resultats[0].get("prevoyance") or {})
    prevoyance["montant"] = _somme("prevoyance", "montant")
    prevoyance["nb_jours"] = _somme_entiere("prevoyance", "nb_jours")
    prevoyance["prevoyance_declenchee"] = any(
        (r.get("prevoyance") or {}).get("prevoyance_declenchee") for r in resultats
    )
    alertes: List[str] = []
    for r in resultats:
        for alerte in r.get("alertes") or []:
            if alerte not in alertes:
                alertes.append(alerte)
    if deduites > 0:
        # Une seule alerte « IJSS versées… », avec la déduction du mois.
        rang = next(
            (i for i, a in enumerate(alertes) if est_alerte_ijss_au_salarie(a)), len(alertes)
        )
        alertes = [a for a in alertes if not est_alerte_ijss_au_salarie(a)]
        alertes.insert(rang, alerte_ijss_au_salarie(maintien))
    fusion.update(
        {
            "ijss": ijss,
            "maintien": maintien,
            "carence": carence,
            "prevoyance": prevoyance,
            "alertes": alertes,
            "subrogation_active": any(r.get("subrogation_active") for r in resultats),
            "nb_jours_arret_total": max(int(r.get("nb_jours_arret_total") or 0) for r in resultats),
            "arrets_du_mois": [
                {
                    "date_debut": s.get("date_debut"),
                    "date_fin": s.get("date_fin"),
                    "arret_type": s.get("arret_type"),
                    "ijss_theorique": (r.get("ijss") or {}).get("ijss_theorique"),
                    "maintien_verse": (r.get("maintien") or {}).get("maintien_verse"),
                    "motif_carence": (r.get("carence") or {}).get("motif_carence"),
                }
                for s, r in zip(segments, resultats)
            ],
        }
    )
    return fusion


# --- Point d'entrée ---


def compute_jours_avec_maintien_mois(
    arret: Dict[str, Any],
    contexte: ContextePaie,
    settings: Dict[str, Any],
    date_debut_periode: date,
    date_fin_periode: date,
) -> set[int]:
    """
    Jours du mois (numéro 1–31) où l'arrêt maladie/AT bénéficie d'un maintien employeur.
    Utilisé pour le prorata de la prime d'ancienneté.
    """
    segments = arret.get("arrets_du_mois") or []
    if len(segments) > 1:
        jours: set[int] = set()
        for segment in segments:
            jours |= compute_jours_avec_maintien_mois(
                _arret_du_segment(arret, segment), contexte, settings,
                date_debut_periode, date_fin_periode,
            )
        return jours

    arret_type = str(arret.get("arret_type") or "maladie_simple")
    qualification = _qualifier_arret(arret_type)

    date_debut_arret = _parse_date(arret.get("date_debut"))
    date_fin_arret = _parse_date(arret.get("date_fin")) or date_debut_arret
    if not date_debut_arret:
        return set()
    if not qualification.get("est_maternite") and bareme_des_reglages(settings) is not None:
        # Sous le barème : les jours des paliers de la règle retenue (barème ou légal).
        resultat = calculer_maintien(arret, contexte, settings, date_debut_periode, date_fin_periode)
        jours_bareme: set[int] = set()
        for palier in (resultat.get("maintien") or {}).get("paliers") or []:
            du, au = _parse_date(palier.get("du")), _parse_date(palier.get("au"))
            jour = du
            while du is not None and au is not None and jour <= au:
                jours_bareme.add(jour.day)
                jour += timedelta(days=1)
        return jours_bareme
    arret = _poser_la_chaine(arret, date_debut_arret, date_fin_arret, arret_type)
    jours_deja = _jours_deja_en_arret(arret)

    date_entree = _date_anciennete(contexte) or date(2000, 1, 1)
    anciennete_mois = _mois_anciennete(
        date_entree, _parse_date(arret.get("date_debut_chaine")) or date_debut_arret
    )

    est_at_mp = bool(qualification.get("est_at_mp"))
    min_senior = _min_seniority_months_for_arret(settings, est_at_mp)
    no_seniority = bool(settings.get("no_seniority_condition"))
    if not no_seniority and anciennete_mois < min_senior:
        return set()
    if qualification.get("est_maternite") and not settings.get("maintain_parental_leave"):
        return set()

    inter_d, inter_f = _intersection_dates(
        date_debut_arret, date_fin_arret or date_debut_arret,
        date_debut_periode, date_fin_periode,
    )
    if inter_d is None or inter_f is None:
        return set()

    historique = list(arret.get("historique_arrets_annee") or [])
    carence = _calculer_carence(
        arret, qualification, settings, date_debut_arret, historique
    )
    carence_emp = int(carence.get("carence_employeur_jours") or 0)
    apply_legal = bool(settings.get("apply_legal_maintenance"))
    duree_par_taux = duree_maintien_par_taux(anciennete_mois) if apply_legal else 0
    custom_d = int(settings.get("custom_duration_days") or 0)
    cap_conv = custom_d if custom_d > 0 else (2 * duree_par_taux)
    taux_conv = _taux_conventionnel(settings, est_at_mp)

    jours_intersection = _compter_jours_calendaires(inter_d, inter_f)
    offset = (inter_d - date_debut_arret).days
    jours_maintien: set[int] = set()

    for k in range(jours_intersection):
        jour_cal = inter_d + timedelta(days=k)
        jour_arret = jours_deja + offset + k + 1
        jour_maintien = jour_arret - carence_emp
        if jour_maintien < 1:
            continue
        t_leg = (
            _taux_legal_pour_jour_maintien(jour_maintien, duree_par_taux)
            if apply_legal
            else 0.0
        )
        m_leg = t_leg > 0
        m_conv = (
            taux_conv is not None
            and jour_maintien <= cap_conv
            and float(taux_conv) > 0
        )
        if m_leg or m_conv:
            jours_maintien.add(jour_cal.day)

    return jours_maintien


def calculer_maintien(
    arret: Dict[str, Any],
    contexte: ContextePaie,
    settings: Dict[str, Any],
    date_debut_periode: date,
    date_fin_periode: date,
    *,
    releve_ijss_du_mois: Optional[ReleveIjss] = None,
) -> Dict[str, Any]:
    """
    Calcule qualification, carences, IJSS, maintien employeur et point prévoyance.

    :param arret: clés attendues dont arret_type, date_debut, date_fin,
        subrogation_active, date_dernier_arret, nombre_enfants, is_temps_partiel,
        quotite_temps_partiel, historique_arrets_annee (liste optionnelle),
        salaire_periode_reelle (optionnel), arrets_annee (liste optionnelle des
        arrêts de l'année {debut, fin, type}, pour la carence payée).
    :param releve_ijss_du_mois: plusieurs arrêts dans le mois, réglage de
        déduction allumé et montant validé : (montant validé, IJSS estimées et
        jours indemnisés de tous les arrêts), pour la part de chacun.
    """
    # Réglages société qui s'imposent à chaque arrêt, quelle que soit sa
    # saisie : subrogation « jamais » (IJSS versées au salarié, hors bulletin)
    # et maintien en jours ouvrés (7 h + quote-part d'heures sup structurelles).
    segments = arret.get("arrets_du_mois") or []
    if len(segments) > 1:
        return _calculer_maintien_des_arrets_du_mois(
            arret, segments, contexte, settings, date_debut_periode, date_fin_periode
        )

    if settings.get("subrogation_mode") == "never" and arret.get("subrogation_active"):
        arret = {**arret, "subrogation_active": False}
    if settings.get("maintain_working_days") and not arret.get("maintien_base_ouvree"):
        arret = {**arret, "maintien_base_ouvree": True}

    arret_type = str(arret.get("arret_type") or "maladie_simple")
    qualification = _qualifier_arret(arret_type)

    date_debut_arret = _parse_date(arret.get("date_debut"))
    date_fin_arret = _parse_date(arret.get("date_fin")) or date_debut_arret
    if not date_debut_arret:
        date_debut_arret = date_debut_periode
    # Prolongation d'un arrêt connu : pas de nouvelle carence, rang continué.
    arret = _poser_la_chaine(arret, date_debut_arret, date_fin_arret, arret_type)
    jours_deja = _jours_deja_en_arret(arret)
    debut_chaine = _parse_date(arret.get("date_debut_chaine")) or date_debut_arret

    historique = list(arret.get("historique_arrets_annee") or [])
    carence = _calculer_carence(
        arret, qualification, settings, date_debut_arret, historique
    )
    if jours_deja:
        carence = _carence_d_une_prolongation(carence, jours_deja, debut_chaine)

    ijss_par_jour: Dict[date, float] = {}
    ijss = _calculer_ijss(
        arret,
        qualification,
        carence,
        contexte,
        date_debut_periode,
        date_fin_periode,
        par_jour=ijss_par_jour,
    )

    ijss_override = arret.get("ijss_brut_override")
    if ijss_override is not None:
        try:
            override_val = float(ijss_override)
        except (TypeError, ValueError):
            override_val = None
        if override_val is not None and override_val >= 0:
            ijss = dict(ijss)
            ijss["ijss_theorique"] = round(override_val, 2)
            ijss["ijss_brut_override"] = True

    date_anciennete = _date_anciennete(contexte)
    anciennete_mois = _mois_anciennete(
        date_anciennete or date(2000, 1, 1), debut_chaine
    )

    statut = ""
    try:
        statut = str(contexte.statut_salarie or "")
    except Exception:
        statut = ""
    est_cadre = _statut_est_cadre(statut)

    # Barème de la convention (24/10/2026) : il remplace la carence payée et les
    # réglages manuels de taux, de durée et de carence. Sans barème : le calcul
    # d'avant, inchangé.
    bareme = None if qualification.get("est_maternite") else bareme_des_reglages(settings)
    plan_conv: Optional[PlanConventionnel] = None
    if bareme is not None:
        plan_conv = _plan_au_bareme(
            arret, contexte, bareme, arret_type, date_debut_arret,
            date_fin_arret or date_debut_arret,
        )
        carence = _carence_au_bareme(
            carence, plan_conv, bareme, date_debut_arret, date_fin_arret or date_debut_arret
        )
        jours_carence_payes: frozenset[date] = frozenset()
    else:
        jours_carence_payes = _jours_de_carence_payes_de_l_arret(
            arret,
            settings,
            date_entree=date_anciennete,
            date_debut_arret=date_debut_arret,
            date_fin_arret=date_fin_arret or date_debut_arret,
            arret_type=arret_type,
            est_cadre=est_cadre,
        )
    if jours_carence_payes:
        carence = {
            **carence,
            "carence_payee_jours": len(jours_carence_payes),
            "carence_payee_dates": sorted(d.isoformat() for d in jours_carence_payes),
            "motif_carence": (
                f"{carence.get('motif_carence', '')} Carence payée par l'employeur : "
                f"{len(jours_carence_payes)} jour(s) sur le crédit de l'année."
            ).strip(),
        }

    taux_retenus: Dict[date, float] = {}

    def _maintien_de(arret_calcule: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal taux_retenus
        if plan_conv is not None and bareme is not None:
            resultat, taux_retenus = _calculer_maintien_au_bareme(
                arret_calcule,
                qualification,
                carence,
                ijss,
                contexte,
                settings,
                date_debut_arret,
                anciennete_mois,
                date_debut_periode,
                date_fin_periode,
                plan=plan_conv,
                bareme=bareme,
                ijss_par_jour=ijss_par_jour,
                releve_du_mois=releve_ijss_du_mois,
            )
            return resultat
        return _calculer_maintien_employeur(
            arret_calcule,
            qualification,
            carence,
            ijss,
            contexte,
            settings,
            date_debut_arret,
            anciennete_mois,
            date_debut_periode,
            date_fin_periode,
            jours_carence_payes=jours_carence_payes,
            ijss_par_jour=ijss_par_jour,
            releve_du_mois=releve_ijss_du_mois,
        )

    maintien = _maintien_de(arret)

    # Sans maintien de salaire sur la période, l'employeur n'a rien à avancer
    # pour la caisse : pas de subrogation, les IJSS sont versées directement au
    # salarié et restent hors du bulletin. Colorplast, août 2026 : subrogation
    # réglée « quand il y a maintien », aucun maintien, et pourtant 393,18 €
    # d'IJSS au net et un complément employeur négatif. La maternité garde son
    # régime (maintien à 100 %, calculé à part).
    subrogation_demandee = bool(arret.get("subrogation_active"))
    parentalite_maintenue = bool(qualification.get("est_maternite")) and bool(
        settings.get("maintain_parental_leave")
    )
    if (
        subrogation_demandee
        and not parentalite_maintenue
        and float(maintien.get("maintien_cible") or 0.0) <= 0.0
    ):
        arret = {**arret, "subrogation_active": False}
        maintien = _maintien_de(arret)

    nb_jours_arret_total = jours_deja + _compter_jours_calendaires(
        date_debut_arret, date_fin_arret or date_debut_arret
    )

    prevoyance = _calculer_prevoyance_complement(
        arret,
        qualification,
        settings,
        est_cadre=est_cadre,
        anciennete_mois=anciennete_mois,
        brut_journalier=(
            float(contexte.salaire_base_mensuel or 0.0) / lc.DIVISEUR_JOURS_CALENDAIRES
            if contexte.salaire_base_mensuel
            else 0.0
        ),
        base_plafonnee=float(ijss.get("base_plafonnee") or 0.0),
        ij_plafonds=plafonds_ij_au(
            (
                contexte.get_bareme_value("ij_plafonds")
                if hasattr(contexte, "get_bareme_value")
                else contexte.baremes.get("ij_plafonds")
            ),
            date_de_reference_des_plafonds(
                arret, bool(qualification.get("est_at_mp")), date_debut_arret
            ),
        ),
        carence_ss=int(carence.get("carence_ss_jours") or 0),
        carence_emp=int(
            carence.get("carence_employeur_jours_arret")
            if carence.get("carence_employeur_jours_arret") is not None
            else maintien.get("carence_employeur_jours") or 0
        ),
        duree_par_taux=int(maintien.get("duree_par_taux_jours") or 0),
        cap_conv=(
            int(settings.get("custom_duration_days") or 0)
            or int(maintien.get("duree_maintien_legale_jours") or 0)
        ),
        taux_conv=_taux_conventionnel(settings, bool(qualification.get("est_at_mp"))),
        apply_legal=bool(settings.get("apply_legal_maintenance")),
        nb_jours_arret_total=nb_jours_arret_total,
        date_debut_arret=date_debut_arret,
        date_fin_arret=date_fin_arret or date_debut_arret,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
        jours_deja_en_arret=jours_deja,
        taux_maintien_par_jour=taux_retenus if plan_conv is not None else None,
    )

    alertes: List[str] = []
    if plan_conv is not None and bareme is not None:
        alertes.extend(
            alertes_du_bareme(
                bareme,
                maintien,
                plan_conv,
                date_debut_arret,
                date_fin_arret or date_debut_arret,
                statut=statut,
                debut_periode=date_debut_periode,
                fin_periode=date_fin_periode,
            )
        )
    else:
        if not maintien.get("maintien_applicable", True):
            alertes.append(
                MOTIF_PARENTALITE_SANS_MAINTIEN
                if maintien.get("est_maternite")
                else "Ancienneté insuffisante pour le maintien légal"
            )
        duree_legale = int(maintien.get("duree_maintien_legale_jours") or 0)
        if duree_legale and nb_jours_arret_total > duree_legale:
            alertes.append(
                f"Durée maximale du maintien employeur atteinte ({duree_legale} jours "
                f"selon l'ancienneté). Vérifier l'activation de la prévoyance relais."
            )
    if maintien.get("conflit_convention"):
        alertes.append(
            "Règle conventionnelle moins favorable que la règle légale — application de la règle légale"
        )
    if not arret.get("subrogation_active"):
        alertes.append(alerte_ijss_au_salarie(maintien))
    elif not maintien.get("maintien_applicable", True) and arret.get("subrogation_active"):
        alertes.append(
            "Subrogation demandée sans maintien applicable — vérifier la cohérence"
        )
    if subrogation_demandee and float(ijss.get("ijss_theorique") or 0) == 0:
        sjb = float(ijss.get("salaire_journalier_base") or 0)
        bp = float(ijss.get("base_plafonnee") or 0)
        if sjb <= 0:
            alertes.append(
                "IJSS non calculables : salaire de base absent ou à 0 € "
                "(renseignez la fiche salarié ou le paramètre what-if « Salaire brut mensuel »)"
            )
        elif bp <= 0:
            alertes.append(
                "IJSS non calculables : plafond SS (PSS) indisponible "
                "(vérifiez la configuration paie / barèmes actifs)"
            )
        else:
            alertes.append(
                "IJSS non calculables, vérifier le salaire journalier de base"
            )
    if prevoyance.get("montant", 0) > 0:
        alertes.append(
            f"Complément prévoyance estimé : {prevoyance['montant']:.2f} € "
            f"(garantie {int(round((prevoyance.get('taux_cible') or 0) * 100))} % "
            f"du brut, versé par l'organisme assureur)"
        )
    elif prevoyance.get("prevoyance_declenchee"):
        alertes.append("Prévoyance relais à déclencher")

    if qualification.get("est_ald"):
        alertes.append(
            "ALD : prolongation IJSS possible sans nouvelle carence en cas de rechute"
        )

    result: Dict[str, Any] = {
        "qualification": qualification,
        "carence": carence,
        "ijss": ijss,
        "maintien": maintien,
        "prevoyance": prevoyance,
        "alertes": alertes,
        "subrogation_active": bool(arret.get("subrogation_active")),
        "maintien_base_ouvree": bool(arret.get("maintien_base_ouvree")),
        "type_arret": arret_type,
        "nb_jours_arret_total": nb_jours_arret_total,
        "anciennete_mois": anciennete_mois,
        "statut": statut,
        "est_cadre": est_cadre,
    }

    if ijss.get("is_mi_temps_therapeutique"):
        spm = float(ijss.get("salaire_partiel_maintenu") or 0.0)
        result["double_ligne_bulletin"] = True
        result["salaire_partiel_maintenu"] = round(spm, 2)
        alertes.append(
            "Mi-temps thérapeutique : double ligne bulletin (IJSS + salaire partiel maintenu)"
        )
        result["alertes"] = alertes

    return result


def calculer_regularisation_at(
    arret_original: Dict[str, Any],
    contexte: ContextePaie,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare le maintien / IJSS en maladie simple vs accident du travail (même période).
    Utilisé après requalification AT pour estimer le delta bulletin.
    """
    date_debut = _parse_date(arret_original.get("date_debut"))
    date_fin = _parse_date(arret_original.get("date_fin"))
    if not date_debut or not date_fin:
        raise ValueError("Dates d'arrêt invalides pour la régularisation AT.")

    arret_ms = {**arret_original, "arret_type": "maladie_simple"}
    arret_at = {**arret_original, "arret_type": "accident_travail"}

    res_ms = calculer_maintien(arret_ms, contexte, settings, date_debut, date_fin)
    res_at = calculer_maintien(arret_at, contexte, settings, date_debut, date_fin)

    ij_ms = float(res_ms["ijss"]["ijss_theorique"])
    ij_at = float(res_at["ijss"]["ijss_theorique"])
    m_ms = float(res_ms["maintien"]["maintien_verse"])
    m_at = float(res_at["maintien"]["maintien_verse"])

    return {
        "type": "regularisation_at",
        "delta_ijss": round(ij_at - ij_ms, 2),
        "delta_maintien_verse": round(m_at - m_ms, 2),
        "nouveau_calcul": res_at,
        "ancien_calcul": res_ms,
        "alerte": (
            "Requalification AT : régularisation rétroactive "
            "à appliquer sur le bulletin du mois en cours"
        ),
    }
