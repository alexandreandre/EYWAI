# moteur_paie/calcul_brut.py

from .contexte import ContextePaie
from . import legal_constants as lc
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from .calcul_conges import calculer_indemnite_conges
from .iccp_fin_cdd import (
    METHODE_SALAIRE_RETABLI,
    assiette_salaire_retabli,
    salaire_retabli_du_mois,
    valeur_jour_maintien,
)
from .iccp_fin_cdd import methode_depuis_parametres as methode_iccp_fin_cdd
from .indemnites_sortie_brut import lignes_indemnites_sortie_soumises
from .salary_evolution_brut import (
    lignes_rappel_salaire,
    salaire_contractuel_avec_evolution,
)
from .salaire_contractuel import (
    heures_mensuelles_legales,
    heures_sup_structurelles_mensuelles as compute_hs_structurelles_mensuelles,
    salaire_hors_hs_structurelles,
    taux_horaire_base_hors_hs_structurelles,
)


def _heures_journalieres_contrat(duree_hebdo: float) -> float:
    """Durée journalière de référence (lun–ven) pour un jour d'absence isolé.

    Basée sur la durée légale (35 h) et non la durée contractuelle : une journée
    d'arrêt maladie/férié non payé se valorise sur la référence légale pour les
    salariés à temps plein (au-delà de 35 h, les heures sont structurelles et
    n'ont pas à être perdues sur une simple journée d'absence) ; en deçà (temps
    partiel), on garde le prorata contractuel.
    """
    if duree_hebdo and duree_hebdo > 0:
        return min(duree_hebdo, lc.DUREE_LEGALE_HEBDO) / 5.0
    return 7.0


#: Libellé de la ligne de retenue, par nature d'arrêt de travail.
LIBELLES_ARRET: Dict[str, str] = {
    "arret_maladie": "arrêt maladie",
    "arret_at": "accident du travail",
    "arret_maternite": "congé maternité",
    "arret_paternite": "congé paternité",
}


def _heures_evenement_absence(evenement: Dict[str, Any], duree_hebdo: float) -> float:
    """Heures imputées sur une absence (impute la journée si heures absentes/nulles)."""
    heures = evenement.get("heures")
    if heures is None or heures == 0:
        return _heures_journalieres_contrat(duree_hebdo)
    return float(heures)


def _repartir_absence_au_prorata_du_contrat(
    heures: float, duree_hebdo: float
) -> tuple[float, float]:
    """Heures d'absence d'un contrat > 35 h : (part au taux de base, part HS).

    Chaque heure planifiée absente est retirée 35/39 au taux de base et 4/39
    sur les heures sup structurelles mensualisées — la règle du cabinet
    (Quadra) : 8,5 h → 7,63 + 0,87 ; 7,8 h → 7,00 + 0,80 ; 0,25 h → 0,22 +
    0,03. La part de base est arrondie au centième, le reste va aux HS pour
    que les deux parts fassent exactement les heures absentes.
    """
    part_base = round(heures * lc.DUREE_LEGALE_HEBDO / duree_hebdo, 2)
    part_hs = round(heures - part_base, 2)
    return part_base, max(part_hs, 0.0)


def _jours_evenement_conges(evenement: Dict[str, Any]) -> float:
    """Quotité de jour consommée par un événement conges_payes.

    0.5 = demi-journée (clé `quotite_absence` posée par la validation
    d'absence) ; absente ou invalide = jour plein. Plafonnée à 1 : jamais
    plus d'un jour de CP par jour calendaire (miroir du plafond forfait,
    cf. calcul_brut_forfait._jours_evenement_absence).
    """
    try:
        quotite = float(evenement.get("quotite_absence") or 1.0)
    except (TypeError, ValueError):
        quotite = 1.0
    if quotite <= 0:
        return 1.0
    return min(quotite, 1.0)


def _libelle_dates_conges(evenements: List[Dict[str, Any]]) -> str:
    """« 13/07, 15/07→17/07, 21/07 (½) » — plages de jours pleins consécutifs
    compressées, demi-journées marquées. Chaîne vide si aucune date lisible."""
    jours: List[tuple] = []
    for ev in evenements:
        try:
            d = date.fromisoformat(ev["date_complete"])
        except (KeyError, TypeError, ValueError):
            continue
        jours.append((d, 0.0 < _jours_evenement_conges(ev) < 1.0))
    if not jours:
        return ""
    jours.sort()
    segments: List[str] = []
    debut, fin = None, None

    def _flush():
        if debut is None:
            return
        if debut == fin:
            segments.append(debut.strftime("%d/%m"))
        else:
            segments.append(f"{debut.strftime('%d/%m')}→{fin.strftime('%d/%m')}")

    for d, est_demi in jours:
        if est_demi:
            _flush()
            debut, fin = None, None
            segments.append(f"{d.strftime('%d/%m')} (½)")
            continue
        if fin is not None and (d - fin).days == 1:
            fin = d
            continue
        _flush()
        debut, fin = d, d
    _flush()
    libelle = ", ".join(segments)
    if len(libelle) > 70 and len(jours) > 1:
        return f"du {jours[0][0].strftime('%d/%m')} au {jours[-1][0].strftime('%d/%m')}"
    return libelle


def _format_jours_conges(nombre: float) -> str:
    """« 1 jour », « 5 jours », « 0,5 jour », « 2,5 jours » (libellé bulletin)."""
    if nombre == int(nombre):
        n = int(nombre)
        return f"{n} jour" + ("s" if n > 1 else "")
    label = f"{nombre:.1f}".replace(".", ",")
    return f"{label} jour" + ("s" if nombre > 1 else "")


def _parse_date_contrat(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _facteur_prorata_entree_sortie(
    contexte: ContextePaie,
    date_debut_periode: date,
    date_fin_periode: date,
) -> float:
    """Prorata entrée/sortie selon les jours ouvrés réellement sous contrat."""
    contrat = contexte.contrat.get("contrat", {}) or {}
    date_entree = _parse_date_contrat(contrat.get("date_entree"))
    date_sortie = _parse_date_contrat(
        contrat.get("date_sortie") or contrat.get("date_fin_contrat")
    )

    debut_effectif = (
        max(date_debut_periode, date_entree) if date_entree else date_debut_periode
    )
    fin_effective = (
        min(date_fin_periode, date_sortie) if date_sortie else date_fin_periode
    )

    if fin_effective < debut_effectif:
        return 0.0

    jours_ouvres_mois = sum(
        1
        for offset in range((date_fin_periode - date_debut_periode).days + 1)
        if (date_debut_periode + timedelta(days=offset)).weekday() < 5
    )
    jours_presence = sum(
        1
        for offset in range((fin_effective - debut_effectif).days + 1)
        if (debut_effectif + timedelta(days=offset)).weekday() < 5
    )
    if jours_ouvres_mois <= 0:
        return 1.0
    return jours_presence / jours_ouvres_mois


def _jour_ferie_est_paye(contexte: ContextePaie, evenement: Dict[str, Any]) -> bool:
    """Jour férié chômé payé, sous condition légale d'ancienneté (art. L3133-3 C. trav.).

    Le maintien de salaire d'un jour férié chômé (hors 1er mai) suppose au moins
    3 mois d'ancienneté dans l'entreprise — c'est le défaut légal appliqué ici.
    Une CCN/usage plus favorable peut abaisser le seuil (0 = payé dès l'embauche)
    via specificites_paie.jours_feries_anciennete_min_mois. L'ancienneté retenue
    tient compte d'une reprise éventuelle (seniority_reference_date / DSN).
    """
    spec = contexte.contrat.get("specificites_paie", {}) or {}
    seuil_raw = spec.get("jours_feries_anciennete_min_mois")
    if seuil_raw is None:
        seuil_mois = 3.0  # défaut légal L3133-3
    else:
        try:
            seuil_mois = float(seuil_raw)
        except (TypeError, ValueError):
            seuil_mois = 3.0
    if seuil_mois <= 0:
        return True

    date_ferie = _parse_date_contrat(evenement.get("date_complete"))
    if not date_ferie:
        return True

    # 1er mai : chômé et payé sans condition d'ancienneté (art. L3133-4/5 C. trav.).
    if date_ferie.month == 5 and date_ferie.day == 1:
        return True

    # Journée de solidarité : jour férié travaillé/neutre par convention, sans effet
    # de paie ; date paramétrée par l'entreprise (parametres_paie.jour_solidarite).
    # À défaut d'accord (art. L3133-11), c'est le lundi de Pentecôte.
    jour_solidarite = (contexte.entreprise.get("parametres_paie", {}) or {}).get(
        "jour_solidarite"
    )
    date_solidarite = _parse_date_contrat(jour_solidarite) if jour_solidarite else None
    if date_solidarite is None:
        from app.modules.absences.domain.rtt_forfait import _easter_sunday

        date_solidarite = _easter_sunday(date_ferie.year) + timedelta(days=50)
    if date_solidarite == date_ferie:
        return True

    # Ancienneté = date la plus favorable (embauche ou reprise d'ancienneté).
    from app.shared.seniority_reference import resolve_date_anciennete_from_contrat

    contrat_block = contexte.contrat.get("contrat", {}) or {}
    ancres = [
        _parse_date_contrat(contrat_block.get("date_entree")),
        _parse_date_contrat(resolve_date_anciennete_from_contrat(contexte.contrat)),
    ]
    ancres = [d for d in ancres if d]
    if not ancres:
        return True
    date_ref = min(ancres)

    mois_anciennete = (date_ferie.year - date_ref.year) * 12 + (
        date_ferie.month - date_ref.month
    )
    if date_ferie.day < date_ref.day:
        mois_anciennete -= 1

    # Reprise d'ancienneté : mois de service antérieurs (contrat précédent,
    # groupe...) comptés dans l'ancienneté entreprise au sens de L3133-3.
    prior = contrat_block.get("prior_service_months")
    try:
        mois_anciennete += int(prior) if prior else 0
    except (TypeError, ValueError):
        pass

    return mois_anciennete >= seuil_mois


def _calculer_prime_precarite_cdd(
    contexte: ContextePaie,
    salaire_brut_hors_precarite: float,
    date_debut_periode: date,
    date_fin_periode: date,
) -> Dict[str, Any] | None:
    """Prime de précarité CDD (dernier mois), taux depuis payroll_config.cdd."""
    if not contexte.is_cdd or not contexte.est_dernier_mois_cdd(
        date_debut_periode, date_fin_periode
    ):
        return None

    spec = contexte.contrat.get("specificites_paie", {}) or {}
    if spec.get("exclure_prime_precarite") or spec.get("cdd_sans_precarite"):
        return None

    cfg = (contexte.baremes.get("cdd", {}) or {}).get("precarite", {}) or {}
    if cfg.get("actif") is False:
        return None
    taux = float(cfg.get("taux", 0.10))

    cumuls = (
        contexte.cumuls.get("cumuls", {})
        if isinstance(contexte.cumuls, dict)
        else {}
    )
    brut_cumule_contrat = float(cumuls.get("brut_total", 0.0)) + salaire_brut_hors_precarite
    montant = round(brut_cumule_contrat * taux, 2)
    if montant <= 0:
        return None

    return {
        "libelle": "Prime de précarité (CDD)",
        "quantite": None,
        "taux": taux,
        "gain": montant,
        "perte": None,
    }


def _calculer_ifm_interim(
    contexte: ContextePaie,
    salaire_brut_hors_indemnites: float,
    date_debut_periode: date,
    date_fin_periode: date,
) -> Dict[str, Any] | None:
    """Indemnité de fin de mission (intérim), dernier mois de mission.

    Base légale : 10 % de la rémunération brute totale de la mission. Taux dans
    payroll_config.interim.ifm (défaut 0,10). Désactivable par flag
    specificites_paie.exclure_ifm.
    """
    if not contexte.is_interim or not contexte.est_dernier_mois_mission(
        date_debut_periode, date_fin_periode
    ):
        return None

    spec = contexte.contrat.get("specificites_paie", {}) or {}
    if spec.get("exclure_ifm"):
        return None

    cfg = (contexte.baremes.get("interim", {}) or {}).get("ifm", {}) or {}
    if cfg.get("actif") is False:
        return None
    taux = float(cfg.get("taux", 0.10))

    cumuls = (
        contexte.cumuls.get("cumuls", {})
        if isinstance(contexte.cumuls, dict)
        else {}
    )
    base = float(cumuls.get("brut_total", 0.0)) + salaire_brut_hors_indemnites
    montant = round(base * taux, 2)
    if montant <= 0:
        return None

    return {
        "libelle": "Indemnité de fin de mission (intérim)",
        "quantite": None,
        "taux": taux,
        "gain": montant,
        "perte": None,
    }


def _sous_total_contractuel_du_mois(lignes: List[Dict[str, Any]] | None) -> float:
    """La part contractuelle réellement payée ce mois : la ligne de sous-total,
    sinon la ligne de salaire de base (contrat sans HS structurelles)."""
    for ligne in lignes or []:
        if ligne.get("is_sous_total") and "CONTRACTUEL" in str(ligne.get("libelle", "")).upper():
            return float(ligne.get("gain") or 0.0)
    for ligne in lignes or []:
        if str(ligne.get("libelle", "")).lower().startswith("salaire de base"):
            return float(ligne.get("gain") or 0.0)
    return 0.0


def _calculer_iccp_cdd(
    contexte: ContextePaie,
    salaire_brut_hors_precarite: float,
    montant_precarite: float,
    date_debut_periode: date,
    date_fin_periode: date,
    *,
    lignes_brut: List[Dict[str, Any]] | None = None,
    taux_horaire_base: float | None = None,
    majoration_hs25: float | None = None,
) -> Dict[str, Any] | None:
    """Indemnité compensatrice de congés payés (dernier mois), méthode du 1/10e.

    Applicable au CDD et à la mission d'intérim. Base légale : 1/10 de la
    rémunération brute totale du contrat, prime de précarité / IFM comprise.
    Taux dans payroll_config.cdd.indemnite_conges (ou interim.indemnite_conges),
    défaut 0,10. Désactivable par flag specificites_paie.cdd_sans_iccp.

    Méthode société « salaire rétabli du mois de sortie, congés N-1 inclus »
    (`entreprise.parametres_paie.indemnite_cp_fin_cdd`, CDD seulement) : le
    sous-total contractuel du dernier mois est remplacé par celui du mois
    plein et le solde de congés N-1 (`contexte.solde_cp_n_1_fin_de_mois`) est
    valorisé au maintien — cf. engine/iccp_fin_cdd. Le détail est déposé sur
    `contexte.detail_iccp_fin_cdd` pour la mention du bulletin.
    """
    is_cdd_fin = contexte.is_cdd and contexte.est_dernier_mois_cdd(
        date_debut_periode, date_fin_periode
    )
    is_interim_fin = contexte.is_interim and contexte.est_dernier_mois_mission(
        date_debut_periode, date_fin_periode
    )
    if not (is_cdd_fin or is_interim_fin):
        return None

    # Un dossier de départ ne prime que s'il porte lui-même une ICCP : ses
    # autres indemnités (préavis, licenciement…) n'ont pas à faire taire
    # celle du contrat (fin de CDD, cf. `ecarter_iccp_du_dossier_pour_fin_cdd`).
    dossier = getattr(contexte, "exit_indemnities", None) or {}
    if float((dossier.get("indemnite_conges") or {}).get("montant") or 0) > 0:
        return None

    if getattr(contexte, "block_iccp_cdd", False):
        return None

    spec = contexte.contrat.get("specificites_paie", {}) or {}
    if spec.get("cdd_sans_iccp") or spec.get("exclure_iccp"):
        return None

    cle_regime = "interim" if is_interim_fin else "cdd"
    cfg = (contexte.baremes.get(cle_regime, {}) or {}).get(
        "indemnite_conges", {}
    ) or {}
    if cfg.get("actif") is False:
        return None
    taux = float(cfg.get("taux", 0.10))

    cumuls = (
        contexte.cumuls.get("cumuls", {})
        if isinstance(contexte.cumuls, dict)
        else {}
    )
    cumul_brut_contrat = float(cumuls.get("brut_total", 0.0))
    base = cumul_brut_contrat + salaire_brut_hors_precarite + max(montant_precarite, 0.0)
    assiette_retablie = None
    if (
        is_cdd_fin
        and methode_iccp_fin_cdd(contexte.entreprise) == METHODE_SALAIRE_RETABLI
        and taux_horaire_base
    ):
        majoration = float(majoration_hs25 or 0.0)
        assiette_retablie = assiette_salaire_retabli(
            cumul_brut_contrat=cumul_brut_contrat,
            brut_du_mois=salaire_brut_hors_precarite,
            sous_total_contractuel_reel=_sous_total_contractuel_du_mois(lignes_brut),
            salaire_retabli=salaire_retabli_du_mois(
                taux_horaire_base, contexte.duree_hebdo_contrat, majoration
            ),
            precarite=montant_precarite,
            solde_n1_jours=float(getattr(contexte, "solde_cp_n_1_fin_de_mois", 0.0) or 0.0),
            valeur_jour=valeur_jour_maintien(
                taux_horaire_base, contexte.duree_hebdo_contrat, majoration
            ),
        )
        base = assiette_retablie.total
    montant = round(base * taux, 2)
    if montant <= 0:
        return None
    if assiette_retablie is not None:
        contexte.detail_iccp_fin_cdd = assiette_retablie.resume(taux=taux, montant=montant)

    libelle_iccp = (
        "Indemnité compensatrice de congés payés (intérim)"
        if is_interim_fin
        else "Indemnité compensatrice de congés payés (CDD)"
    )
    return {
        "libelle": libelle_iccp,
        "quantite": None,
        "taux": taux,
        "gain": montant,
        "perte": None,
    }


def _taux_majoration_hs(contexte: ContextePaie, index: int = 0) -> Optional[float]:
    """Lit le taux de majoration HS depuis heures_supp (None si absent)."""
    if hasattr(contexte, "get_bareme_value"):
        val = contexte.get_bareme_value(
            "heures_supp",
            "regles_calcul_communes",
            "taux_majoration_par_defaut",
            "heures_supplementaires",
            index,
            "taux",
        )
    else:
        hs_list = (
            (getattr(contexte, "baremes", {}) or {})
            .get("heures_supp", {})
            .get("regles_calcul_communes", {})
            .get("taux_majoration_par_defaut", {})
            .get("heures_supplementaires", [])
        )
        val = None
        if isinstance(hs_list, list) and len(hs_list) > index:
            val = hs_list[index].get("taux")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _taux_majoration_hc(contexte: ContextePaie, index: int = 0) -> Optional[float]:
    """Lit le taux de majoration des heures complémentaires (temps partiel).

    Source : heures_supp.regles_calcul_communes.taux_majoration_par_defaut
    .heures_complementaires[index].taux (None si absent).
    """
    if hasattr(contexte, "get_bareme_value"):
        val = contexte.get_bareme_value(
            "heures_supp",
            "regles_calcul_communes",
            "taux_majoration_par_defaut",
            "heures_complementaires",
            index,
            "taux",
        )
    else:
        hc_list = (
            (getattr(contexte, "baremes", {}) or {})
            .get("heures_supp", {})
            .get("regles_calcul_communes", {})
            .get("taux_majoration_par_defaut", {})
            .get("heures_complementaires", [])
        )
        val = None
        if isinstance(hc_list, list) and len(hc_list) > index:
            val = hc_list[index].get("taux")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _get_salaire_horaire_base(
    contexte: ContextePaie, duree_hebdo_reelle: float
) -> float:
    salaire_mensuel = contexte.salaire_base_mensuel
    duree_legale_hebdo = lc.DUREE_LEGALE_HEBDO
    if (
        salaire_hors_hs_structurelles(contexte.contrat)
        and duree_hebdo_reelle > duree_legale_hebdo
    ):
        return taux_horaire_base_hors_hs_structurelles(salaire_mensuel)
    if duree_hebdo_reelle <= duree_legale_hebdo:
        heures_mensuelles = round((duree_hebdo_reelle * 52) / 12, 2)
        return salaire_mensuel / heures_mensuelles if heures_mensuelles > 0 else 0.0
    heures_mensuelles_legales = round((duree_legale_hebdo * 52) / 12, 2)
    heures_sup_structurelles_mensuelles = round(
        ((duree_hebdo_reelle - duree_legale_hebdo) * 52) / 12, 2
    )
    majoration_hs = _taux_majoration_hs(contexte, 0)
    if majoration_hs is None:
        majoration_hs = 0.0
    heures_equivalentes_majorees = heures_mensuelles_legales + (
        heures_sup_structurelles_mensuelles * (1 + majoration_hs)
    )
    return (
        salaire_mensuel / heures_equivalentes_majorees
        if heures_equivalentes_majorees > 0
        else 0.0
    )


def _construire_ligne_avantages_en_nature(
    contexte: ContextePaie,
) -> Dict[str, Any] | None:
    # Cette fonction reste inchangée
    total_avantages = 0.0
    regles_aen = contexte.entreprise.get("parametres_paie", {}).get(
        "avantages_en_nature", {}
    ) or {}
    situation_salarie_aen = contexte.contrat.get("remuneration", {}).get(
        "avantages_en_nature", {}
    ) or {}
    situation_repas = situation_salarie_aen.get("repas", {})
    if situation_repas.get("nombre_par_mois", 0) > 0:
        valeur_forfaitaire_repas = regles_aen.get("repas_valeur_forfaitaire", 0.0)
        total_avantages += situation_repas["nombre_par_mois"] * valeur_forfaitaire_repas
    situation_logement = situation_salarie_aen.get("logement", {})
    if situation_logement.get("beneficie"):
        bareme_logement = regles_aen.get("logement_bareme_forfaitaire", [])
        salaire_mensuel = contexte.salaire_base_mensuel
        nb_pieces = situation_logement.get("nombre_pieces_principales", 1)
        for tranche in bareme_logement:
            if salaire_mensuel <= tranche.get("remuneration_max", float("inf")):
                valeur = tranche["valeur_1_piece"]
                if nb_pieces > 1:
                    valeur += tranche["valeur_par_piece"] * (nb_pieces - 1)
                total_avantages += valeur
                break
    situation_pret = situation_salarie_aen.get("pret_employeur", {})
    if isinstance(situation_pret, dict):
        montant_pret = situation_pret.get("montant_mensuel", 0) or 0
        if montant_pret > 0:
            total_avantages += float(montant_pret)
    if total_avantages > 0:
        return {
            "libelle": "Avantages en nature",
            "quantite": None,
            "taux": None,
            "gain": round(total_avantages, 2),
            "perte": None,
        }
    return None


def _calculer_prime_anciennete(
    contexte: ContextePaie,
    *,
    calendrier_saisie: List[Dict[str, Any]],
    date_debut_periode: date,
    date_fin_periode: date,
    jours_maintien: Optional[set[int]] = None,
    actual_hours_raw: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any] | None:
    from app.modules.payroll.engine.prime_anciennete import calculer_ligne_prime_anciennete

    ligne = calculer_ligne_prime_anciennete(
        contexte,
        calendrier_saisie=calendrier_saisie,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
        jours_maintien=jours_maintien,
        actual_hours_raw=actual_hours_raw,
    )
    if not ligne:
        return None
    ligne.pop("meta", None)
    return ligne


def _prime_anciennete_deja_saisie(
    primes_saisies: Optional[List[Dict[str, Any]]],
) -> bool:
    """Une saisie mensuelle explicite remplace le calcul conventionnel automatique."""
    for prime in primes_saisies or []:
        label = " ".join(
            str(prime.get(key) or "")
            for key in ("prime_id", "libelle", "name")
        ).lower()
        if "anciennet" in label:
            return True
    return False


# def _calculer_hs_semaine(heures_travaillees: float, duree_contrat_hebdo: float, regles_majoration: List[Dict]) -> Dict[float, float]:
#     """
#     Calcule la répartition des heures supplémentaires pour UNE semaine.
#     """
#     heures_sup_semaine = max(0, heures_travaillees - duree_contrat_hebdo)
#     if heures_sup_semaine == 0:
#         return {}

#     hs_par_taux = {}
#     heures_restantes_a_ventiler = heures_sup_semaine

#     # On prend en compte les HS structurelles déjà incluses dans la durée du contrat
#     heures_structurelles = max(0, duree_contrat_hebdo - 35)

#     # Le seuil de passage à 50% est après 8h au total (structurelles + conjoncturelles)
#     seuil_majoration_max = 8.0

#     # On calcule combien d'heures à 25% on peut encore faire cette semaine
#     heures_a_25_restantes = max(0, seuil_majoration_max - heures_structurelles)

#     taux_25 = regles_majoration[0].get('taux', 0.25)
#     taux_50 = regles_majoration[1].get('taux', 0.50)

#     # On ventile les heures sup de la semaine
#     heures_a_25 = min(heures_restantes_a_ventiler, heures_a_25_restantes)
#     if heures_a_25 > 0:
#         hs_par_taux[taux_25] = heures_a_25
#         heures_restantes_a_ventiler -= heures_a_25

#     if heures_restantes_a_ventiler > 0:
#         hs_par_taux[taux_50] = heures_restantes_a_ventiler

#     return hs_par_taux

# Fichier : moteur_paie/calcul_brut.py

# moteur_paie/calcul_brut.py


#: Types d'événements comptés sur la fenêtre des variables et non sur le mois
#: civil : ce que la gestionnaire de paie arrête à une date qu'elle choisit,
#: les heures supplémentaires et les absences non rémunérées (retour Gaëlle,
#: Colorplast, 14/09/2026 : fenêtre arrêtée au 26/07, la semaine du 27 au 31
#: est celle de la paie d'août — Espinosa, Fuckar, Marion). Le salaire de base
#: est mensualisé ; congés, arrêts et fériés appartiennent au mois du bulletin
#: (IJSS, DSN). Les fenêtres sont des semaines entières contiguës
#: (`shared.domain.periode_variables`) : un jour n'appartient qu'à une seule.
TYPES_RATTACHES_AUX_VARIABLES = frozenset(
    {
        "travail_hs25",
        "travail_hs50",
        "absence_injustifiee_base",
        "absence_injustifiee_hs25",
        "absence_non_remuneree",
        # Congé pour événement familial : le cabinet paie sur le bulletin de
        # mars celui de Cotte du 25 au 27 février, la fenêtre de février
        # s'arrêtant au 22. Comme les heures sup et les absences non payées,
        # c'est un élément variable que la gestionnaire arrête à sa date.
        # L'arrêt maladie, lui, reste au mois civil : le cabinet déduit
        # l'intégralité de celui de Gautheron (16 au 28/03) sur mars, alors
        # que la semaine du 23 appartient à la fenêtre d'avril — il porte ses
        # propres dates, pour les IJSS comme pour la DSN.
        "evenement_familial",
        # Congé payé : même chose, le cabinet paie sur le bulletin de mars
        # celui de Gautheron du 23 février. L'indemnité et le décompte du solde
        # suivent donc la fenêtre, pas le mois civil.
        "conges_payes",
    }
)


def evenements_de_la_periode(
    calendrier_saisie: List[Dict[str, Any]],
    bornes_mois: tuple[date, date],
    bornes_variables: Optional[tuple[date, date]],
) -> List[Dict[str, Any]]:
    """Filtre les événements selon la fenêtre qui les concerne.

    `bornes_variables` à None = comportement historique, une seule fenêtre.
    """
    debut_mois, fin_mois = bornes_mois
    retenus: List[Dict[str, Any]] = []
    for evenement in calendrier_saisie:
        # Une régularisation antérieure est volontairement datée d'un mois
        # antérieur : elle reste rattachée au bulletin courant.
        if evenement.get("is_regularisation_anterieure"):
            retenus.append(evenement)
            continue
        try:
            date_evenement = date.fromisoformat(evenement["date_complete"])
        except (KeyError, TypeError, ValueError):
            continue
        if (
            bornes_variables is not None
            and evenement.get("type") in TYPES_RATTACHES_AUX_VARIABLES
        ):
            debut, fin = bornes_variables
        else:
            debut, fin = debut_mois, fin_mois
        if debut <= date_evenement <= fin:
            retenus.append(evenement)
    return retenus


def calculer_salaire_brut(
    contexte: ContextePaie,
    calendrier_saisie: List[Dict[str, Any]],
    date_debut_periode: date,
    date_fin_periode: date,
    primes_saisies: List[Dict[str, Any]] = None,
    jours_maintien: Optional[set[int]] = None,
    actual_hours_raw: Optional[List[Dict[str, Any]]] = None,
    actual_hours_all_months: Optional[List[Dict[str, Any]]] = None,
    nb_jours_travail_planifies: Optional[int] = None,
    date_debut_variables: Optional[date] = None,
    date_fin_variables: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Calcule le salaire brut à partir d'une liste d'événements de paie déjà analysés.

    ``nb_jours_travail_planifies`` (optionnel) : nombre de jours de type
    ``"travail"`` OU ``"conges_payes"`` dans le `planned_calendar` BRUT du mois
    (avant analyse) — les congés payés comptent aussi comme "couvert" (le
    salarié est normalement rémunéré via l'indemnité de CP, ce n'est PAS une
    absence intégrale non rémunérée). Sert UNIQUEMENT à détecter une absence
    couvrant l'intégralité du mois calendaire (aucun jour de travail NI de CP
    planifié nulle part), afin de compléter la retenue jusqu'au montant
    mensualisé total (fériés/repos inclus, cf. Cegid MBC mai 2026 SAFI2/BABA).
    ⚠️ Ne PAS utiliser les accumulateurs d'heures travaillées
    du présent calcul pour cette détection : `heures_travail_base_total` est
    TOUJOURS à 0 pour un salarié "heures" (le type d'événement "travail_base"
    n'est émis que par le chemin forfait-jour, jamais par
    `analyser_horaires_du_mois`) — l'utiliser comme signal a provoqué une
    régression sur FUCKAR (Colorplast, mois normal sans pointage soumis) lors
    d'une première tentative. Le signal fiable est le calendrier BRUT, pas les
    événements analysés. Si `None` (valeur par défaut, tous les appelants
    existants sauf `payslip_run_heures.py`), le complément ne se déclenche
    jamais — comportement strictement inchangé.
    """
    lignes_composants_brut = []
    duree_legale_hebdo = lc.DUREE_LEGALE_HEBDO
    duree_contrat_hebdo = contexte.duree_hebdo_contrat
    salaire_contractuel = salaire_contractuel_avec_evolution(
        contexte, contexte.salaire_base_mensuel
    )
    facteur_prorata = _facteur_prorata_entree_sortie(
        contexte, date_debut_periode, date_fin_periode
    )
    jours_ouvres_mois = sum(
        1
        for offset in range((date_fin_periode - date_debut_periode).days + 1)
        if (date_debut_periode + timedelta(days=offset)).weekday() < 5
    )
    jours_ouvres_presence = round(jours_ouvres_mois * facteur_prorata)
    taux_horaire_de_base = _get_salaire_horaire_base(contexte, duree_contrat_hebdo)
    remuneration_mois_partiel: Dict[str, Any] = {}
    if facteur_prorata < 1.0:
        specificites = contexte.contrat.get("specificites_paie", {}) or {}
        candidate = specificites.get("remuneration_mois_partiel")
        if isinstance(candidate, dict):
            remuneration_mois_partiel = candidate

    heures_base_reelles = remuneration_mois_partiel.get("heures_base")
    if not isinstance(heures_base_reelles, (int, float)) or isinstance(
        heures_base_reelles, bool
    ) or heures_base_reelles < 0:
        heures_base_reelles = None

    heures_hs_structurelles_reelles = remuneration_mois_partiel.get(
        "heures_hs_structurelles"
    )
    if not isinstance(heures_hs_structurelles_reelles, (int, float)) or isinstance(
        heures_hs_structurelles_reelles, bool
    ) or heures_hs_structurelles_reelles < 0:
        heures_hs_structurelles_reelles = None

    retenue_entree_sortie_heures = remuneration_mois_partiel.get(
        "retenue_entree_sortie_heures"
    )
    if not isinstance(retenue_entree_sortie_heures, (int, float)) or isinstance(
        retenue_entree_sortie_heures, bool
    ) or retenue_entree_sortie_heures <= 0:
        retenue_entree_sortie_heures = None

    heures_hs_exonerees = remuneration_mois_partiel.get("heures_hs_exonerees")
    if not isinstance(heures_hs_exonerees, (int, float)) or isinstance(
        heures_hs_exonerees, bool
    ) or heures_hs_exonerees < 0:
        heures_hs_exonerees = None

    montant_hs_exonerees = remuneration_mois_partiel.get("montant_hs_exonerees")
    if not isinstance(montant_hs_exonerees, (int, float)) or isinstance(
        montant_hs_exonerees, bool
    ) or montant_hs_exonerees < 0:
        montant_hs_exonerees = None

    majoration_hs25 = _taux_majoration_hs(contexte, 0)
    majoration_hs50 = _taux_majoration_hs(contexte, 1)
    if majoration_hs25 is None:
        majoration_hs25 = 0.0
    if majoration_hs50 is None:
        majoration_hs50 = 0.0

    remuneration_hs_structurelles = 0.0
    heures_sup_structurelles_mensuelles = 0.0
    #: Heures de base réellement payées : la quantité portée par la ligne
    #: « Salaire de base ». Vaut le mois plein d'ordinaire, et les seules heures
    #: dues sur un mois d'entrée ou de sortie.
    heures_base_remunerees = 0.0

    # 1. Décomposition du salaire de base
    if duree_contrat_hebdo < duree_legale_hebdo:
        heures_mensuelles_contrat = round((duree_contrat_hebdo * 52) / 12, 2)
        if facteur_prorata < 1.0:
            # Mois d'entrée/sortie : les heures réellement dues, si saisies
            # (`remuneration_mois_partiel.heures_base`, comme à temps plein),
            # priment sur le prorata calendaire — un temps partiel à répartition
            # irrégulière (7/7/3/7/7) n'est pas payé « jours ouvrés × durée / 5 »
            # (BOULAY MAJI 04/2026 : 24,33 h dues, 24,80 h par prorata).
            heures_mensuelles_contrat = round(
                heures_base_reelles
                if heures_base_reelles is not None
                else jours_ouvres_presence * duree_contrat_hebdo / 5,
                2,
            )
            gain_base = round(
                heures_mensuelles_contrat * taux_horaire_de_base, 2
            )
        else:
            gain_base = round(salaire_contractuel, 2)
        heures_base_remunerees = heures_mensuelles_contrat
        lignes_composants_brut.append(
            {
                "libelle": "Salaire de base",
                "quantite": heures_mensuelles_contrat,
                "taux": round(taux_horaire_de_base, 4),
                "gain": gain_base,
                "perte": None,
            }
        )
        remuneration_hs_structurelles = 0.0
        heures_sup_structurelles_mensuelles = 0.0
    else:
        heures_mensuelles_legales_val = heures_mensuelles_legales()
        hors_hs = salaire_hors_hs_structurelles(contexte.contrat)
        if facteur_prorata < 1.0:
            heures_mensuelles_legales_val = round(
                heures_base_reelles
                if heures_base_reelles is not None
                else jours_ouvres_presence * duree_legale_hebdo / 5,
                2,
            )
            salaire_base_35h = round(
                heures_mensuelles_legales_val * taux_horaire_de_base, 2
            )
        elif hors_hs:
            salaire_base_35h = round(salaire_contractuel, 2)
        else:
            salaire_base_35h = heures_mensuelles_legales_val * taux_horaire_de_base
        heures_base_remunerees = heures_mensuelles_legales_val
        lignes_composants_brut.append(
            {
                "libelle": "Salaire de base",
                "quantite": heures_mensuelles_legales_val,
                "taux": round(
                    salaire_base_35h / heures_mensuelles_legales_val
                    if heures_mensuelles_legales_val
                    else taux_horaire_de_base,
                    4,
                ),
                "gain": round(salaire_base_35h, 2),
                "perte": None,
            }
        )
        remuneration_hs_structurelles = 0.0
        heures_sup_structurelles_mensuelles = 0.0
        if duree_contrat_hebdo > duree_legale_hebdo:
            if facteur_prorata < 1.0:
                heures_sup_structurelles_mensuelles = round(
                    heures_hs_structurelles_reelles
                    if heures_hs_structurelles_reelles is not None
                    else (
                        jours_ouvres_presence
                        * (duree_contrat_hebdo - duree_legale_hebdo)
                        / 5
                    ),
                    2,
                )
            else:
                heures_sup_structurelles_mensuelles = (
                    compute_hs_structurelles_mensuelles(duree_contrat_hebdo)
                )
            if hors_hs:
                taux_horaire_majore = taux_horaire_de_base * (1 + majoration_hs25)
                remuneration_hs_structurelles = round(
                    heures_sup_structurelles_mensuelles * taux_horaire_majore, 2
                )
                total_contractuel = round(
                    salaire_base_35h + remuneration_hs_structurelles, 2
                )
            elif facteur_prorata < 1.0:
                taux_horaire_majore = taux_horaire_de_base * (1 + majoration_hs25)
                remuneration_hs_structurelles = round(
                    heures_sup_structurelles_mensuelles * taux_horaire_majore, 2
                )
                total_contractuel = round(
                    salaire_base_35h + remuneration_hs_structurelles, 2
                )
            else:
                remuneration_hs_structurelles = salaire_contractuel - salaire_base_35h
                total_contractuel = salaire_contractuel
            taux_horaire_majore = (
                remuneration_hs_structurelles / heures_sup_structurelles_mensuelles
                if heures_sup_structurelles_mensuelles > 0
                else 0
            )
            majoration_pct = (
                (taux_horaire_majore / taux_horaire_de_base - 1) * 100
                if taux_horaire_de_base > 0
                else 0
            )
            lignes_composants_brut.append(
                {
                    "libelle": f"Heures suppl. structurelles majorées à {majoration_pct:.0f}%",
                    "quantite": heures_sup_structurelles_mensuelles,
                    "taux": round(taux_horaire_majore, 4),
                    "gain": round(remuneration_hs_structurelles, 2),
                    "perte": None,
                }
            )
            lignes_composants_brut.append(
                {
                    "libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL",
                    "quantite": round(
                        heures_mensuelles_legales_val + heures_sup_structurelles_mensuelles,
                        2,
                    ),
                    "taux": None,
                    "gain": total_contractuel,
                    "perte": None,
                    "is_sous_total": True,
                }
            )

    if retenue_entree_sortie_heures is not None:
        lignes_composants_brut.append(
            {
                "libelle": "Absence pour entrée ou sortie",
                "quantite": round(retenue_entree_sortie_heures, 2),
                "taux": round(taux_horaire_de_base, 4),
                "gain": None,
                "perte": round(
                    retenue_entree_sortie_heures * taux_horaire_de_base, 2
                ),
            }
        )

    # Montant mensualisé total du salaire de base (+ HS structurelles si contrat
    # au-dessus de la durée légale) — référence pour la retenue "mois complet
    # d'absence" ci-dessous (indépendant du branchement temps plein/temps
    # partiel/HS structurelles).
    montant_base_mensualise = (
        gain_base
        if duree_contrat_hebdo < duree_legale_hebdo
        else round(salaire_base_35h + remuneration_hs_structurelles, 2)
    )

    # 2. Préparation des taux et des accumulateurs
    taux_hs25 = taux_horaire_de_base * (1 + majoration_hs25)
    taux_hs50 = taux_horaire_de_base * (1 + majoration_hs50)

    # Heures complémentaires (temps partiel) : majorations dédiées (10 % puis 25 %).
    majoration_hc1 = _taux_majoration_hc(contexte, 0)
    majoration_hc2 = _taux_majoration_hc(contexte, 1)
    if majoration_hc1 is None:
        majoration_hc1 = 0.10
    if majoration_hc2 is None:
        majoration_hc2 = 0.25
    taux_hc1 = taux_horaire_de_base * (1 + majoration_hc1)
    taux_hc2 = taux_horaire_de_base * (1 + majoration_hc2)

    smoothing_gain = float(getattr(contexte, "modulation_smoothing_gain", 0) or 0)
    if smoothing_gain > 0:
        lignes_composants_brut.append(
            {
                "libelle": "Lissage modulation",
                "quantite": None,
                "taux": None,
                "gain": round(smoothing_gain, 2),
                "perte": None,
            }
        )

    heures_travail_base_total = 0.0
    heures_travail_hs25_total = 0.0
    heures_travail_hs50_total = 0.0
    heures_travail_hc1_total = 0.0
    heures_travail_hc2_total = 0.0
    heures_absence_hs_total = 0.0  #
    # Heures d'absence retirées sur les HS structurelles au prorata du contrat
    # (contrats > 35 h), cf. `_repartir_absence_au_prorata_du_contrat`.
    heures_hs_structurelles_perdues = 0.0
    # Heures dont la paie a réellement été retirée par une absence NON
    # rémunérée (injustifiée, non rémunérée, férié chômé non payé). Elles
    # sortent du SMIC de référence de la réduction générale, qui est
    # proportionnel aux heures rémunérées. L'arrêt maladie en est exclu : la
    # rémunération y est maintenue en tout ou partie et le SMIC suit alors la
    # part restée à la charge de l'employeur (règle distincte).
    # La retenue d'entrée ou de sortie démarre le compteur : ces heures-là ne
    # sont pas payées non plus. Le mois est mensualisé en entier puis la part
    # antérieure à l'embauche (ou postérieure à la sortie) est retirée, donc
    # elles doivent sortir des heures rémunérées et du SMIC de référence —
    # sinon on réclame un allègement sur des heures qu'on n'a pas payées, le
    # défaut corrigé en janvier pour les absences non rémunérées. Fuckar
    # (Colorplast, avril 2026) : 30,50 h retirées de sa paie mais laissées dans
    # son compteur, 82,02 € d'allègement de trop.
    heures_absence_non_payees = float(retenue_entree_sortie_heures or 0.0)

    contrat_dates = contexte.contrat.get("contrat", {}) or {}
    date_entree_contrat = _parse_date_contrat(contrat_dates.get("date_entree"))
    date_sortie_contrat = _parse_date_contrat(
        contrat_dates.get("date_sortie") or contrat_dates.get("date_fin_contrat")
    )
    jours_dans_periode = []
    bornes_variables = (
        (date_debut_variables, date_fin_variables)
        if date_debut_variables and date_fin_variables
        else None
    )
    for evenement in evenements_de_la_periode(
        calendrier_saisie,
        (date_debut_periode, date_fin_periode),
        bornes_variables,
    ):
        try:
            date_evenement = date.fromisoformat(evenement["date_complete"])
        except (KeyError, TypeError, ValueError):
            continue
        # Aucun événement ne peut produire de paie hors contrat.
        if date_entree_contrat and date_evenement < date_entree_contrat:
            continue
        if date_sortie_contrat and date_evenement > date_sortie_contrat:
            continue
        jours_dans_periode.append(evenement)

    # 3. Traitement de tous les événements de la période
    jours_conges_dans_periode = []
    deduction_arret_maladie_total = 0.0
    #: Heures retirées de la paie par un arrêt de travail. Elles ne sortent du
    #: SMIC de référence qu'à proportion de ce que l'employeur ne maintient pas
    #: — arbitrage fait en aval, où le maintien est connu.
    heures_arret_deduites = 0.0
    #: Congé pour événement familial : heures déduites et journées légales
    #: équivalentes, gardées à part pour remettre exactement la même somme.
    montant_evenement_familial = 0.0
    jours_legaux_evenement_familial = 0.0
    jours_absence_legale_equivalents = 0.0
    # Les journees deduites sur la reference legale, ventilees par origine :
    # leur quote-part d'heures sup structurelles n'est comptee dans aucun
    # accumulateur (contrairement aux absences fractionnees, ou `part_hs`
    # entre directement dans `heures_absence_non_payees`). On la leur rend
    # en fin de calcul, quand la quote-part journaliere est connue.
    jours_absence_legale_ferie = 0.0
    jours_absence_legale_arret = 0.0
    # Cumul des retenues "absence non rémunérée" / "arrêt maladie" / "réduction
    # HS structurelles" déjà appliquées jour par jour — comparé au montant
    # mensualisé total (ci-dessus) UNIQUEMENT si `nb_jours_travail_planifies==0`
    # (aucun jour "travail" dans le calendrier BRUT du mois, cf. docstring).
    montant_absence_pleine_total = 0.0
    for evenement in jours_dans_periode:
        type_ev = evenement.get("type", "")
        heures = evenement.get("heures", 0.0)

        if type_ev == "travail_base" or type_ev == "absence_justifiee":
            heures_travail_base_total += heures
        elif type_ev == "travail_hs25":
            heures_travail_hs25_total += heures
        elif type_ev == "travail_hs50":
            heures_travail_hs50_total += heures
        elif type_ev in ("travail_hc", "travail_hc10"):
            heures_travail_hc1_total += heures
        elif type_ev == "travail_hc25":
            heures_travail_hc2_total += heures
        elif "absence_injustifiee" in type_ev:
            if actual_hours_all_months is not None:
                date_abs = date.fromisoformat(evenement["date_complete"])
                from app.modules.payroll.planning_repli import mois_sans_pointage

                if mois_sans_pointage(
                    actual_hours_all_months,
                    annee=date_abs.year,
                    mois=date_abs.month,
                ):
                    continue

            taux_deduction = taux_horaire_de_base
            is_hs_absence = False
            if "hs25" in type_ev:
                taux_deduction = taux_hs25
                is_hs_absence = True

            heures_abs = _heures_evenement_absence(evenement, duree_contrat_hebdo)
            if duree_contrat_hebdo > lc.DUREE_LEGALE_HEBDO:
                # Contrat > 35 h : chaque heure d'absence est retirée au prorata
                # du contrat, 35/39 au taux de base et 4/39 sur les heures sup
                # structurelles mensualisées, sur les heures planifiées du jour.
                # C'est ce que fait le cabinet : Colorplast juillet 2026,
                # journée de 8,5 h → 7,63 + 0,87 (Marion, retour Gaëlle 12/09) ;
                # MBC, journées de 7,8 h → 7,00 + 0,80. La position de l'absence
                # dans la semaine (base/hs25 de l'analyseur) n'entre pas en jeu,
                # et une journée n'est plus plafonnée à 7 h.
                part_base, part_hs = _repartir_absence_au_prorata_du_contrat(
                    heures_abs, duree_contrat_hebdo
                )
                if not evenement.get("is_regularisation_anterieure"):
                    heures_hs_structurelles_perdues += part_hs
                    heures_absence_non_payees += part_hs
                heures_absence_non_payees += part_base
                heures_abs = part_base
                taux_deduction = taux_horaire_de_base
                type_ev = "absence_injustifiee_base"
            elif is_hs_absence:
                heures_absence_hs_total += heures_abs
                heures_absence_non_payees += heures_abs
            else:
                # Même règle que l'arrêt maladie (cf. bloc arret_maladie plus
                # bas, cas OSMANI2) : la retenue « base » d'une journée
                # d'absence se plafonne à la référence journalière LÉGALE
                # (min(contrat, 35)/5). Un contrat 39 h planifié 8,5 h/j
                # retenait 8,5 h au taux de base — les heures structurelles
                # du jour, payées majorées, étaient retenues au taux normal —
                # et la quote-part d'HS structurelles n'était jamais réduite
                # (retour Gaëlle 07/09, GAUTHERON juillet : sur-retenue base
                # +19,72 € et réduction HS absente). Le `min` préserve les
                # absences fractionnaires (0,25 h reste 0,25 h).
                heures_abs = min(
                    heures_abs, _heures_journalieres_contrat(duree_contrat_hebdo)
                )
                heures_absence_non_payees += heures_abs
                if not evenement.get("is_regularisation_anterieure"):
                    jours_absence_legale_equivalents += (
                        heures_abs / lc.DUREE_LEGALE_HEBDO * 5
                    )

            montant_deduction = round(heures_abs * taux_deduction, 2)
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            libelle_absence = (
                f"Absence injustifiée du {date_absence} ({type_ev.split('_')[-1]})"
            )
            lignes_composants_brut.append(
                {
                    "libelle": libelle_absence,
                    "quantite": heures_abs,
                    "taux": round(taux_deduction, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )

        elif type_ev == "absence_non_remuneree":
            heures_abs = _heures_evenement_absence(evenement, duree_contrat_hebdo)
            part_hs = 0.0
            if duree_contrat_hebdo > lc.DUREE_LEGALE_HEBDO:
                # Même prorata du contrat que l'absence injustifiée ci-dessus
                # (Demory, Colorplast juin 2026 : 8,5 h → 7,63 + 0,87).
                heures_abs, part_hs = _repartir_absence_au_prorata_du_contrat(
                    heures_abs, duree_contrat_hebdo
                )
            montant_deduction = round(heures_abs * taux_horaire_de_base, 2)
            # Une régularisation antérieure (cf. `is_regularisation_anterieure`)
            # ne doit PAS contribuer à la quote-part des HS structurelles
            # mensualisées DU MOIS COURANT (cette quote-part concerne le mois
            # d'origine, déjà clos — Cegid ne réduit pas les HS structurelles
            # de mai pour une absence d'avril rattachée au bulletin de mai,
            # cf. KIRMIZI mai 2026 MBC : sans cette exclusion, la retenue est
            # sur-évaluée d'une réduction HS structurelles fantôme).
            heures_absence_non_payees += heures_abs
            if not evenement.get("is_regularisation_anterieure"):
                if duree_contrat_hebdo > lc.DUREE_LEGALE_HEBDO:
                    heures_hs_structurelles_perdues += part_hs
                    heures_absence_non_payees += part_hs
                else:
                    jours_absence_legale_equivalents += (
                        heures_abs / lc.DUREE_LEGALE_HEBDO * 5
                    )
                montant_absence_pleine_total += montant_deduction
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            lignes_composants_brut.append(
                {
                    "libelle": f"Absence non rémunérée du {date_absence}",
                    "quantite": heures_abs,
                    "taux": round(taux_horaire_de_base, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )
        elif type_ev == "conges_payes":
            jours_conges_dans_periode.append(evenement)
        elif type_ev == "evenement_familial":
            # Congé pour événement familial (art. L3142-1 et suivants) :
            # absence autorisée dont la rémunération est intégralement
            # maintenue. Déduite puis remise à l'identique, comme le fait le
            # cabinet — le brut ne bouge pas, mais la journée cesse d'être
            # invisible. Écrite jusqu'ici sous le type `conge`, que le moteur
            # ne lit nulle part, elle n'était ni travaillée ni en congé : elle
            # ne figurait pas au bulletin et minorait les heures sup de sa
            # semaine (371 jours dans ce cas sur le groupe au 26/08/2026).
            #
            # Ni le compteur d'heures, ni le plafond, ni le SMIC de référence
            # ne bougent : la rémunération étant maintenue, ces trois-là ne se
            # réduisent pas. Le cabinet retire pourtant les heures du compteur
            # et proratise le plafond, alors qu'il garde les heures d'un congé
            # payé — sans conséquence financière ici, le brut restant sous le
            # plafond dans les deux cas. Écarts documentés dans
            # `docs/colorplast-mars-2026-ligne-a-ligne.md`.
            heures_abs = min(
                _heures_evenement_absence(evenement, duree_contrat_hebdo),
                _heures_journalieres_contrat(duree_contrat_hebdo),
            )
            montant_deduction = round(heures_abs * taux_horaire_de_base, 2)
            montant_evenement_familial += montant_deduction
            if not evenement.get("is_regularisation_anterieure"):
                jours_legaux_evenement_familial += (
                    heures_abs / lc.DUREE_LEGALE_HEBDO * 5
                )
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            lignes_composants_brut.append(
                {
                    "libelle": f"Absence événement familial du {date_absence}",
                    "quantite": heures_abs,
                    "taux": round(taux_horaire_de_base, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )
        elif type_ev == "ferie" and not _jour_ferie_est_paye(contexte, evenement):
            # Comme l'arrêt maladie et le congé pour événement familial, une
            # journée de férié non payé se valorise sur la référence journalière
            # légale : 7 h de base, la quote-part d'heures sup structurelles
            # étant retirée séparément juste après. Déduire les heures planifiées
            # (7,80 sur un contrat de 39 h) retirerait deux fois la part
            # structurelle. Demory et Fuckar, Colorplast mai 2026 : le cabinet
            # déduit 7,00 h à 12,20 (85,40) et 0,80 h structurelles.
            heures_abs = min(
                _heures_evenement_absence(evenement, duree_contrat_hebdo),
                _heures_journalieres_contrat(duree_contrat_hebdo),
            )
            montant_deduction = round(heures_abs * taux_horaire_de_base, 2)
            heures_absence_non_payees += heures_abs
            if not evenement.get("is_regularisation_anterieure"):
                jours_absence_legale_equivalents += (
                    heures_abs / lc.DUREE_LEGALE_HEBDO * 5
                )
                jours_absence_legale_ferie += heures_abs / lc.DUREE_LEGALE_HEBDO * 5
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            lignes_composants_brut.append(
                {
                    "libelle": f"Abs. jour férié non payé du {date_absence}",
                    "quantite": heures_abs,
                    "taux": round(taux_horaire_de_base, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )
        elif type_ev.startswith("arret"):
            # Tous les arrêts de travail se déduisent de la même façon —
            # maladie, accident du travail, maternité, paternité. Seul le
            # maintien de salaire les distingue, et il se joue ailleurs (à
            # partir de `arret_type`). La branche ne reconnaissait que
            # `arret_maladie` : l'accident du travail de Demory (Colorplast,
            # 23 au 29/05/2026) passait à travers, 390,40 € de trop au brut.
            #
            # La retenue d'un jour d'arrêt se valorise sur la référence
            # journalière LÉGALE (7 h temps plein), jamais sur les heures
            # planifiées du jour (souvent 7,5 h contractuelles issues d'un
            # template) : le salaire de base est mensualisé sur 151,67 h légales
            # et la quote-part d'HS structurelle est déjà retirée séparément par
            # la ligne « Réduction HS structurelles ». Déduire 7,5 h au taux de
            # base retirerait deux fois la part structurelle (sur-déduction, cf.
            # OSMANI2 MBC mai 2026 : 7,5 h vs 7 h → −0,5 h/jour de trop). Le
            # `min` préserve les arrêts fractionnaires (demi-journée < réf.
            # légale, ex. 3,5 h), imputés à leur valeur réelle.
            heures_abs = min(
                _heures_evenement_absence(evenement, duree_contrat_hebdo),
                _heures_journalieres_contrat(duree_contrat_hebdo),
            )
            montant_deduction = round(heures_abs * taux_horaire_de_base, 2)
            deduction_arret_maladie_total += montant_deduction
            heures_arret_deduites += heures_abs
            if not evenement.get("is_regularisation_anterieure"):
                jours_absence_legale_equivalents += (
                    heures_abs / lc.DUREE_LEGALE_HEBDO * 5
                )
                jours_absence_legale_arret += heures_abs / lc.DUREE_LEGALE_HEBDO * 5
                montant_absence_pleine_total += montant_deduction
            lignes_composants_brut.append(
                {
                    "libelle": f"Absence {LIBELLES_ARRET.get(type_ev, 'arrêt de travail')} (jours déduction)",
                    "quantite": heures_abs,
                    "taux": round(taux_horaire_de_base, 4),
                    "gain": None,
                    "perte": montant_deduction,
                    "is_arret_maladie": True,
                }
            )

    # Réduction proportionnelle des HS structurelles mensualisées (salaire_hors_hs_structurelles)
    # pour les journées d'absence déduites sur la référence légale : le salarié absent un
    # jour ne génère pas non plus sa quote-part de l'heure supplémentaire structurelle de
    # ce jour-là (17,33 h/mois répartis sur les jours ouvrés légaux du mois).
    heures_hs_perdues = 0.0
    if jours_absence_legale_equivalents > 0 and heures_sup_structurelles_mensuelles > 0:
        jours_legaux_mensuels = (
            jours_ouvres_presence
            if facteur_prorata < 1.0
            else heures_mensuelles_legales() / (lc.DUREE_LEGALE_HEBDO / 5)
        )
        quote_part_hs_journaliere = (
            heures_sup_structurelles_mensuelles / jours_legaux_mensuels
        )
        heures_hs_perdues = (
            quote_part_hs_journaliere * jours_absence_legale_equivalents
        )
        # Un jour non travaillé et non payé ne vaut pas 7 h mais 7,80 sur un
        # contrat de 39 h : 7 h de base plus la quote-part d'heure sup
        # structurelle du jour. Le brut retirait bien les deux, mais le
        # compteur d'heures et le SMIC de référence ne voyaient que la base —
        # la part structurelle des jours fériés non payés et des jours d'arrêt
        # y revenait comme si elle avait été payée. Colorplast mai 2026 :
        # Demory 338,70 h au compteur au lieu des 333,90 du cabinet, soit
        # 6 jours × 0,80. On la rattache à l'absence dont elle vient, pour que
        # le maintien d'un arrêt la restitue comme il restitue la base.
        heures_absence_non_payees += (
            quote_part_hs_journaliere * jours_absence_legale_ferie
        )
        heures_arret_deduites += (
            quote_part_hs_journaliere * jours_absence_legale_arret
        )
    # Part des absences retirée directement sur les HS structurelles (contrat
    # > 35 h, prorata du contrat) : elle s'ajoute à la quote-part par journée.
    heures_hs_perdues = round(heures_hs_perdues + heures_hs_structurelles_perdues, 2)
    if heures_hs_perdues > 0 and heures_sup_structurelles_mensuelles > 0:
        if heures_hs_perdues > 0:
            montant_reduction_hs = round(heures_hs_perdues * taux_horaire_majore, 2)
            montant_absence_pleine_total += montant_reduction_hs
            lignes_composants_brut.append(
                {
                    "libelle": "Réduction HS structurelles (jours d'absence)",
                    "quantite": heures_hs_perdues,
                    "taux": round(taux_horaire_majore, 4),
                    "gain": None,
                    "perte": montant_reduction_hs,
                    "is_reduction_hs": True,
                }
            )

    # Congé pour événement familial : sa quote-part d'heures sup structurelles
    # est retirée comme pour toute journée d'absence, puis l'ensemble — base et
    # heures sup — est remis par une ligne de maintien. Le calcul de la
    # quote-part est celui des autres absences, appliqué aux seules journées
    # d'événement familial (Cotte, mars 2026 : 3 jours, 21,00 h de base pour
    # 271,93 € et 2,40 h structurelles pour 38,85 €, maintien de 310,78 €).
    if jours_legaux_evenement_familial > 0:
        if heures_sup_structurelles_mensuelles > 0:
            jours_legaux_mensuels = (
                jours_ouvres_presence
                if facteur_prorata < 1.0
                else heures_mensuelles_legales() / (lc.DUREE_LEGALE_HEBDO / 5)
            )
            heures_hs_evenement_familial = round(
                heures_sup_structurelles_mensuelles
                * jours_legaux_evenement_familial
                / jours_legaux_mensuels,
                2,
            )
            if heures_hs_evenement_familial > 0:
                montant_hs_evenement_familial = round(
                    heures_hs_evenement_familial * taux_horaire_majore, 2
                )
                montant_evenement_familial += montant_hs_evenement_familial
                lignes_composants_brut.append(
                    {
                        "libelle": "Réduction HS structurelles (événement familial)",
                        "quantite": heures_hs_evenement_familial,
                        "taux": round(taux_horaire_majore, 4),
                        "gain": None,
                        "perte": montant_hs_evenement_familial,
                    }
                )
        montant_evenement_familial = round(montant_evenement_familial, 2)
        if montant_evenement_familial > 0:
            lignes_composants_brut.append(
                {
                    "libelle": "Maintien de salaire (événement familial)",
                    "quantite": None,
                    "taux": None,
                    "gain": montant_evenement_familial,
                    "perte": None,
                }
            )

    # Absence couvrant l'INTÉGRALITÉ du mois calendaire (cf. Cegid MBC mai 2026
    # SAFI2/BABA — arrêt maladie/prolongation de rechute, AUCUN jour "travail"
    # planifié nulle part dans le calendrier BRUT du mois, pas seulement "zéro
    # heure travaillée" au sens des accumulateurs ci-dessus qui sont TOUJOURS à
    # 0 pour un salarié "heures", cf. docstring). La retenue jour-ouvré-par-
    # jour-ouvré ne déduit pas les jours fériés/repos compris dans la période
    # (ils ne sont ni travaillés ni "absents" au sens du calendrier), mais
    # Cegid déduit alors l'intégralité du salaire mensualisé. Gaté strictement
    # sur `nb_jours_travail_planifies == 0` (calendrier brut fourni par
    # l'appelant, cf. payslip_run_heures.py) : ne peut PAS se déclencher pour
    # un salarié qui a ne serait-ce qu'un seul jour "travail" planifié dans le
    # mois, quel que soit l'état du pointage.
    if (
        nb_jours_travail_planifies == 0
        and montant_absence_pleine_total > 0
    ):
        complement_absence_pleine = round(
            montant_base_mensualise - montant_absence_pleine_total, 2
        )
        if complement_absence_pleine > 0.01:
            lignes_composants_brut.append(
                {
                    "libelle": "Complément retenue absence intégrale du mois "
                    "(jours fériés/repos inclus)",
                    "quantite": None,
                    "taux": None,
                    "gain": None,
                    "perte": complement_absence_pleine,
                }
            )

    # Saisie manuelle (monthly_inputs) : HS conjoncturelles déclarées sans badgeage.
    declared_conj = float(contexte.heures_sup_du_mois or 0)
    declared_conj_50 = float(contexte.heures_sup_du_mois_50 or 0)
    if declared_conj > 0 or declared_conj_50 > 0:
        calendar_conj = heures_travail_hs25_total + heures_travail_hs50_total
        if abs((declared_conj + declared_conj_50) - calendar_conj) > 0.001:
            heures_travail_hs25_total = round(declared_conj, 2)
            heures_travail_hs50_total = round(declared_conj_50, 2)

    # 4. Ajout des lignes de GAIN pour les heures travaillées (après accumulation)
    # if heures_travail_base_total > 0:
    #     lignes_composants_brut.append({"libelle": "Heures normales travaillées", "quantite": round(heures_travail_base_total, 2), "taux": round(taux_horaire_de_base, 4), "gain": round(heures_travail_base_total * taux_horaire_de_base, 2), "perte": None})
    if heures_travail_hs25_total > 0:
        gain = round(heures_travail_hs25_total * taux_hs25, 2)
        lignes_composants_brut.append(
            {
                "libelle": f"Heures suppl. majorées à {majoration_hs25 * 100:.0f}%",
                "quantite": round(heures_travail_hs25_total, 2),
                "taux": round(taux_hs25, 4),
                "gain": gain,
                "perte": None,
            }
        )
    if heures_travail_hs50_total > 0:
        gain = round(heures_travail_hs50_total * taux_hs50, 2)
        lignes_composants_brut.append(
            {
                "libelle": f"Heures suppl. majorées à {majoration_hs50 * 100:.0f}%",
                "quantite": round(heures_travail_hs50_total, 2),
                "taux": round(taux_hs50, 4),
                "gain": gain,
                "perte": None,
            }
        )
    # Heures complémentaires (temps partiel) : rémunération ordinaire majorée,
    # sans régime social des heures supplémentaires.
    if heures_travail_hc1_total > 0:
        gain = round(heures_travail_hc1_total * taux_hc1, 2)
        lignes_composants_brut.append(
            {
                "libelle": f"Heures complémentaires majorées à {majoration_hc1 * 100:.0f}%",
                "quantite": round(heures_travail_hc1_total, 2),
                "taux": round(taux_hc1, 4),
                "gain": gain,
                "perte": None,
            }
        )
    if heures_travail_hc2_total > 0:
        gain = round(heures_travail_hc2_total * taux_hc2, 2)
        lignes_composants_brut.append(
            {
                "libelle": f"Heures complémentaires majorées à {majoration_hc2 * 100:.0f}%",
                "quantite": round(heures_travail_hc2_total, 2),
                "taux": round(taux_hc2, 4),
                "gain": gain,
                "perte": None,
            }
        )

    # 5. Calcul final des congés (somme des quotités : une demi-journée = 0,5)
    if jours_conges_dans_periode:
        nombre_jours_conges = sum(
            _jours_evenement_conges(ev) for ev in jours_conges_dans_periode
        )
        resultat_conges = calculer_indemnite_conges(
            contexte, nombre_jours_conges, taux_horaire_de_base
        )
        dates_conges = _libelle_dates_conges(jours_conges_dans_periode)
        libelle_conges = "Absence congés payés " + (
            f"({_format_jours_conges(float(resultat_conges['nombre_jours']))} : {dates_conges})"
            if dates_conges
            else f"({_format_jours_conges(float(resultat_conges['nombre_jours']))})"
        )
        lignes_composants_brut.append(
            {
                "libelle": libelle_conges,
                "quantite": round(resultat_conges["total_heures_absence"], 2),
                "taux": None,
                "gain": None,
                "perte": resultat_conges["montant_retenue"],
            }
        )
        if resultat_conges["methode_retenue"] == "Maintien":
            lignes_composants_brut.append(
                {
                    "libelle": "Indemnité de congés payés (partie base)",
                    "quantite": round(resultat_conges["heures_base"], 2),
                    "taux": round(taux_horaire_de_base, 4),
                    "gain": resultat_conges["indemnite_maintien_base"],
                    "perte": None,
                }
            )
            if resultat_conges["indemnite_maintien_hs"] > 0:
                salaire_horaire_majore = taux_horaire_de_base * (1 + majoration_hs25)
                lignes_composants_brut.append(
                    {
                        "libelle": f"Indemnité de congés payés (partie HS {majoration_hs25 * 100:.0f}%)",
                        "quantite": round(resultat_conges["heures_hs"], 2),
                        "taux": round(salaire_horaire_majore, 4),
                        "gain": resultat_conges["indemnite_maintien_hs"],
                        "perte": None,
                    }
                )
        else:
            lignes_composants_brut.append(
                {
                    "libelle": "Indemnité de congés payés (règle du 1/10ème)",
                    "quantite": None,
                    "taux": None,
                    "gain": resultat_conges["montant_indemnite"],
                    "perte": None,
                }
            )

    # 6. Ajout des primes, avantages et calcul des totaux
    ligne_prime_anciennete = None
    if not _prime_anciennete_deja_saisie(primes_saisies):
        ligne_prime_anciennete = _calculer_prime_anciennete(
            contexte,
            calendrier_saisie=calendrier_saisie,
            date_debut_periode=date_debut_periode,
            date_fin_periode=date_fin_periode,
            jours_maintien=jours_maintien,
            actual_hours_raw=actual_hours_raw,
        )
    if ligne_prime_anciennete:
        lignes_composants_brut.append(ligne_prime_anciennete)
    if primes_saisies:
        for prime in primes_saisies:
            lignes_composants_brut.append(
                {
                    "libelle": prime.get("libelle", "Prime"),
                    "quantite": None,
                    "taux": None,
                    "gain": prime.get("montant", 0.0),
                    "perte": None,
                }
            )
    ligne_aen = _construire_ligne_avantages_en_nature(contexte)
    if ligne_aen:
        lignes_composants_brut.append(ligne_aen)
    for ligne_rappel in lignes_rappel_salaire(contexte):
        lignes_composants_brut.append(ligne_rappel)

    # Prime de précarité CDD (dernier mois) — calculée avant le total brut.
    total_gains_inter = sum(
        ligne.get("gain", 0.0) or 0.0
        for ligne in lignes_composants_brut
        if not ligne.get("is_sous_total")
    )
    total_pertes_inter = sum(
        ligne.get("perte", 0.0) or 0.0 for ligne in lignes_composants_brut
    )
    brut_hors_precarite = total_gains_inter - total_pertes_inter
    ligne_precarite = _calculer_prime_precarite_cdd(
        contexte, brut_hors_precarite, date_debut_periode, date_fin_periode
    )
    montant_indemnite_fin = 0.0
    if ligne_precarite:
        lignes_composants_brut.append(ligne_precarite)
        montant_indemnite_fin = ligne_precarite.get("gain", 0.0) or 0.0

    # Indemnité de fin de mission (intérim), dernier mois — équivalent précarité.
    ligne_ifm = _calculer_ifm_interim(
        contexte, brut_hors_precarite, date_debut_periode, date_fin_periode
    )
    if ligne_ifm:
        lignes_composants_brut.append(ligne_ifm)
        montant_indemnite_fin = ligne_ifm.get("gain", 0.0) or 0.0

    # Indemnité compensatrice de congés payés (1/10e), dernier mois CDD/mission.
    ligne_iccp = _calculer_iccp_cdd(
        contexte,
        brut_hors_precarite,
        montant_indemnite_fin,
        date_debut_periode,
        date_fin_periode,
        lignes_brut=lignes_composants_brut,
        taux_horaire_base=taux_horaire_de_base,
        majoration_hs25=majoration_hs25,
    )
    if ligne_iccp:
        lignes_composants_brut.append(ligne_iccp)

    # Indemnités du dossier de départ soumises à cotisations (préavis, congés
    # payés) : dans le brut, pas après les cotisations.
    lignes_composants_brut.extend(lignes_indemnites_sortie_soumises(contexte))

    # Le calcul du brut total reste inchangé
    total_gains = sum(
        ligne.get("gain", 0.0) or 0.0
        for ligne in lignes_composants_brut
        if not ligne.get("is_sous_total")
    )
    total_pertes = sum(
        ligne.get("perte", 0.0) or 0.0 for ligne in lignes_composants_brut
    )
    total_brut = total_gains - total_pertes

    # Étape 1 : Isoler les gains liés aux HS (structurelles et conjoncturelles)
    # Note: La rémunération des HS structurelles est déjà calculée plus haut.
    remuneration_hs_conjoncturelles = sum(
        ligne.get("gain", 0.0)
        for ligne in lignes_composants_brut
        if ligne.get("libelle", "").startswith("Heures suppl. majorées")
    )

    # Étape 2 (NOUVEAU) : Isoler les pertes liées aux HS
    pertes_heures_supp = sum(
        ligne.get("perte", 0.0)
        for ligne in lignes_composants_brut
        if ligne.get("is_reduction_hs")
        or (
            "absence" in ligne.get("libelle", "").lower()
            and (
                "hs25" in ligne.get("libelle", "").lower()
                or "hs50" in ligne.get("libelle", "").lower()
            )
        )
    )

    # Étape 3 : Calculer la rémunération NETTE des heures supplémentaires
    remuneration_hs_totale = (
        remuneration_hs_structurelles + remuneration_hs_conjoncturelles
    ) - pertes_heures_supp

    # Le total des heures supp pour la déduction forfaitaire patronale n'est pas impacté par les absences
    heures_sup_conjoncturelles = heures_travail_hs25_total + heures_travail_hs50_total
    total_heures_supp_mois = (
        heures_sup_structurelles_mensuelles + heures_sup_conjoncturelles
    ) - heures_absence_hs_total
    if heures_hs_exonerees is not None:
        total_heures_supp_mois = heures_hs_exonerees
    if montant_hs_exonerees is not None:
        remuneration_hs_totale = montant_hs_exonerees

    # --- FIN DU BLOC CORRIGÉ ---

    # Heures complémentaires du mois : exposées au calcul des cotisations pour
    # relever le prorata du plafond SS temps partiel (assiette).
    try:
        contexte.heures_complementaires_mois = round(
            heures_travail_hc1_total + heures_travail_hc2_total, 2
        )
    except Exception:
        pass

    return {
        "salaire_brut_total": round(total_brut, 2),
        "lignes_composants_brut": lignes_composants_brut,
        "remuneration_brute_heures_supp": round(remuneration_hs_totale, 2),
        "total_heures_supp": round(total_heures_supp_mois, 2),
        # HS conjoncturelles seules (au-delà de l'horaire contractuel) : utile
        # pour le SMIC de référence de la réduction (heures rémunérées = contrat
        # + conjoncturelles + complémentaires), sans double-compter le structurel.
        "heures_sup_conjoncturelles": round(heures_sup_conjoncturelles, 2),
        # Heures de base effectivement payées — mois plein, ou les seules heures
        # dues sur un mois d'entrée ou de sortie. Le compteur d'heures et le
        # SMIC de référence en partent : Demory, embauché le 23/03/2026, a
        # 47,50 h de base et non 151,67 (Quadra imprime 50,50 h de période).
        "heures_base_remunerees": round(heures_base_remunerees, 2),
        # Heures retirées de la paie par une absence non rémunérée : à sortir du
        # SMIC de référence de la réduction générale (arrêt maladie exclu).
        "heures_absence_non_payees": round(heures_absence_non_payees, 2),
        # Part « heures sup structurelles » de ces absences, déjà retirée du brut
        # par la ligne « Réduction HS structurelles ». Le compteur d'heures sup
        # imprimé la retranche aussi (Cotte 16,97 et non 17,33 ; Gautheron
        # 16,20). Ne pas la soustraire une seconde fois du SMIC de référence :
        # `heures_absence_non_payees` la contient déjà.
        "heures_sup_perdues_absence": round(heures_hs_perdues, 2),
        "deduction_arret_maladie": round(deduction_arret_maladie_total, 2),
        "heures_arret_deduites": round(heures_arret_deduites, 2),
        "heures_complementaires": round(
            heures_travail_hc1_total + heures_travail_hc2_total, 2
        ),
    }
