from app.core.logging import get_logger, log_payroll_debug

from .contexte import ContextePaie
from .exoneration_alternance import contexte_exoneration_apprenti
from typing import Dict, Any, List


logger = get_logger("modules.payroll.engine.calcul_net")
# moteur_paie/calcul_net.py
def _get_safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def _participation_aggregats(
    participations: List[Dict[str, Any]] | None,
) -> tuple[float, float, float]:
    """Agrège les contributions des sommes de participation/intéressement (numéraire).

    Régime social/fiscal (Code du travail art. L3325-1 ; BOSS) : sommes exonérées
    de cotisations sociales, soumises à CSG/CRDS 9,7 % (6,8 % déductible + 2,9 %
    non déductible). La **part numéraire** est imposable à l'IR ; la part placée
    sur un plan d'épargne salariale (PEE) est exonérée d'IR.

    Chaque entrée : {brut, csg_deductible, csg_non_deductible, csg_total,
    acompte, part_pee}. Retourne (imposable, net_a_payer, net_social) :
    - imposable  = Σ (brut_numéraire − CSG déductible)
    - net_a_payer = Σ (brut − CSG totale − acompte déjà versé)  [part numéraire]
    - net_social  = Σ (brut − CSG totale)                        [part numéraire]
    """
    imposable = 0.0
    net = 0.0
    net_social = 0.0
    for p in participations or []:
        brut = _get_safe_float(p.get("brut"))
        part_pee = _get_safe_float(p.get("part_pee"))
        brut_numeraire = max(0.0, brut - part_pee)
        csg_ded = _get_safe_float(p.get("csg_deductible"))
        csg_total = _get_safe_float(
            p.get("csg_total"),
            csg_ded + _get_safe_float(p.get("csg_non_deductible")),
        )
        acompte = _get_safe_float(p.get("acompte"))
        # CSG déductible imputée au prorata de la part numéraire imposable.
        csg_ded_numeraire = csg_ded * (brut_numeraire / brut) if brut > 0 else 0.0
        csg_total_numeraire = csg_total * (brut_numeraire / brut) if brut > 0 else 0.0
        imposable += brut_numeraire - csg_ded_numeraire
        net_participation = brut_numeraire - csg_total_numeraire
        net += net_participation - acompte
        net_social += net_participation
    return round(imposable, 2), round(net, 2), round(net_social, 2)


# Dans le fichier moteur_paie/calcul_net.py

# Dans le fichier moteur_paie/calcul_net.py


def _get_part_patronale_mutuelle(contexte: ContextePaie) -> float:
    """Part patronale mutuelle soumise à CSG (incluse dans le MNS)."""
    mutuelle_spec = contexte.contrat.get("specificites_paie", {}).get("mutuelle", {})
    part_patronale_mutuelle = 0.0
    if not mutuelle_spec.get("adhesion"):
        return part_patronale_mutuelle

    mutuelle_type_ids = mutuelle_spec.get("mutuelle_type_ids", [])
    if mutuelle_type_ids:
        try:
            # Client admin (service_role) : contourne la RLS pour lire les types de
            # mutuelle d'entreprise (le client par défaut peut être bloqué).
            from app.core.database import get_supabase_admin_client

            supabase_client = get_supabase_admin_client()
            mutuelles_response = (
                supabase_client.table("company_mutuelle_types")
                .select("*")
                .in_("id", mutuelle_type_ids)
                .eq("is_active", True)
                .execute()
            )
            if mutuelles_response.data:
                for mutuelle in mutuelles_response.data:
                    if mutuelle.get("part_patronale_soumise_a_csg", True):
                        part_patronale_mutuelle += _get_safe_float(
                            mutuelle.get("montant_patronal")
                        )
        except Exception as e:
            logger.warning(
                f"ERREUR: Impossible de charger les mutuelles depuis la BDD: {e}"
            )

    for ligne in mutuelle_spec.get("lignes_specifiques", []):
        if ligne.get("part_patronale_soumise_a_csg", True):
            part_patronale_mutuelle += _get_safe_float(ligne.get("montant_patronal"))

    if (
        not mutuelle_type_ids
        and not mutuelle_spec.get("lignes_specifiques")
        and mutuelle_spec.get("montant_patronal") is not None
        and mutuelle_spec.get("part_patronale_soumise_a_csg", True)
    ):
        part_patronale_mutuelle += _get_safe_float(mutuelle_spec.get("montant_patronal"))

    return round(part_patronale_mutuelle, 2)


def calculer_montant_net_social(
    contexte: ContextePaie,
    salaire_brut: float,
    total_cotisations_salariales: float,
    primes_non_soumises: List[Dict[str, Any]],
    participations: List[Dict[str, Any]] | None = None,
) -> float:
    """
    Montant net social (BOSS, arrêté 25/02/2016 modifié).

    MNS = brut
        + part patronale complémentaire santé (non soumise)
        + primes non soumises
        − cotisations sociales obligatoires salariales (CSG/CRDS incluses)

    Hors PAS, remboursements de frais professionnels et IJSS.
    """
    part_patronale_mutuelle = _get_part_patronale_mutuelle(contexte)
    total_primes_non_soumises = sum(
        _get_safe_float(p.get("montant")) for p in primes_non_soumises
    )
    _, _, net_social_participation = _participation_aggregats(participations)
    mns = (
        _get_safe_float(salaire_brut)
        + part_patronale_mutuelle
        + total_primes_non_soumises
        - _get_safe_float(total_cotisations_salariales)
        + net_social_participation
    )
    return round(mns, 2)


def _calculer_net_imposable(
    contexte: ContextePaie,
    salaire_brut: float,
    total_cotisations_salariales: float,
    lignes_cotisations: List[Dict[str, Any]],
    remuneration_heures_supp: float,  # <-- NOUVEAU: On passe le montant des HS
    primes_soumises_impot: List[
        Dict[str, Any]
    ] = None,  # <-- NOUVEAU: Primes soumises à l'impôt (ex: PPV si effectif >= 50)
    participations: List[Dict[str, Any]] | None = None,
) -> float:
    if primes_soumises_impot is None:
        primes_soumises_impot = []

    montant_csg_non_deductible = 0.0
    montant_csg_sur_hs = 0.0
    for ligne in lignes_cotisations:
        # Les lignes CSG de participation sont traitées à part (elles ne
        # s'appliquent pas au brut de salaire) : ne pas les réintégrer ici.
        if ligne.get("is_participation"):
            continue
        libelle = ligne.get("libelle", "").lower()
        if "csg/crds" in libelle and "non déductible" in libelle:
            montant_csg_non_deductible += _get_safe_float(ligne.get("montant_salarial"))
        # CSG/CRDS assise sur les heures supplémentaires : elle reste due même si
        # les HS sont exonérées d'impôt ; on la retranche donc du montant d'HS
        # défiscalisé (l'exonération d'IR porte sur le NET des HS, pas le brut).
        if "sur hs" in libelle:
            montant_csg_sur_hs += _get_safe_float(ligne.get("montant_salarial"))

    part_patronale_mutuelle = _get_part_patronale_mutuelle(contexte)

    salaire_brut_safe = _get_safe_float(salaire_brut)
    total_cotisations_safe = _get_safe_float(total_cotisations_salariales)

    # --- Formule standard du net imposable "brut" ---
    net_imposable_avant_defiscalisation = (
        (salaire_brut_safe - total_cotisations_safe)
        + montant_csg_non_deductible
        + part_patronale_mutuelle
    )

    # --- Défiscalisation des heures supplémentaires (art. 81 quater CGI) ---
    # L'exonération d'impôt porte sur le montant NET des HS = rémunération brute
    # des HS moins la CSG/CRDS qui reste due sur ces heures. On ne défiscalise
    # donc pas le brut mais le net imposable réellement attribuable aux HS.
    hs_defiscalisees = max(
        0.0, _get_safe_float(remuneration_heures_supp) - montant_csg_sur_hs
    )
    net_imposable_apres_hs = net_imposable_avant_defiscalisation - hs_defiscalisees

    # --- NOUVEAU : Ajout des primes soumises à l'impôt (ex: PPV si effectif >= 50) ---
    montant_primes_soumises_impot = 0.0
    for prime in primes_soumises_impot:
        montant_prime = _get_safe_float(prime.get("montant"))
        montant_primes_soumises_impot += montant_prime

    # --- Participation / intéressement (part numéraire imposable IR) ---
    imposable_participation, _, _ = _participation_aggregats(participations)

    net_imposable_final = (
        net_imposable_apres_hs + montant_primes_soumises_impot + imposable_participation
    )

    # Le bloc de debug détaillé
    log_payroll_debug(logger, '\n--- Calcul du Net Imposable ---')
    log_payroll_debug(logger, f'\t  Net Social (Net à payer av. impôt) : {salaire_brut_safe - total_cotisations_safe:10.2f} €')
    log_payroll_debug(logger, f'\t+ CSG/CRDS non déductible          : {montant_csg_non_deductible:10.2f} €')
    log_payroll_debug(logger, f'\t+ Part Patronale Mutuelle          : {part_patronale_mutuelle:10.2f} €')
    log_payroll_debug(logger, '\t--------------------------------------------')
    log_payroll_debug(logger, f'\t= Imposable avant défiscalisation  : {net_imposable_avant_defiscalisation:10.2f} €')
    log_payroll_debug(logger, f'\t- Exonération Heures Supp. (net)   : {hs_defiscalisees:10.2f} €')
    if montant_primes_soumises_impot > 0:
        log_payroll_debug(logger, f"\t+ Primes soumises à l'impôt        : {montant_primes_soumises_impot:10.2f} €")
    if imposable_participation:
        log_payroll_debug(logger, f"\t+ Participation (num. imposable)   : {imposable_participation:10.2f} €")
    log_payroll_debug(logger, '\t--------------------------------------------')
    log_payroll_debug(logger, f'\t= NET IMPOSABLE                    : {round(net_imposable_final, 2):10.2f} €')
    log_payroll_debug(logger, '---------------------------------\n')

    return round(net_imposable_final, 2)


def _base_pas_du_mois(contexte: ContextePaie, net_imposable_mois: float) -> float:
    """Base mensuelle du prélèvement à la source.

    Cas général : la base PAS = net imposable du mois.

    Apprenti : la rémunération est exonérée d'impôt jusqu'au SMIC annuel.
    On ne rabote QUE la base PAS (le net imposable affiché/déclaré DSN reste
    inchangé). L'exonération étant annuelle, on raisonne en cumul : la base
    imposable du mois est la fraction du cumul annuel dépassant le plafond.
    Conséquence connue : un « saut » de PAS le mois où le cumul franchit le
    SMIC annuel (comportement correct sur l'année).
    """
    net_imposable_mois = _get_safe_float(net_imposable_mois)

    exo = contexte_exoneration_apprenti(contexte)
    if exo is None:
        return net_imposable_mois

    exoneration_ir = exo.get("exoneration_ir") or {}
    if not exoneration_ir.get("actif"):
        return net_imposable_mois

    pct_annuel = _get_safe_float(exoneration_ir.get("plafond_annuel_pct_smic"))
    if pct_annuel <= 0:
        return net_imposable_mois

    plafond_ir_annuel = contexte.smic_mensuel * 12 * pct_annuel

    cumuls = contexte.cumuls_annee_precedente if isinstance(
        contexte.cumuls, dict
    ) else {}
    net_imposable_cumule_avant = _get_safe_float(cumuls.get("net_imposable"))
    net_imposable_cumule_avec = net_imposable_cumule_avant + net_imposable_mois

    base_pas_cumulee_avant = max(0.0, net_imposable_cumule_avant - plafond_ir_annuel)
    base_pas_cumulee_avec = max(0.0, net_imposable_cumule_avec - plafond_ir_annuel)
    base_pas_mois = base_pas_cumulee_avec - base_pas_cumulee_avant
    return round(max(0.0, base_pas_mois), 2)


def _calculer_prelevement_a_la_source(
    contexte: ContextePaie, net_imposable: float
) -> float:
    taux_pas = _get_safe_float(
        contexte.contrat.get("specificites_paie", {})
        .get("prelevement_a_la_source", {})
        .get("taux")
    )
    # Base PAS éventuellement réduite (exonération IR apprenti). Pour un taux
    # personnalisé DGFiP comme pour un taux neutre/0, on applique le taux sur
    # la base réduite ; un taux 0 donne donc 0 (cohérent).
    base_pas = _base_pas_du_mois(contexte, net_imposable)
    montant_pas = base_pas * (taux_pas / 100.0)
    return round(montant_pas, 2)


def _zone_pas(contexte: ContextePaie) -> str:
    if contexte.is_alsace_moselle:
        return "alsace_moselle"
    return "metropole"


def taux_pas_neutre(
    baremes_pas: List[Dict[str, Any]],
    net_imposable: float,
    zone: str = "metropole",
) -> float:
    """
    Taux neutre PAS depuis le barème scrapé (simulation / contrôle / sans taux individuel).
    """
    if not baremes_pas or net_imposable <= 0:
        return 0.0
    zone_norm = zone.lower().replace("-", "_")
    selected = None
    for entry in baremes_pas:
        if not isinstance(entry, dict):
            continue
        z = str(entry.get("zone", "")).lower().replace("-", "_")
        if z == zone_norm or zone_norm in z or z in zone_norm:
            selected = entry
            break
    if selected is None and baremes_pas:
        selected = baremes_pas[0] if isinstance(baremes_pas[0], dict) else None
    if not selected:
        return 0.0
    tranches = selected.get("tranches") or []
    if not isinstance(tranches, list):
        return 0.0

    def _plafond_key(t: Dict[str, Any]) -> float:
        p = t.get("plafond")
        return float("inf") if p is None else float(p)

    tranches_sorted = sorted(tranches, key=_plafond_key)
    for tr in tranches_sorted:
        plafond = tr.get("plafond")
        if plafond is None or net_imposable <= float(plafond):
            try:
                return float(tr.get("taux") or 0.0)
            except (TypeError, ValueError):
                return 0.0
    if tranches_sorted:
        try:
            return float(tranches_sorted[-1].get("taux") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _calculer_net_a_payer(
    net_social: float,
    montant_pas: float,
    contexte: ContextePaie,
    primes_non_soumises: List[Dict[str, Any]],
    montant_acompte: float = 0.0,
    primes_soumises_impot: List[Dict[str, Any]] = None,
    participations: List[Dict[str, Any]] | None = None,
) -> tuple[float, float, float]:
    if primes_soumises_impot is None:
        primes_soumises_impot = []

    log_payroll_debug(logger, '\n--- Calcul du Net À Payer ---')
    log_payroll_debug(logger, f'\t  Net Social (base de départ)      : {net_social:10.2f} €')
    log_payroll_debug(logger, f'\t- Impôt sur le revenu              : {montant_pas:10.2f} €')

    net_apres_impot = _get_safe_float(net_social) - _get_safe_float(montant_pas)
    log_payroll_debug(logger, '\t--------------------------------------------')
    log_payroll_debug(logger, f'\t= Net après impôt                  : {net_apres_impot:10.2f} €')

    # Initialisation du net à payer
    net_a_payer = net_apres_impot

    # Déduction des titres-restaurant
    tr_spec = contexte.contrat.get("specificites_paie", {}).get("titres_restaurant", {})
    if tr_spec.get("beneficie"):
        valeur_faciale = _get_safe_float(tr_spec.get("valeur_faciale"))
        part_patronale = _get_safe_float(tr_spec.get("part_patronale"))
        nombre_tr = _get_safe_float(tr_spec.get("nombre_par_mois"))
        part_salariale_tr = valeur_faciale - part_patronale
        deduction_tr = part_salariale_tr * nombre_tr

        log_payroll_debug(logger, f'\t- Déduction Titres-Restaurant      : {deduction_tr:10.2f} €')
        net_a_payer -= deduction_tr

    # Ajout du remboursement transport
    transport_spec = contexte.contrat.get("specificites_paie", {}).get("transport", {})
    cout_total_abonnement = _get_safe_float(
        transport_spec.get("abonnement_mensuel_total", 0.0)
    )
    remboursement_transport = 0.0

    if cout_total_abonnement > 0:
        remboursement_transport = round(cout_total_abonnement * 0.5, 2)
        log_payroll_debug(logger, f'\t+ Remboursement Transport          : {remboursement_transport:10.2f} €')
        net_a_payer += remboursement_transport

    indemnite_transport_fixe = _get_safe_float(
        transport_spec.get("indemnite_mensuelle_nette", 0.0)
    )
    if indemnite_transport_fixe > 0:
        indemnite_transport_fixe = round(indemnite_transport_fixe, 2)
        log_payroll_debug(
            logger,
            f'\t+ Indemnité transport contractuelle : {indemnite_transport_fixe:10.2f} €',
        )
        net_a_payer += indemnite_transport_fixe

    # Ajout des primes non soumises aux cotisations ni à l'impôt
    montant_primes_non_soumises = 0.0
    for prime in primes_non_soumises:
        montant_prime = _get_safe_float(prime.get("montant"))
        montant_primes_non_soumises += montant_prime

    # Une entrée non soumise peut être négative (retenue nette : acompte déjà
    # versé, régularisation…) : on l'applique quel que soit le signe, de façon
    # cohérente avec le calcul du montant net social.
    if montant_primes_non_soumises:
        log_payroll_debug(logger, f'\t+ Primes non soumises              : {montant_primes_non_soumises:10.2f} €')
        net_a_payer += montant_primes_non_soumises

    # --- NOUVEAU : Ajout des primes soumises à l'impôt (non soumises aux cotisations) ---
    # Ces primes ne sont pas dans le brut car non soumises aux cotisations, mais doivent être dans le net à payer
    montant_primes_soumises_impot = 0.0
    for prime in primes_soumises_impot:
        montant_prime = _get_safe_float(prime.get("montant"))
        montant_primes_soumises_impot += montant_prime

    if montant_primes_soumises_impot > 0:
        log_payroll_debug(logger, f"\t+ Primes soumises à l'impôt        : {montant_primes_soumises_impot:10.2f} €")
        net_a_payer += montant_primes_soumises_impot

    # --- Participation / intéressement : net numéraire (brut − CSG) − acompte ---
    _, net_participation, _ = _participation_aggregats(participations)
    if net_participation:
        log_payroll_debug(logger, f'\t+ Participation (net numéraire)     : {net_participation:10.2f} €')
        net_a_payer += net_participation

    if montant_acompte > 0:
        log_payroll_debug(logger, f'\t- Acompte versé                    : {montant_acompte:10.2f} €')
        net_a_payer -= montant_acompte
    log_payroll_debug(logger, '\t--------------------------------------------')
    log_payroll_debug(logger, f'\t= NET À PAYER                      : {round(net_a_payer, 2):10.2f} €')
    log_payroll_debug(logger, '-----------------------------\n')

    return round(net_a_payer, 2), remboursement_transport, indemnite_transport_fixe


def calculer_net_et_impot(
    contexte: ContextePaie,
    salaire_brut: float,
    lignes_cotisations: List[Dict[str, Any]],
    total_cotisations_salariales: float,
    primes_non_soumises: List[Dict[str, Any]],
    remuneration_heures_supp: float,
    montant_acompte: float = 0.0,
    primes_soumises_impot: List[
        Dict[str, Any]
    ] = None,  # <-- NOUVEAU: Primes soumises à l'impôt (ex: PPV si effectif >= 50)
    participations: List[Dict[str, Any]] | None = None,
) -> Dict[str, float]:
    if primes_soumises_impot is None:
        primes_soumises_impot = []

    log_payroll_debug(logger, "INFO: Démarrage du calcul des nets et de l'impôt...")

    net_social = round(
        _get_safe_float(salaire_brut) - _get_safe_float(total_cotisations_salariales), 2
    )

    # MODIFIÉ: On passe la nouvelle variable à la fonction de calcul
    net_imposable = _calculer_net_imposable(
        contexte,
        salaire_brut,
        total_cotisations_salariales,
        lignes_cotisations,
        remuneration_heures_supp,
        primes_soumises_impot,  # <-- NOUVEAU: Primes soumises à l'impôt
        participations,
    )

    montant_impot = _calculer_prelevement_a_la_source(contexte, net_imposable)
    base_pas = _base_pas_du_mois(contexte, net_imposable)
    montant_net_social = calculer_montant_net_social(
        contexte,
        salaire_brut,
        total_cotisations_salariales,
        primes_non_soumises,
        participations,
    )
    net_a_payer, remboursement_transport, indemnite_transport_fixe = _calculer_net_a_payer(
        net_social,
        montant_impot,
        contexte,
        primes_non_soumises,
        montant_acompte,  # <--- AJOUTEZ L'ARGUMENT ICI
        primes_soumises_impot,  # <-- NOUVEAU: Primes soumises à l'impôt
        participations,
    )
    logger.info("INFO: Calcul des nets et de l'impôt terminé.")
    return {
        "net_social": net_social,
        "montant_net_social": montant_net_social,
        "net_imposable": net_imposable,
        "base_pas": base_pas,
        "montant_impot_pas": montant_impot,
        "net_a_payer": net_a_payer,
        "remboursement_transport": remboursement_transport,
        "indemnite_transport_fixe": indemnite_transport_fixe,
        "acompte_verse": montant_acompte,  # <--- AJOUTEZ CETTE LIGNE
    }
