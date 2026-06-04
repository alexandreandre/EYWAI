"""
Moteur de calcul du maintien de salaire (service pur, sans FastAPI ni Supabase).

Appelé depuis le générateur de bulletins avec données déjà chargées (Ticket 3).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .contexte import ContextePaie
from . import legal_constants as lc

# --- Dates & utilitaires ---


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value[:10])
    return None


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
    elif t in ("maternite", "paternite", "maternite_paternite"):
        key = "maternite_paternite"
    else:
        key = "maladie"
    val = ij_plafonds.get(key)
    if isinstance(val, (int, float)) and val > 0:
        return float(val)
    return None


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

    if t in types_at_mp:
        carence_ss_jours = 0
        taux_ijss_base = lc.TAUX_IJSS_AT_MP_J1_28
        est_at_mp = True
    elif t in types_3j_ss:
        carence_ss_jours = 3
        taux_ijss_base = lc.TAUX_IJSS_MALADIE
        est_at_mp = False
    else:
        carence_ss_jours = 3
        taux_ijss_base = lc.TAUX_IJSS_MALADIE
        est_at_mp = False

    est_ald = t == "ald"

    return {
        "carence_ss_jours": carence_ss_jours,
        "taux_ijss_base": taux_ijss_base,
        "est_at_mp": t in types_at_mp,
        "est_ald": est_ald,
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

    if settings.get("remove_employer_waiting"):
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
    jour_index_1based: int,
    nombre_enfants: int,
) -> float:
    """jour_index_1based : 1 = premier jour indemnisable de l'arrêt."""
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
            if jour_index_1based >= 29
            else lc.TAUX_IJSS_AT_MP_J1_28
        )
    if t in ("maladie_simple", "ald", "arret_exceptionnel"):
        if nombre_enfants >= 3:
            return lc.TAUX_IJSS_MALADIE_3_ENFANTS
        return lc.TAUX_IJSS_MALADIE
    if t == "mi_temps_therapeutique":
        return lc.TAUX_IJSS_MI_TEMPS
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


def _calculer_ijss(
    arret: Dict[str, Any],
    qualification: Dict[str, Any],
    carence: Dict[str, Any],
    contexte: ContextePaie,
    date_debut_periode: date,
    date_fin_periode: date,
) -> Dict[str, Any]:
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

    salaire_mensuel = float(contexte.salaire_base_mensuel or 0.0)
    salaire_journalier_base = (
        salaire_mensuel / lc.DIVISEUR_JOURS_CALENDAIRES if salaire_mensuel else 0.0
    )

    pss_data = contexte.get_bareme_value("pss") if hasattr(contexte, "get_bareme_value") else contexte.baremes.get("pss")
    pss_annuel = _extraire_pss_annuel(pss_data)
    if pss_annuel is None:
        plafond_ss_journalier = 0.0
        base_plafonnee = 0.0
    else:
        plafond_ss_journalier = pss_annuel / 365.0
        base_plafonnee = min(
            salaire_journalier_base,
            plafond_ss_journalier * lc.COEFF_PLAFOND_IJ_PSS,
        )

    ij_plafonds = (
        contexte.get_bareme_value("ij_plafonds")
        if hasattr(contexte, "get_bareme_value")
        else contexte.baremes.get("ij_plafonds")
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
                jour_arret_1based = offset - carence_ss + 1
                taux_j = _taux_ijss_pour_jour_arret(
                    arret_type, jour_arret_1based, nombre_enfants
                )
                ijss_j = base_plafonnee * taux_j
                plafond_j = plafond_ij_pour(
                    arret_type, jour_arret_1based, ij_plafonds
                )
                if plafond_j is not None:
                    ijss_j = min(ijss_j, plafond_j)
                if is_tp:
                    ijss_j *= quotite
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


def _taux_legal_pour_jour_maintien(
    jour_index_1based: int,
    extension_extra_days: int,
) -> float:
    """
    jour_index_1based : jour depuis le début de l'arrêt (calendaire) pour le maintien légal.
    Tranches : 1-30 → 90 %, 31-60 → 66,66 %, puis extension à 90 % si droit ouvert.
    """
    ext = max(0, extension_extra_days)
    limite_avec_extension = min(90, 60 + ext)
    if jour_index_1based > limite_avec_extension:
        return 0.0
    if jour_index_1based <= 30:
        return lc.TRANCHE_MAINTIEN_90
    if jour_index_1based <= 60:
        return lc.TRANCHE_MAINTIEN_66
    if ext > 0:
        return lc.TRANCHE_MAINTIEN_90
    return 0.0


def _extension_jours_seniorite(
    anciennete_mois: int, min_seniority_months: int, enabled: bool
) -> int:
    if not enabled or anciennete_mois < min_seniority_months:
        return 0
    mois_au_dela = anciennete_mois - min_seniority_months
    annees_5 = mois_au_dela // 60
    return min(30, annees_5 * 10)


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
) -> Dict[str, Any]:
    motif_non_maintien: Optional[str] = None
    conflit_convention = False

    min_senior = int(settings.get("min_seniority_months") or 0)
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
    brut_journalier = (
        salaire_mensuel / lc.DIVISEUR_JOURS_CALENDAIRES if salaire_mensuel else 0.0
    )

    extension = 0
    if settings.get("apply_legal_maintenance"):
        extension = _extension_jours_seniorite(
            anciennete_mois, min_senior, bool(settings.get("seniority_extension_enabled"))
        )

    jours_intersection = _compter_jours_calendaires(inter_d, inter_f)
    cap_absolu = 90
    custom_d = int(settings.get("custom_duration_days") or 0)
    if custom_d > 0:
        cap_absolu = min(cap_absolu, custom_d)
    nb_jours_maintien = min(jours_intersection, cap_absolu)

    est_at_mp = bool(qualification.get("est_at_mp"))
    taux_conv = None
    if settings.get("maintain_100_percent"):
        taux_conv = 1.0
    elif settings.get("differentiated_at_illness") and est_at_mp:
        taux_conv = 1.0
    # maintain_by_category : V1 ignoré

    explicite = settings.get("taux_maintien_conventionnel")
    if isinstance(explicite, (int, float)):
        taux_conv = float(explicite)

    maintien_total_legal = 0.0
    offset = (inter_d - date_debut_arret).days
    for k in range(nb_jours_maintien):
        jour_idx = offset + k + 1
        if settings.get("apply_legal_maintenance"):
            t_leg = _taux_legal_pour_jour_maintien(jour_idx, extension)
        else:
            t_leg = 0.0
        maintien_total_legal += brut_journalier * t_leg

    if taux_conv is not None:
        maintien_total_conv = nb_jours_maintien * brut_journalier * float(taux_conv)
    else:
        maintien_total_conv = maintien_total_legal

    if taux_conv is not None and settings.get("apply_legal_maintenance"):
        if maintien_total_conv < maintien_total_legal - 1e-6:
            conflit_convention = True
            maintien_cible = maintien_total_legal
        else:
            maintien_cible = max(maintien_total_legal, maintien_total_conv)
    elif taux_conv is not None:
        maintien_cible = maintien_total_conv
    else:
        maintien_cible = maintien_total_legal

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

    subrogation_active = bool(arret.get("subrogation_active"))
    if subrogation_active:
        maintien_verse = maintien_cible - float(ijss.get("ijss_theorique") or 0.0)
    else:
        maintien_verse = maintien_cible

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
    }


# --- Bloc 5 : prévoyance ---


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


# --- Point d'entrée ---


def calculer_maintien(
    arret: Dict[str, Any],
    contexte: ContextePaie,
    settings: Dict[str, Any],
    date_debut_periode: date,
    date_fin_periode: date,
) -> Dict[str, Any]:
    """
    Calcule qualification, carences, IJSS, maintien employeur et point prévoyance.

    :param arret: clés attendues dont arret_type, date_debut, date_fin,
        subrogation_active, date_dernier_arret, nombre_enfants, is_temps_partiel,
        quotite_temps_partiel, historique_arrets_annee (liste optionnelle),
        salaire_periode_reelle (optionnel).
    """
    arret_type = str(arret.get("arret_type") or "maladie_simple")
    qualification = _qualifier_arret(arret_type)

    date_debut_arret = _parse_date(arret.get("date_debut"))
    date_fin_arret = _parse_date(arret.get("date_fin")) or date_debut_arret
    if not date_debut_arret:
        date_debut_arret = date_debut_periode

    historique = list(arret.get("historique_arrets_annee") or [])
    carence = _calculer_carence(
        arret, qualification, settings, date_debut_arret, historique
    )

    ijss = _calculer_ijss(
        arret,
        qualification,
        carence,
        contexte,
        date_debut_periode,
        date_fin_periode,
    )

    date_entree_raw = (
        (contexte.contrat or {})
        .get("contrat", {})
        .get("date_entree")
    )
    date_entree = _parse_date(date_entree_raw) or date(
        2000, 1, 1
    )
    anciennete_mois = _mois_anciennete(date_entree, date_debut_arret)

    maintien = _calculer_maintien_employeur(
        arret,
        qualification,
        carence,
        ijss,
        contexte,
        settings,
        date_debut_arret,
        anciennete_mois,
        date_debut_periode,
        date_fin_periode,
    )

    nb_jours_arret_total = _compter_jours_calendaires(
        date_debut_arret, date_fin_arret or date_debut_arret
    )
    prevoyance = _verifier_prevoyance_relais(nb_jours_arret_total, settings)

    alertes: List[str] = []
    if not maintien.get("maintien_applicable", True):
        alertes.append(
            "Ancienneté insuffisante pour le maintien légal"
        )
    if maintien.get("nb_jours_maintien", 0) >= 90:
        alertes.append(
            "Plafond maintien 90 jours atteint. Vérifier l'activation de la prévoyance relais."
        )
    if maintien.get("conflit_convention"):
        alertes.append(
            "Règle conventionnelle moins favorable que la règle légale — application de la règle légale"
        )
    if not arret.get("subrogation_active"):
        alertes.append("IJSS versées directement au salarié")
    if arret.get("subrogation_active") and float(ijss.get("ijss_theorique") or 0) == 0:
        alertes.append(
            "IJSS non calculables, vérifier le salaire journalier de base"
        )
    if prevoyance.get("prevoyance_declenchee"):
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
        "type_arret": arret_type,
        "nb_jours_arret_total": nb_jours_arret_total,
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
