# moteur_paie/calcul_reduction_generale.py

from __future__ import annotations

from datetime import date

from app.core.logging import get_logger, log_payroll_debug

from .cotisations_rubriques import enrichir_ligne_cotisation

from typing import Any

from app.modules.payroll.engine.contexte import ContextePaie
from app.modules.payroll.engine import legal_constants as lc

# Note: Ce module suppose l'existence d'un objet "contexte" qui contient
# les informations de l'employé, de l'entreprise et les barèmes/taux.


logger = get_logger("modules.payroll.engine.calcul_reduction_generale")

def _calculer_parametre_T(contexte: ContextePaie) -> float:
    """
    Calcule dynamiquement le paramètre T en additionnant les taux de cotisations
    patronales concernées par la réduction générale.

    Cette méthode est plus robuste qu'un T hardcodé car elle s'adapte
    aux changements de législation si le fichier cotisations.json est à jour.
    """
    taux_a_sommer = {}
    cotisations_data = contexte.baremes.get("cotisations", {}).get("cotisations", [])

    # On convertit la liste en dictionnaire pour un accès facile par ID
    catalogue_cotisations = {c["id"]: c for c in cotisations_data}

    # 1. Taux fixes
    taux_a_sommer["maladie"] = catalogue_cotisations.get(
        "securite_sociale_maladie", {}
    ).get("patronal_reduit", 0.0)
    taux_a_sommer["allocations_familiales"] = catalogue_cotisations.get(
        "allocations_familiales", {}
    ).get("patronal_reduit", 0.0)
    taux_a_sommer["vieillesse_plaf"] = catalogue_cotisations.get(
        "retraite_secu_plafond", {}
    ).get("patronal", 0.0)
    taux_a_sommer["vieillesse_deplaf"] = catalogue_cotisations.get(
        "retraite_secu_deplafond", {}
    ).get("patronal", 0.0)
    taux_a_sommer["csa"] = catalogue_cotisations.get("csa", {}).get("patronal", 0.0)
    taux_a_sommer["chomage"] = catalogue_cotisations.get("assurance_chomage", {}).get(
        "patronal", 0.0
    )

    # 2. Taux de retraite complémentaire (T1 uniquement)
    taux_a_sommer["retraite_comp_t1"] = catalogue_cotisations.get(
        "retraite_comp_t1", {}
    ).get("patronal", 0.0)
    taux_a_sommer["ceg_t1"] = catalogue_cotisations.get("ceg_t1", {}).get(
        "patronal", 0.0
    )

    # 3. Taux variables selon l'entreprise
    effectif = contexte.effectif
    fnal_taux = catalogue_cotisations.get("fnal", {}).get("patronal", {})
    if effectif >= lc.SEUIL_EFFECTIF_FNAL:
        taux_a_sommer["fnal"] = fnal_taux.get("taux_50_et_plus", 0.0)
    else:
        taux_a_sommer["fnal"] = fnal_taux.get("taux_moins_50", 0.0)

    # 4. Taux AT/MP (spécifique à l'entreprise/employé)
    # Il est essentiel que ce taux soit correctement renseigné.
    taux_at_mp = contexte.entreprise.get("parametres_paie", {}).get("taux_at_mp", 0.0)
    if not taux_at_mp:
        logger.warning("AVERTISSEMENT: Le taux AT/MP n'est pas défini. La réduction générale sera sous-évaluée.")
    taux_a_sommer["at_mp"] = taux_at_mp

    parametre_T = sum(taux_a_sommer.values())

    # Le T est plafonné à une valeur maximale (en 2025, 0.3333 pour un taux AT/MP de 1.50%).
    # On peut ajouter un plafond de sécurité si nécessaire, mais le calcul dynamique est la norme.

    log_payroll_debug(logger, f'DEBUG [Réduction]: Calcul du paramètre T = {parametre_T:.6f}')
    return parametre_T


# Dans moteur_paie/calcul_reduction_generale.py


class SmicDeReferenceIntrouvable(ValueError):
    """Pas de SMIC au 1er janvier de l'année du bulletin dans l'historique du SMIC.

    `ValueError` : les générateurs la rendent telle quelle à l'écran (refus 400).
    """


CODE_SMIC_REFERENCE_DIFFERE = "smic_reference_reduction_differe"


def smic_horaire_au_1er_janvier(baremes: dict[str, Any], annee: int) -> float:
    """SMIC horaire en vigueur au 1er janvier `annee`, lu dans `smic.historique`.

    Le SMIC est revalorisé chaque 1er janvier : l'historique doit porter un palier
    daté de ce jour. Sans lui, refus : une valeur d'une autre date (le SMIC
    courant, ou celui de l'année d'avant) fausserait la réduction en silence.
    """
    smic = baremes.get("smic") or {}
    premier_janvier = date(annee, 1, 1)
    valeur = None
    for palier in (smic.get("historique") if isinstance(smic, dict) else None) or []:
        if not isinstance(palier, dict):
            continue
        try:
            debut = date.fromisoformat(str(palier.get("date_debut"))[:10])
            montant = float(palier.get("cas_general") or 0.0)
        except (TypeError, ValueError):
            continue
        if debut == premier_janvier and montant > 0:
            valeur = montant
    if valeur is None:
        raise SmicDeReferenceIntrouvable(
            f"Réduction générale : le SMIC horaire au 1er janvier {annee} manque dans "
            "l'historique du barème SMIC. La réduction se calcule avec le SMIC de "
            "cette date : le bulletin n'est pas calculé. Contactez le support."
        )
    return valeur


def _signaler_cle_dediee_differente(
    contexte: ContextePaie, cle: Any, smic_1er_janvier: float, annee: int
) -> None:
    """Alerte (une par bulletin) si `smic_reference_horaire` diffère de l'historique."""
    try:
        valeur_cle = float(cle)
    except (TypeError, ValueError):
        return
    if round(valeur_cle, 4) == round(smic_1er_janvier, 4):
        return
    alertes = getattr(contexte, "alertes_baremes", None)
    if not isinstance(alertes, list):
        alertes = []
        contexte.alertes_baremes = alertes
    if any(isinstance(a, dict) and a.get("code") == CODE_SMIC_REFERENCE_DIFFERE for a in alertes):
        return
    alertes.append(
        {
            "code": CODE_SMIC_REFERENCE_DIFFERE,
            "critique": False,
            "severity": "warning",
            "message": (
                "Réduction générale : le SMIC de référence saisi dans son barème "
                f"({_montant_fr(valeur_cle)} €) diffère du SMIC au 1er janvier {annee} "
                f"de l'historique du SMIC ({_montant_fr(smic_1er_janvier)} €). "
                f"Martine retient {_montant_fr(smic_1er_janvier)} €. "
                "À vérifier avant de valider ce bulletin."
            ),
        }
    )


def _smic_horaire_de_reference(contexte: ContextePaie) -> float:
    """SMIC horaire de référence de la réduction générale du bulletin.

    RGDU (>= 2026) : celui du 1er janvier de l'année du bulletin (service-public
    F24542 : « 3 × SMIC calculé pour un an, valeur au 1er janvier 2026 »), lu
    dans l'historique du SMIC. Plus de repli sur le SMIC courant : il
    sur-évaluait la réduction [I12]. La clé `smic_reference_horaire` du barème
    de la réduction n'est plus qu'un contrôle.

    Fillon (< 2026) : inchangé, clé dédiée sinon SMIC courant.
    """
    config_red = contexte.baremes.get("reduction_generale", {}) or {}
    annee = getattr(contexte, "year", None) or lc.ANNEE_BASCULE_RGDU
    if annee >= lc.ANNEE_BASCULE_RGDU:
        smic_horaire = smic_horaire_au_1er_janvier(contexte.baremes, annee)
        cle = config_red.get("smic_reference_horaire")
        if cle is not None:
            _signaler_cle_dediee_differente(contexte, cle, smic_horaire, annee)
        return smic_horaire
    smic_data = contexte.baremes.get("smic", {}) or {}
    return float(
        config_red.get("smic_reference_horaire")
        or smic_data.get("smic_horaire_brut")
        or smic_data.get("cas_general")
        or 0.0
    )


def _calculer_smic_de_reference_cumule(
    contexte: ContextePaie, heures_remunerees_cumulees: float
) -> float:
    """SMIC de référence cumulé = SMIC horaire de référence × heures rémunérées.

    Règle URSSAF : le SMIC de référence de la réduction est proportionnel aux
    heures rémunérées, **majorées des heures supplémentaires et complémentaires**
    (comptées au taux normal). On multiplie donc directement un SMIC horaire par
    le total des heures rémunérées cumulées — valable pour temps plein, 39 h ou
    temps partiel (pas de dénominateur `duree_hebdo`, qui faussait le taux
    horaire effectif pour les contrats ≠ 35 h).

    Le SMIC horaire de référence : voir `_smic_horaire_de_reference`.
    """
    smic_horaire = _smic_horaire_de_reference(contexte)
    if smic_horaire <= 0:
        raise ValueError("SMIC horaire de référence introuvable pour la réduction.")

    smic_reference_cumule = round(smic_horaire * heures_remunerees_cumulees, 2)

    log_payroll_debug(
        logger,
        f"DEBUG [Réduction]: SMIC de référence cumulé = {smic_reference_cumule:.2f} € "
        f"(pour {heures_remunerees_cumulees:.2f}h)",
    )

    return smic_reference_cumule


def calculer_coefficient_rgdu(
    brut_cumule: float,
    smic_ref_cumule: float,
    *,
    tmin: float,
    tdelta: float,
    p: float,
    point_sortie: float = 3.0,
) -> tuple[float, dict[str, Any]]:
    """Coefficient de la Réduction Générale Dégressive Unique (RGDU, >= 2026).

    Formule officielle (décret n°2025-887) :
        C = Tmin + (Tdelta × [ (1/2) × (point_sortie × SMIC / Brut − 1) ]^P)

    Bornage : plancher Tmin, plafond Tmax = Tmin + Tdelta, et **nullité par
    discontinuité dès `Brut >= point_sortie × SMIC`** (à 3 SMIC le crochet vaut 0,
    la formule donnerait Tmin et non 0 : la coupure est explicite). Arrondi 4 décimales.

    Fonction PURE : source unique consommée par le moteur ET la page diagnostic
    super-admin (pas de duplication de formule).

    Retourne `(coefficient, detail)` où `detail` documente chaque étape pour l'UI.
    """
    tmax = round(tmin + tdelta, 4)
    seuil_sortie = round(point_sortie * smic_ref_cumule, 2)
    detail: dict[str, Any] = {
        "formule_complete": (
            "C = Tmin + (Tdelta × [ (1/2) × (point_sortie × SMIC / Brut − 1) ]^P)"
        ),
        "tmin": tmin,
        "tdelta": tdelta,
        "p": p,
        "point_sortie": point_sortie,
        "tmax": tmax,
        "smic_ref_cumule": round(smic_ref_cumule, 2),
        "seuil_sortie": round(seuil_sortie, 2),
        "brut_cumule": round(brut_cumule, 2),
    }

    if smic_ref_cumule <= 0 or brut_cumule <= 0:
        detail["resultat"] = "Brut ou SMIC nul → coefficient 0"
        detail["coefficient_C_final"] = 0.0
        return 0.0, detail

    if round(brut_cumule, 2) >= seuil_sortie:
        detail["condition"] = (
            f"Brut cumulé ({brut_cumule:.2f}) ≥ {point_sortie} × SMIC "
            f"({seuil_sortie:.2f})"
        )
        detail["resultat"] = "Non éligible (discontinuité au point de sortie) → 0"
        detail["coefficient_C_final"] = 0.0
        return 0.0, detail

    crochet = 0.5 * (seuil_sortie / brut_cumule - 1)
    crochet_puissance = crochet ** p
    coefficient_brut = tmin + tdelta * crochet_puissance
    coefficient = round(min(coefficient_brut, tmax), 4)

    detail["etape_crochet"] = {
        "calcul": "(1/2) × (point_sortie × SMIC / Brut − 1)",
        "valeur": f"0.5 × ({point_sortie} × {smic_ref_cumule:.2f} / {brut_cumule:.2f} − 1)",
        "resultat": round(crochet, 6),
    }
    detail["etape_puissance"] = {
        "calcul": "crochet ^ P",
        "valeur": f"{crochet:.6f} ^ {p}",
        "resultat": round(crochet_puissance, 6),
    }
    detail["coefficient_avant_plafond"] = round(coefficient_brut, 6)
    detail["plafond_applique"] = coefficient_brut > tmax
    detail["coefficient_C_final"] = coefficient
    return coefficient, detail


def heures_reduction_forfait_jours(
    jours_du_forfait: float, rapport_salaires: float = 1.0
) -> float:
    """Heures du SMIC de référence d'un mois, pour un salarié au forfait annuel en jours.

    CSS D241-7, IV, 3e alinéa, et BOSS (allègements généraux, § 860) : le SMIC
    annuel est « corrigé du rapport entre le nombre de jours prévu au forfait du
    salarié, et 218 jours ». Un mois complet vaut donc la durée légale mensuelle
    (35 × 52 / 12 = 151,67 h) × jours du forfait / 218 : 150,28 h pour 216 jours,
    comme le compte Quadra. Le nombre de jours travaillés dans le mois n'y entre
    pas ; un forfait n'est jamais compté au-delà de 218 jours (pas de majoration
    pour des jours de repos rachetés, § 860).

    `rapport_salaires` corrige le mois d'une absence non payée, d'un arrêt sans
    maintien intégral ou d'une entrée/sortie en cours de mois (D241-7, IV,
    5e alinéa ; voir `rapport_salaires_forfait_jours`). Il est borné à [0, 1].
    """
    jours = float(jours_du_forfait or 0.0)
    if jours <= 0:
        raise ValueError(
            "Nombre de jours du forfait inconnu : la réduction générale d'un "
            "salarié au forfait jours ne peut pas être calculée."
        )
    jours = min(jours, lc.JOURS_FORFAIT_LEGAL)
    rapport = min(1.0, max(0.0, float(rapport_salaires)))
    heures_mois_complet = (lc.DUREE_LEGALE_HEBDO * 52) / 12 * jours / lc.JOURS_FORFAIT_LEGAL
    return round(heures_mois_complet * rapport, 2)


def rapport_salaires_forfait_jours(
    salaire_du_forfait: float,
    retenues_d_absence: float,
    maintien_employeur: float,
) -> float:
    """Rapport des salaires du mois d'un salarié au forfait jours, borné à [0, 1].

    D241-7, IV, 5e alinéa : le SMIC du mois est corrigé du rapport entre la
    rémunération due au titre du mois et celle qui aurait été due si le salarié
    avait été présent tout le mois, hors éléments non affectés par l'absence.
    Pour un forfait jours, la seconde est le salaire du forfait ; la première en
    retire les retenues d'absence non payée, d'arrêt et d'entrée ou de sortie, et
    y rajoute le maintien versé par l'employeur (les IJSS subrogées n'y entrent
    pas, BOSS § 790). Les primes, rappels et indemnités de rupture ne sont
    affectés par aucune absence : ils restent hors du rapport. Les congés payés
    sont payés (retenue compensée par l'indemnité) : ils ne réduisent rien
    (BOSS § 630), l'appelant ne les compte donc pas dans les retenues.
    """
    salaire = float(salaire_du_forfait or 0.0)
    if salaire <= 0:
        return 0.0
    du_au_titre_du_mois = (
        salaire - float(retenues_d_absence or 0.0) + float(maintien_employeur or 0.0)
    )
    return min(1.0, max(0.0, du_au_titre_du_mois / salaire))


class OuvertureReductionIncomplete(ValueError):
    """Cumuls repris sans heures alors qu'une réduction a déjà été appliquée.

    `ValueError` : les générateurs la rendent telle quelle à l'écran (refus 400).
    """


def _montant_fr(montant: float) -> str:
    return f"{montant:,.2f}".replace(",", " ").replace(".", ",")


def _verifier_cumuls_coherents(
    brut_cumule: float, heures_cumulees: float, reduction_deja_appliquee: float
) -> None:
    """Refuse un cumul d'heures vide quand une réduction a déjà été appliquée.

    Une réduction cumulée suppose un SMIC de référence cumulé, donc des heures.
    Un solde d'ouverture repris sans elles (cas d'un forfait jours chez Quadra,
    qui n'imprime pas d'heures) ferait conclure la formule annualisée à plus de
    3 SMIC : le bulletin rembourserait toute la réduction de l'année. Mieux vaut
    ne pas le calculer et dire pourquoi.
    """
    if brut_cumule > 0 and heures_cumulees <= 0 and reduction_deja_appliquee > 0:
        raise OuvertureReductionIncomplete(
            "Réduction générale : les cumuls du mois précédent portent "
            f"{_montant_fr(reduction_deja_appliquee)} € de réduction déjà appliquée "
            f"sur {_montant_fr(brut_cumule)} € de brut, mais aucune heure de SMIC de "
            "référence. Calculé ainsi, ce bulletin rembourserait toute la réduction "
            "de l'année. Le bulletin n'est pas calculé : il faut d'abord compléter "
            "les heures de la réduction générale dans le solde d'ouverture repris."
        )


def _lire_cumuls_precedents(contexte: ContextePaie) -> tuple[float, float, float]:
    """Lit les cumuls (brut, heures rémunérées, réduction déjà appliquée) du mois N-1.

    La régularisation progressive de la réduction générale se calcule sur l'ANNÉE
    CIVILE. Or le générateur lit délibérément décembre N-1 quand il produit
    janvier, et aucun de ces trois compteurs n'est remis à zéro à l'écriture.
    Sans la garde de janvier ci-dessous, le coefficient partirait du brut de toute
    l'année précédente, et la réduction déjà appliquée l'an dernier serait
    soustraite de celle du mois : le bulletin de janvier rembourserait la
    réduction de l'année entière.

    Même garde que `calcul_cotisations._cumul_agirc_arrco_debut_mois` et
    `calcul_net._cumul_hs_exonerees_ir_debut_mois`, qui l'avaient déjà pour leurs
    propres compteurs d'année civile.

    Le brut est `brut_annee_civile`, remis à zéro en janvier comme les heures et
    la réduction : `brut_total` porte aussi l'année d'avant (précarité, dixième
    des congés), et février aurait remboursé la réduction de janvier. Les cumuls
    écrits avant ce compteur (reprise, septembre 2026) n'ont que `brut_total`,
    qui est alors le cumul de l'année civile 2026.
    """
    if getattr(contexte, "month", None) == 1:
        return 0.0, 0.0, 0.0
    if contexte.cumuls is None:
        contexte.cumuls = {}
    cumuls_precedents = (
        contexte.cumuls.get("cumuls", {}) if isinstance(contexte.cumuls, dict) else {}
    )
    brut_cumule = cumuls_precedents.get(
        "brut_annee_civile", cumuls_precedents.get("brut_total", 0.0)
    )
    heures_cumulees = cumuls_precedents.get("heures_remunerees", 0.0)
    reduction_deja_appliquee = abs(
        cumuls_precedents.get("reduction_generale_patronale", 0.0)
    )
    return brut_cumule, heures_cumulees, reduction_deja_appliquee


def _resultat_remboursement_seul(
    salaire_brut_mois: float, reduction_deja_appliquee: float
) -> dict[str, Any] | None:
    """Ligne de remboursement quand plus aucune réduction n'est due (régularisation)."""
    if reduction_deja_appliquee <= 0:
        return None
    return enrichir_ligne_cotisation(
        {
            "libelle": "Réduction générale de cotisations patronales",
            "base": salaire_brut_mois,
            "taux_salarial": None,
            "montant_salarial": 0.0,
            "taux_patronal": None,
            # Remboursement : montant patronal positif (annule le cumul déjà appliqué).
            "montant_patronal": round(reduction_deja_appliquee, 2),
            "valeur_cumulative_a_enregistrer": 0.0,
        },
        coti_id="reduction_generale",
    )


def calculer_reduction_generale(
    contexte: ContextePaie,
    salaire_brut_mois: float,
    heures_remunerees_mois: float,
) -> dict[str, Any] | None:
    """Réduction générale des cotisations patronales avec régularisation progressive.

    Garde-fou par période (`contexte.year`) :
      - `year < 2026` → ancienne réduction Fillon (RGCP) conservée à l'identique ;
      - `year >= 2026` → Réduction Générale Dégressive Unique (RGDU).

    On n'applique jamais une formule structurellement fausse à une période antérieure.

    Args:
        contexte: L'objet contexte (barèmes, cumuls, effectif, year).
        salaire_brut_mois: Le salaire brut du mois en cours.
        heures_remunerees_mois: Le total des heures du mois qui entrent dans le
                               calcul du SMIC de référence (travail, HS, CP, etc.).
    """
    annee = getattr(contexte, "year", None) or lc.ANNEE_BASCULE_RGDU
    if getattr(contexte, "is_stagiaire", False):
        return None
    if annee < lc.ANNEE_BASCULE_RGDU:
        return _calculer_reduction_fillon(
            contexte, salaire_brut_mois, heures_remunerees_mois
        )
    return _calculer_reduction_rgdu(
        contexte, salaire_brut_mois, heures_remunerees_mois
    )


def _calculer_reduction_rgdu(
    contexte: ContextePaie,
    salaire_brut_mois: float,
    heures_remunerees_mois: float,
) -> dict[str, Any] | None:
    """Branche RGDU (>= 2026). Lit les paramètres scrapables dans payroll_config."""
    log_payroll_debug(logger, 'INFO: Calcul de la Réduction Générale (RGDU 2026)...')

    config = contexte.baremes.get("reduction_generale", {}) or {}
    brut_prec, heures_prec, reduction_deja = _lire_cumuls_precedents(contexte)

    # Dispositif absent ou explicitement désactivé (ex. abrogation) : aucune
    # réduction, mais on rembourse une éventuelle réduction déjà cumulée.
    if not config or not config.get("actif", False):
        log_payroll_debug(logger, 'INFO: RGDU inactive (absente ou actif=false).')
        return _resultat_remboursement_seul(salaire_brut_mois, reduction_deja)

    _verifier_cumuls_coherents(brut_prec, heures_prec, reduction_deja)

    brut_total_cumule = brut_prec + salaire_brut_mois
    heures_total_cumulees = heures_prec + heures_remunerees_mois
    smic_reference_total_cumule = _calculer_smic_de_reference_cumule(
        contexte, heures_total_cumulees
    )

    tmin = float(config.get("tmin", 0.0))
    p = float(config.get("p", 1.75))
    point_sortie = float(config.get("point_sortie_smic", 3.0))
    tdelta_cfg = config.get("tdelta", {}) or {}
    if contexte.effectif >= lc.SEUIL_EFFECTIF_FNAL:
        tdelta = float(tdelta_cfg.get("fnal_50_et_plus", 0.0))
    else:
        tdelta = float(tdelta_cfg.get("fnal_moins_50", 0.0))

    coefficient_C, _detail = calculer_coefficient_rgdu(
        brut_total_cumule,
        smic_reference_total_cumule,
        tmin=tmin,
        tdelta=tdelta,
        p=p,
        point_sortie=point_sortie,
    )

    reduction_totale_due = round(brut_total_cumule * coefficient_C, 2)
    montant_reduction_mois = reduction_totale_due - reduction_deja
    montant_final = -round(montant_reduction_mois, 2)

    log_payroll_debug(logger, f'DEBUG [RGDU]: Coeff = {coefficient_C} | Total dû = {reduction_totale_due:.2f} € | Mois = {montant_final} €')

    return enrichir_ligne_cotisation(
        {
            "libelle": "Réduction générale de cotisations patronales",
            "base": salaire_brut_mois,
            "taux_salarial": None,
            "montant_salarial": 0.0,
            "taux_patronal": coefficient_C if coefficient_C > 0 else None,
            "montant_patronal": montant_final,
            "valeur_cumulative_a_enregistrer": reduction_totale_due,
            # SMIC retenu du mois, que la DSN déclare (S21.G00.79 type 01).
            "smic_reference_mois": _calculer_smic_de_reference_cumule(
                contexte, heures_remunerees_mois
            ),
        },
        coti_id="reduction_generale",
    )


def _calculer_reduction_fillon(
    contexte: ContextePaie,
    salaire_brut_mois: float,
    heures_remunerees_mois: float,
) -> dict[str, Any] | None:
    """Ancienne réduction Fillon (RGCP), conservée pour les périodes < 2026.

    Méthode de régularisation progressive : C = (T / 0,6) × (1,6 × SMIC / brut − 1).
    """
    log_payroll_debug(logger, 'INFO: Calcul de la Réduction Générale (Fillon, période < 2026)...')

    # --- ÉTAPE 1 : Récupérer les données cumulées du mois précédent ---
    (
        brut_cumule_annee_N_1,
        heures_cumulees_annee_N_1,
        reduction_deja_appliquee_N_1,
    ) = _lire_cumuls_precedents(contexte)

    # --- ÉTAPE 2 : Calculer les nouveaux cumuls pour le mois en cours ---
    brut_total_cumule = brut_cumule_annee_N_1 + salaire_brut_mois
    heures_total_cumulees = heures_cumulees_annee_N_1 + heures_remunerees_mois

    # --- ÉTAPE 3 : Calculer les paramètres de la formule sur les cumuls ---
    parametre_T = _calculer_parametre_T(contexte)
    smic_reference_total_cumule = _calculer_smic_de_reference_cumule(
        contexte, heures_total_cumulees
    )

    # --- ÉTAPE 4 : Appliquer la formule de la réduction générale sur les cumuls ---
    seuil_eligibilite_cumule = 1.6 * smic_reference_total_cumule

    if brut_total_cumule >= seuil_eligibilite_cumule:
        log_payroll_debug(logger, f'INFO: Brut cumulé ({brut_total_cumule:.2f} €) >= 1.6 * SMIC cumulé ({seuil_eligibilite_cumule:.2f} €). La réduction totale est de 0.')
        # S'il y a eu une réduction les mois précédents, il faut la "rembourser".
        montant_reduction_mois = -reduction_deja_appliquee_N_1
        coefficient_C = 0.0
        reduction_totale_due = (
            0.0  # LIGNE CORRIGÉE : Initialise la variable dans ce cas
        )

    else:
        # Formule : C = (T / 0,6) × ([1,6 × SMIC cumulé / Rémunération brute cumulée] - 1)
        if brut_total_cumule == 0:
            return None  # Division par zéro, pas de salaire, pas de réduction.

        coefficient_C = (parametre_T / 0.6) * (
            (seuil_eligibilite_cumule / brut_total_cumule) - 1
        )
        coefficient_C = min(
            max(0, coefficient_C), parametre_T
        )  # Le coefficient est borné entre 0 et T

        reduction_totale_due = brut_total_cumule * coefficient_C

        # --- ÉTAPE 5 : Calculer la réduction du mois par différence ---
        montant_reduction_mois = reduction_totale_due - reduction_deja_appliquee_N_1

    montant_final = -round(montant_reduction_mois, 2)

    log_payroll_debug(logger, f'DEBUG [Réduction]: Coeff C cumulé = {coefficient_C:.6f} | Réduction totale due = {reduction_totale_due:.2f} €')
    log_payroll_debug(logger, f'DEBUG [Réduction]: Déjà appliqué = {reduction_deja_appliquee_N_1:.2f} € | Montant du mois = {montant_final} €')

    return enrichir_ligne_cotisation(
        {
            "libelle": "Réduction générale de cotisations patronales",
            "base": salaire_brut_mois,
            "taux_salarial": None,
            "montant_salarial": 0.0,
            "taux_patronal": round(coefficient_C, 6) if coefficient_C > 0 else None,
            "montant_patronal": montant_final,
            # Info supplémentaire pour la mise à jour des cumuls
            "valeur_cumulative_a_enregistrer": round(reduction_totale_due, 2),
            # SMIC retenu du mois, que la DSN déclare (S21.G00.79 type 01).
            "smic_reference_mois": _calculer_smic_de_reference_cumule(
                contexte, heures_remunerees_mois
            ),
        },
        coti_id="reduction_generale",
    )
