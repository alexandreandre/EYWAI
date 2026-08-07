from app.core.logging import get_logger, log_payroll_debug

from .contexte import ContextePaie
from typing import Any, Dict, List, Optional
from datetime import date
import calendar

from .cotisations_rubriques import construire_cotisations_officielles


logger = get_logger("modules.payroll.engine.bulletin")
# moteur_paie/bulletin.py

def _get_end_date_for_month(
    target_annee: int, target_mois: int, jour_cible: int, occurrence_cible: int
) -> date:
    _, num_days = calendar.monthrange(target_annee, target_mois)
    jours_trouves = [
        date(target_annee, target_mois, day)
        for day in range(1, num_days + 1)
        if date(target_annee, target_mois, day).weekday() == jour_cible
    ]
    if not jours_trouves:
        return date(target_annee, target_mois, num_days)
    try:
        if occurrence_cible > 0:
            return jours_trouves[occurrence_cible - 1]
        return jours_trouves[occurrence_cible]
    except IndexError:
        return jours_trouves[-1]


def _calculer_date_paiement(contexte: ContextePaie, annee: int, mois: int) -> str:
    from app.modules.payroll.engine.period_forfait import est_mode_mois_calendaire

    regles_paie = contexte.entreprise.get("parametres_paie", {}).get(
        "periode_de_paie", {}
    )
    jour_reference = regles_paie.get("jour_de_fin", 4)
    occurrence_reference = regles_paie.get("occurrence", -2)
    if est_mode_mois_calendaire(jour_reference):
        _, num_days = calendar.monthrange(annee, mois)
        return date(annee, mois, num_days).isoformat()
    date_paiement = _get_end_date_for_month(
        annee, mois, int(jour_reference), int(occurrence_reference)
    )
    return date_paiement.isoformat()


def _formater_classification(contrat: Dict[str, Any]) -> Optional[str]:
    classification = contrat.get("remuneration", {}).get(
        "classification_conventionnelle", {}
    )
    if not isinstance(classification, dict) or not classification:
        return None
    coeff = classification.get("coefficient")
    classe = classification.get("classe_emploi") or classification.get("classe")
    if coeff is not None:
        try:
            coeff_num = float(coeff)
            coeff_txt = str(int(coeff_num)) if coeff_num == int(coeff_num) else str(coeff)
        except (TypeError, ValueError):
            coeff_txt = str(coeff)
        return coeff_txt
    parts = [
        classification.get("niveau"),
        classification.get("echelon"),
        classification.get("position"),
        classification.get("libelle"),
        classe,
    ]
    texte = " ".join(str(p) for p in parts if p)
    return texte or None


def _formater_convention_collective(contrat: Dict[str, Any]) -> Optional[str]:
    ccn = contrat.get("remuneration", {}).get("convention_collective", {})
    if not isinstance(ccn, dict) or not ccn:
        return None
    libelle = ccn.get("libelle") or ccn.get("nom")
    idcc = ccn.get("idcc") or ccn.get("code_idcc")
    if libelle and idcc:
        return f"{libelle} (IDCC {idcc})"
    return libelle or (f"IDCC {idcc}" if idcc else None)


def _extraire_naf_ape(entreprise: Dict[str, Any]) -> Optional[str]:
    identification = entreprise.get("identification", {})
    for key in ("naf_ape", "naf", "code_naf", "naf_code", "ape"):
        value = identification.get(key) or entreprise.get(key)
        if value:
            return str(value)
    return None


def build_solde_conges_pied_de_page(
    employee_id: Optional[str], annee: int, mois: int
) -> Optional[Dict[str, Any]]:
    if not employee_id:
        return None
    try:
        from app.modules.absences.application.queries import (
            get_absence_balances_for_payslip,
        )

        balances = get_absence_balances_for_payslip(employee_id, annee, mois)
    except Exception as exc:
        logger.warning("Impossible de calculer le solde de congés pour le bulletin: %s", exc)
        return None
    return balances or None


def _extraire_employee_id(contexte: ContextePaie) -> Optional[str]:
    employee_id = contexte.contrat.get("employee_id")
    if employee_id:
        return str(employee_id)
    salarie = contexte.contrat.get("salarie", {})
    if isinstance(salarie, dict) and salarie.get("id"):
        return str(salarie["id"])
    return None


def _participation_brut_numeraire(lignes_brut: List[Dict[str, Any]]) -> float:
    """Brut participation / intéressement (numéraire), hors salaire_brut."""
    total = 0.0
    for ligne in lignes_brut:
        libelle = (ligne.get("libelle") or "").lower()
        if "participation" in libelle and "brut" in libelle:
            total += float(ligne.get("gain") or 0)
    return round(total, 2)


def _participation_numeraire_depuis_resultats(
    resultats_nets: Dict[str, Any],
) -> float:
    """Participation effectivement versée en numéraire (hors part placée en PEE)."""
    total = 0.0
    for participation in resultats_nets.get("participations") or []:
        if not isinstance(participation, dict):
            continue
        brut = float(participation.get("brut") or 0)
        part_pee = float(participation.get("part_pee") or 0)
        total += max(0.0, brut - part_pee)
    return round(total, 2)


def _acompte_participation_deja_verse(
    primes_non_soumises: List[Dict[str, Any]],
) -> float:
    """Acompte participation déjà versé (retenue nette du mois, non une réduction de masse)."""
    total = 0.0
    for prime in primes_non_soumises:
        libelle = (prime.get("libelle") or "").lower()
        montant = float(prime.get("montant") or 0)
        if montant < 0 and "acompte" in libelle and "participation" in libelle:
            total += abs(montant)
    return round(total, 2)


def _calculer_cout_total_employeur(
    salaire_brut: float,
    total_cotisations_patronales: float,
    primes_non_soumises: List[Dict[str, Any]],
    lignes_brut: List[Dict[str, Any]],
    primes_soumises_impot: Optional[List[Dict[str, Any]]] = None,
) -> float:
    """
    Coût total employeur (alignement Cegid) :
    brut salaire + charges patronales + participation brute versée
    − acompte déjà payé + primes non soumises positives (remboursements…).

    Les retenues nettes négatives (acompte participation) ne réduisent pas la masse
    salariale : elles régularisent un versement antérieur.
    """
    participation_brut = _participation_brut_numeraire(lignes_brut)
    acompte = _acompte_participation_deja_verse(primes_non_soumises)
    primes_positives = sum(
        max(0.0, float(p.get("montant") or 0))
        for p in primes_non_soumises
        if not p.get("is_rappel_ijss")
    )
    indemnites_activite_partielle = sum(
        max(0.0, float(p.get("montant") or 0))
        for p in primes_soumises_impot or []
        if p.get("prime_id") == "indemnite_activite_partielle"
    )
    return round(
        float(salaire_brut)
        + float(total_cotisations_patronales)
        + participation_brut
        - acompte
        + primes_positives
        + indemnites_activite_partielle,
        2,
    )


def creer_bulletin_final(
    contexte: ContextePaie,
    salaire_brut: float,
    details_brut: List[Dict[str, Any]],
    lignes_cotisations: List[Dict[str, Any]],
    resultats_nets: Dict[str, float],
    primes_non_soumises: List[Dict[str, Any]],
    annee: int,
    mois: int,
    resultats_maintien: Optional[Dict[str, Any]] = None,
    primes_soumises_impot: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Assemble tous les éléments calculés en une structure de données finale
    qui respecte l'ordre d'affichage désiré sur le bulletin.
    """
    log_payroll_debug(logger, 'INFO: Assemblage et tri du bulletin de paie final...')

    lignes_maintien = [ligne for ligne in details_brut if ligne.get("is_arret_maladie")]

    # Séparation en 3 blocs (congés, absences, et le reste)
    lignes_conges = []
    lignes_absences = []
    autres_lignes_brut = []
    indemnite_conges = 0.0
    retenue_conges = 0.0

    for ligne in details_brut:
        libelle = ligne.get("libelle", "").lower()
        if "conges payes" in libelle.replace("é", "e"):
            lignes_conges.append(ligne)
            if "indemnité" in libelle:
                indemnite_conges = ligne.get("gain", 0.0)
            if "absence" in libelle:
                retenue_conges = ligne.get("perte", 0.0)
        elif "absence" in libelle and "congés payés" not in libelle:
            lignes_absences.append(ligne)
        else:
            autres_lignes_brut.append(ligne)

    # Préparation du texte pour l'arbitrage des congés payés
    texte_arbitrage = None
    if lignes_conges:
        if indemnite_conges > retenue_conges:
            texte_arbitrage = f"L'indemnité de congés payés a été calculée selon la règle du 1/10ème (soit {indemnite_conges:.2f} €), plus favorable que le maintien de salaire ({retenue_conges:.2f} €)."
        else:
            texte_arbitrage = f"L'indemnité de congés payés a été calculée selon la règle du maintien de salaire ({retenue_conges:.2f} €), plus favorable que la règle du 1/10ème."

    # Tri des cotisations en plusieurs blocs pour l'affichage
    bloc_principales = []
    bloc_allegements = []
    bloc_autres_contributions = []
    bloc_csg_non_deductible = []

    AUTRES_CONTRIBUTIONS_KEYWORDS = [
        "fnal",
        "formation",
        "apprentissage",
        "solidarité",
        "dialogue",
        "mobilité",
    ]
    ALLEGEMENTS_KEYWORDS = [
        "réduction générale",
        "réduction de cotisations sur heures sup",
        "déduction forfaitaire",
        "exonération cotisations salariales apprenti",
    ]

    for ligne in lignes_cotisations:
        libelle = ligne.get("libelle", "").lower()

        if "csg/crds sur hs" in libelle or "csg/crds non déductible" in libelle:
            bloc_csg_non_deductible.append(ligne)
        elif any(keyword in libelle for keyword in ALLEGEMENTS_KEYWORDS):
            bloc_allegements.append(ligne)
        elif any(keyword in libelle for keyword in AUTRES_CONTRIBUTIONS_KEYWORDS):
            bloc_autres_contributions.append(ligne)
        else:
            bloc_principales.append(ligne)

    # Calcul des totaux
    total_autres_contributions = sum(
        row.get("montant_patronal", 0.0) or 0.0 for row in bloc_autres_contributions
    )
    total_cotisations_salariales = sum(
        row.get("montant_salarial", 0.0) or 0.0 for row in lignes_cotisations
    )
    total_cotisations_patronales = sum(
        row.get("montant_patronal", 0.0) or 0.0 for row in lignes_cotisations
    )

    total_retenues_avant_csg_nd = sum(
        row.get("montant_salarial", 0.0) or 0.0
        for row in bloc_principales + bloc_allegements
    )
    total_patronal_avant_csg_nd = sum(
        row.get("montant_patronal", 0.0) or 0.0
        for row in bloc_principales + bloc_allegements
    )

    cotisations_officielles, total_exonerations = construire_cotisations_officielles(
        lignes_cotisations
    )

    # Assemblage du dictionnaire final
    mois_nom_francais = [
        "Janvier",
        "Février",
        "Mars",
        "Avril",
        "Mai",
        "Juin",
        "Juillet",
        "Août",
        "Septembre",
        "Octobre",
        "Novembre",
        "Décembre",
    ]
    periode_formatee = f"{mois_nom_francais[mois - 1]} {annee}"

    # Base du PAS : net imposable, sauf apprenti exonéré d'IR (base réduite).
    base_pas = resultats_nets.get("base_pas")
    if base_pas is None:
        base_pas = resultats_nets.get("net_imposable")
    exoneration_ir_apprenti = bool(
        contexte.is_apprenti
        and base_pas is not None
        and resultats_nets.get("net_imposable") is not None
        and base_pas < resultats_nets.get("net_imposable")
    )

    # Net avant impôt = net à payer + PAS réintégré (pas le montant net social :
    # celui-ci peut différer du net réellement dû ce mois-ci quand une partie de
    # la rémunération est différée/non cash, ex. participation placée en PEE, ou
    # qu'une régularisation de net à payer négatif ne doit pas impacter le net
    # social — cf. Cegid GAUTHERON/GIRERD mai 2026).
    net_avant_impot = resultats_nets.get("net_a_payer")
    if net_avant_impot is not None and resultats_nets.get("montant_impot_pas") is not None:
        net_avant_impot = round(net_avant_impot + resultats_nets["montant_impot_pas"], 2)
    elif net_avant_impot is None:
        net_avant_impot = resultats_nets.get("montant_net_social") or resultats_nets.get(
            "net_social"
        )

    synthese_net: Dict[str, Any] = {
        "net_social_avant_impot": net_avant_impot,
        "montant_net_social": resultats_nets.get("montant_net_social"),
        "net_imposable": resultats_nets.get("net_imposable"),
        "exoneration_ir_apprenti": exoneration_ir_apprenti,
        "impot_prelevement_a_la_source": {
            "base": base_pas,
            # Le taux appliqué par le moteur, pas celui de la fiche : quand aucun
            # taux personnalisé n'est connu, c'est la grille du mois qui a servi,
            # et le bulletin doit afficher le taux dont vient le montant.
            "taux": resultats_nets.get("taux_pas_applique", 0.0),
            "montant": resultats_nets.get("montant_impot_pas"),
        },
        "remboursement_transport": resultats_nets.get("remboursement_transport"),
        "indemnite_transport_fixe": resultats_nets.get("indemnite_transport_fixe"),
        "acompte_verse": resultats_nets.get(
            "acompte_verse", 0.0
        ),  # Montant des avances déduites
    }
    if resultats_maintien:
        synthese_net["ijss_subrogees"] = (
            resultats_maintien.get("ijss", {}).get("ijss_theorique", 0.0) or 0.0
        )
        synthese_net["maintien_employeur"] = (
            resultats_maintien.get("maintien", {}).get("maintien_verse", 0.0) or 0.0
        )
        synthese_net["complement_employeur"] = (
            resultats_maintien.get("maintien", {}).get("complement_employeur", 0.0)
            or 0.0
        )
        synthese_net["alertes_maintien"] = resultats_maintien.get("alertes", []) or []
        synthese_net["subrogation_active"] = resultats_maintien.get(
            "subrogation_active", False
        )
        ijss_block = resultats_maintien.get("ijss", {}) or {}
        if ijss_block.get("ijss_brut_override"):
            synthese_net["ijss_source"] = "cpam_validated"
            synthese_net["ijss_brut"] = float(ijss_block.get("ijss_theorique") or 0)
        elif synthese_net.get("subrogation_active"):
            synthese_net["ijss_source"] = "theorique"
            synthese_net["ijss_brut"] = float(
                ijss_block.get("ijss_theorique") or synthese_net.get("ijss_subrogees") or 0
            )
        if synthese_net.get("ijss_brut"):
            from app.modules.payroll.engine.ijss_bulletin import compute_ijss_csg_lines

            _, csg_total, net_ijss = compute_ijss_csg_lines(
                float(synthese_net["ijss_brut"]),
                (getattr(contexte, "baremes", None) or {}).get("maladie"),
            )
            synthese_net["ijss_csg_total"] = csg_total
            synthese_net["ijss_net"] = net_ijss

    if not isinstance(getattr(contexte, "alertes_baremes", None), list):
        contexte.alertes_baremes = []
    from app.modules.payroll.engine.controles_convention import (
        controle_convention_collective,
        controle_net_superieur_brut,
        controle_prime_anciennete,
    )

    for alerte_cc in controle_convention_collective(contexte, salaire_brut):
        contexte.alertes_baremes.append(alerte_cc)

    existing_codes = {
        str(a.get("code"))
        for a in contexte.alertes_baremes
        if isinstance(a, dict) and a.get("code")
    }
    for alerte_pa in controle_prime_anciennete(contexte):
        if alerte_pa.get("code") not in existing_codes:
            contexte.alertes_baremes.append(alerte_pa)
            existing_codes.add(str(alerte_pa.get("code")))

    net_a_payer_val = resultats_nets.get("net_a_payer")
    if net_a_payer_val is not None:
        # Une participation/intéressement numéraire augmente légitimement le net
        # sans entrer dans le salaire_brut. Le contrôle doit comparer au brut
        # total versé, sinon il produit un faux positif (ex. MBC mai 2026).
        participation_resultats = _participation_numeraire_depuis_resultats(
            resultats_nets
        )
        brut_reference_net = salaire_brut + (
            participation_resultats
            if participation_resultats
            else _participation_brut_numeraire(details_brut)
        )
        # Les frais professionnels hors brut sont transportés comme une
        # correction nette négative d'acompte (ex. indemnité de déplacement).
        brut_reference_net += max(
            0.0, -float(resultats_nets.get("acompte_verse") or 0)
        )
        brut_reference_net += sum(
            max(0.0, float(prime.get("montant") or 0))
            for prime in primes_non_soumises
            if isinstance(prime, dict)
        )
        brut_reference_net += sum(
            max(0.0, float(prime.get("montant") or 0))
            for prime in primes_soumises_impot or []
            if isinstance(prime, dict)
        )
        for alerte_net in controle_net_superieur_brut(
            brut_reference_net, float(net_a_payer_val)
        ):
            contexte.alertes_baremes.append(alerte_net)

    alertes_baremes = contexte.alertes_baremes
    donnees_non_officielles = any(
        a.get("donnee_non_officielle") for a in alertes_baremes
    )

    bulletin = {
        "en_tete": {
            "periode": periode_formatee,
            "annee": annee,
            "mois": mois,
            "date_paiement": _calculer_date_paiement(contexte, annee, mois),
            "entreprise": {
                "raison_sociale": contexte.entreprise.get("identification", {}).get(
                    "raison_sociale"
                ),
                "siret": contexte.entreprise.get("identification", {}).get("siret"),
                "adresse": contexte.entreprise.get("identification", {}).get("adresse"),
                "naf_ape": _extraire_naf_ape(contexte.entreprise),
            },
            "salarie": {
                "nom_complet": f"{contexte.contrat.get('salarie', {}).get('prenom')} {contexte.contrat.get('salarie', {}).get('nom')}",
                "nom": contexte.contrat.get("salarie", {}).get("nom"),
                "prenom": contexte.contrat.get("salarie", {}).get("prenom"),
                "sexe": contexte.contrat.get("salarie", {}).get("sexe"),
                "matricule": contexte.contrat.get("salarie", {}).get("matricule"),
                "adresse": contexte.contrat.get("salarie", {}).get("adresse"),
                "mode_paiement": contexte.contrat.get("salarie", {}).get(
                    "mode_paiement"
                ),
                "nir": contexte.contrat.get("salarie", {}).get("nir"),
                "emploi": contexte.contrat.get("contrat", {}).get("emploi"),
                "statut": contexte.statut_salarie,
                "type_contrat": contexte.type_contrat,
                "is_alternant": contexte.is_alternant,
                "date_entree": contexte.contrat.get("contrat", {}).get("date_entree"),
                "date_anciennete": contexte.contrat.get("contrat", {}).get(
                    "seniority_reference_date"
                )
                or contexte.contrat.get("contrat", {}).get("date_entree"),
                "classification": _formater_classification(contexte.contrat),
                "classification_brute": contexte.contrat.get("remuneration", {}).get(
                    "classification_conventionnelle"
                ),
                "convention_collective": _formater_convention_collective(
                    contexte.contrat
                ),
            },
        },
        "details_conges": lignes_conges,
        "details_absences": lignes_absences,
        "details_maintien": lignes_maintien,
        "bloc_maintien": resultats_maintien or {},
        "calcul_du_brut": autres_lignes_brut,
        "arbitrage_conges": texte_arbitrage,
        "salaire_brut": salaire_brut,
        "parametres": {
            "smic_horaire": contexte.smic_horaire,
            "pss_mensuel": (contexte.baremes.get("pss", {}) or {}).get("mensuel", 0.0)
            or 0.0,
        },
        "structure_cotisations": {
            "bloc_principales": bloc_principales,
            "bloc_allegements": bloc_allegements,
            "bloc_autres_contributions": {
                "lignes": bloc_autres_contributions,
                "total": round(total_autres_contributions, 2),
            },
            "total_avant_csg_crds": {
                "libelle": "Total des retenues (avant CSG/CRDS non déductible)",
                "montant_salarial": round(total_retenues_avant_csg_nd, 2),
                "montant_patronal": round(total_patronal_avant_csg_nd, 2),
            },
            "bloc_csg_non_deductible": bloc_csg_non_deductible,
            "total_salarial": round(total_cotisations_salariales, 2),
            "total_patronal": round(total_cotisations_patronales, 2),
        },
        "cotisations_officielles": cotisations_officielles,
        "total_exonerations": total_exonerations,
        "synthese_net": synthese_net,
        "primes_non_soumises": primes_non_soumises,
        "revenus_hors_brut_imposables": list(primes_soumises_impot or []),
        "participations": resultats_nets.get("participations") or [],
        "net_a_payer": resultats_nets.get("net_a_payer"),
        "pied_de_page": {
            "cout_total_employeur": _calculer_cout_total_employeur(
                salaire_brut,
                total_cotisations_patronales,
                primes_non_soumises,
                autres_lignes_brut,
                primes_soumises_impot,
            ),
            "total_exonerations": total_exonerations,
            "solde_conges": build_solde_conges_pied_de_page(
                _extraire_employee_id(contexte), annee, mois
            ),
            "mentions_legales": {
                "conservation": "Ce bulletin de paie doit être conservé sans limitation de durée.",
                "information": "Pour en savoir plus : www.service-public.fr",
            },
            "cumuls_annuels": {
                "_commentaire": "Ces valeurs seraient calculées sur la base des bulletins précédents.",
                "brut_cumule": 0.0,
                "net_imposable_cumule": 0.0,
                "heures_supplementaires_cumulees": 0,
            },
        },
        "alertes_baremes": alertes_baremes,
        "donnees_non_officielles": donnees_non_officielles,
    }
    log_payroll_debug(logger, 'INFO: Bulletin de paie final assemblé.')
    return bulletin


def creer_bulletin_sortie(
    contexte: ContextePaie,
    salaire_brut: float,
    details_brut: List[Dict[str, Any]],
    lignes_cotisations: List[Dict[str, Any]],
    resultats_nets: Dict[str, float],
    primes_non_soumises: List[Dict[str, Any]],
    indemnites_sortie: Dict[str, Any],
    annee: int,
    mois: int,
    resultats_maintien: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Assemble un bulletin de paie de sortie incluant les indemnités de fin de contrat.

    Les indemnités de sortie sont ajoutées après le salaire brut, avec distinction entre:
    - Indemnités soumises à cotisations (préavis, congés payés)
    - Indemnités exonérées (licenciement, rupture conventionnelle)

    Args:
        contexte: Contexte de paie
        salaire_brut: Salaire brut du mois
        details_brut: Lignes de détail du brut
        lignes_cotisations: Lignes de cotisations sociales
        resultats_nets: Calculs des nets
        primes_non_soumises: Primes non soumises
        indemnites_sortie: Dictionnaire contenant les indemnités calculées
        annee: Année du bulletin
        mois: Mois du bulletin

    Returns:
        Dict contenant le bulletin complet avec indemnités de sortie
    """
    log_payroll_debug(logger, 'INFO: Assemblage du bulletin de sortie avec indemnités...')

    # Commencer par créer un bulletin normal
    bulletin_base = creer_bulletin_final(
        contexte,
        salaire_brut,
        details_brut,
        lignes_cotisations,
        resultats_nets,
        primes_non_soumises,
        annee,
        mois,
        resultats_maintien=resultats_maintien,
    )

    # Préparer les lignes d'indemnités de sortie
    lignes_indemnites_soumises = []
    lignes_indemnites_exonerees = []

    # Indemnité de préavis (soumise à cotisations)
    if indemnites_sortie.get("indemnite_preavis"):
        ind_preavis = indemnites_sortie["indemnite_preavis"]
        if ind_preavis.get("montant", 0) > 0:
            lignes_indemnites_soumises.append(
                {
                    "libelle": "Indemnité compensatrice de préavis",
                    "description": ind_preavis.get("description", ""),
                    "calcul": ind_preavis.get("calcul", ""),
                    "gain": round(ind_preavis["montant"], 2),
                    "nature": "soumise",
                }
            )

    # Indemnité de congés payés (soumise à cotisations)
    if indemnites_sortie.get("indemnite_conges"):
        ind_conges = indemnites_sortie["indemnite_conges"]
        if ind_conges.get("montant", 0) > 0:
            lignes_indemnites_soumises.append(
                {
                    "libelle": "Indemnité compensatrice de congés payés",
                    "description": ind_conges.get("description", ""),
                    "calcul": ind_conges.get("calcul", ""),
                    "gain": round(ind_conges["montant"], 2),
                    "nature": "soumise",
                }
            )

    # Indemnité légale de licenciement (exonérée dans la limite légale)
    if indemnites_sortie.get("indemnite_licenciement"):
        ind_lic = indemnites_sortie["indemnite_licenciement"]
        if ind_lic.get("montant", 0) > 0:
            lignes_indemnites_exonerees.append(
                {
                    "libelle": "Indemnité légale de licenciement",
                    "description": ind_lic.get(
                        "description", "Article L1234-9 du Code du travail"
                    ),
                    "calcul": ind_lic.get("calcul", ""),
                    "montant": round(ind_lic["montant"], 2),
                    "nature": "exoneree",
                    "note": "Exonérée de cotisations sociales dans la limite légale",
                }
            )

    # Indemnité de rupture conventionnelle (exonérée dans la limite légale)
    if indemnites_sortie.get("indemnite_rupture_conventionnelle"):
        ind_rc = indemnites_sortie["indemnite_rupture_conventionnelle"]
        if ind_rc.get("montant_negocie", 0) > 0:
            lignes_indemnites_exonerees.append(
                {
                    "libelle": "Indemnité de rupture conventionnelle",
                    "description": ind_rc.get("description", "Indemnité négociée"),
                    "calcul": ind_rc.get("calcul", ""),
                    "montant": round(ind_rc["montant_negocie"], 2),
                    "nature": "exoneree",
                    "note": "Exonérée de cotisations sociales dans la limite légale",
                }
            )

    # Calculer les totaux des indemnités
    total_indemnites_soumises = sum(
        ligne["gain"] for ligne in lignes_indemnites_soumises
    )
    total_indemnites_exonerees = sum(
        ligne["montant"] for ligne in lignes_indemnites_exonerees
    )

    # Recalculer le brut total incluant les indemnités soumises
    brut_total_avec_indemnites = salaire_brut + total_indemnites_soumises

    # Recalculer le net à payer incluant toutes les indemnités
    net_a_payer_final = (
        resultats_nets.get("net_a_payer", 0)
        + total_indemnites_soumises
        + total_indemnites_exonerees
    )

    # Ajouter les sections d'indemnités au bulletin
    bulletin_base["indemnites_sortie"] = {
        "lignes_soumises": lignes_indemnites_soumises,
        "lignes_exonerees": lignes_indemnites_exonerees,
        "total_soumises": round(total_indemnites_soumises, 2),
        "total_exonerees": round(total_indemnites_exonerees, 2),
        "total_general": round(
            total_indemnites_soumises + total_indemnites_exonerees, 2
        ),
    }

    # Mettre à jour les totaux du bulletin
    bulletin_base["salaire_brut_avec_indemnites_soumises"] = round(
        brut_total_avec_indemnites, 2
    )
    bulletin_base["net_a_payer"] = round(net_a_payer_final, 2)
    bulletin_base["is_bulletin_sortie"] = True

    ind_conges = indemnites_sortie.get("indemnite_conges") or {}
    details_iccp = ind_conges.get("details") or {}
    if details_iccp:
        maintien = details_iccp.get("indemnite_maintien", 0) or 0
        dixieme = details_iccp.get("indemnite_dixieme", 0) or 0
        montant = ind_conges.get("montant", 0) or 0
        methode = details_iccp.get("methode_retenue", "maintien")
        if methode == "dixieme":
            bulletin_base["arbitrage_conges"] = (
                f"L'indemnité compensatrice de congés payés a été calculée selon la "
                f"règle du 1/10e ({montant:.2f} €), plus favorable que le maintien "
                f"de salaire ({maintien:.2f} €)."
            )
        elif methode == "l1243_8":
            bulletin_base["arbitrage_conges"] = (
                f"L'indemnité compensatrice de congés payés (CDD) retenue : "
                f"{montant:.2f} € (règle des 10 % de la rémunération totale du contrat)."
            )
        else:
            bulletin_base["arbitrage_conges"] = (
                f"L'indemnité compensatrice de congés payés a été calculée selon le "
                f"maintien de salaire ({montant:.2f} €), plus favorable que la "
                f"règle du 1/10e ({dixieme:.2f} €)."
            )

    # Ajouter une note explicative
    bulletin_base["note_sortie"] = (
        "BULLETIN DE SOLDE DE TOUT COMPTE - "
        "Ce bulletin inclut les indemnités de fin de contrat. "
        "Les indemnités légales de licenciement et de rupture conventionnelle "
        "sont exonérées de cotisations sociales dans la limite du montant légal."
    )

    # Recalculer le coût total employeur
    total_primes_non_soumises = sum(
        p.get("montant", 0.0) or 0.0 for p in primes_non_soumises
    )
    total_cotisations_patronales = sum(
        row.get("montant_patronal", 0.0) or 0.0 for row in lignes_cotisations
    )

    bulletin_base["pied_de_page"]["cout_total_employeur"] = round(
        brut_total_avec_indemnites
        + total_cotisations_patronales
        + total_primes_non_soumises
        + total_indemnites_exonerees,
        2,
    )

    log_payroll_debug(logger, f'INFO: Bulletin de sortie assemblé - Indemnités totales: {round(total_indemnites_soumises + total_indemnites_exonerees, 2)} €')

    return bulletin_base
