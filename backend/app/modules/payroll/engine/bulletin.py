# moteur_paie/bulletin.py

import sys
from .contexte import ContextePaie
from typing import Dict, Any, List


def creer_bulletin_final(
    contexte: ContextePaie,
    salaire_brut: float,
    details_brut: List[Dict[str, Any]],
    lignes_cotisations: List[Dict[str, Any]],
    resultats_nets: Dict[str, float],
    primes_non_soumises: List[Dict[str, Any]],
    annee: int,
    mois: int,
) -> Dict[str, Any]:
    """
    Assemble tous les éléments calculés en une structure de données finale
    qui respecte l'ordre d'affichage désiré sur le bulletin.
    """
    print("INFO: Assemblage et tri du bulletin de paie final...", file=sys.stderr)

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

    total_primes_non_soumises = sum(
        p.get("montant", 0.0) or 0.0 for p in primes_non_soumises
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

    bulletin = {
        "en_tete": {
            "periode": periode_formatee,
            "entreprise": {
                "raison_sociale": contexte.entreprise.get("identification", {}).get(
                    "raison_sociale"
                ),
                "siret": contexte.entreprise.get("identification", {}).get("siret"),
                "adresse": contexte.entreprise.get("identification", {}).get("adresse"),
            },
            "salarie": {
                "nom_complet": f"{contexte.contrat.get('salarie', {}).get('prenom')} {contexte.contrat.get('salarie', {}).get('nom')}",
                "nir": contexte.contrat.get("salarie", {}).get("nir"),
                "emploi": contexte.contrat.get("contrat", {}).get("emploi"),
                "statut": contexte.statut_salarie,
                "date_entree": contexte.contrat.get("contrat", {}).get("date_entree"),
            },
        },
        "details_conges": lignes_conges,
        "details_absences": lignes_absences,
        "calcul_du_brut": autres_lignes_brut,
        "arbitrage_conges": texte_arbitrage,
        "salaire_brut": salaire_brut,
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
        "synthese_net": {
            "net_social_avant_impot": resultats_nets.get("net_social"),
            "net_imposable": resultats_nets.get("net_imposable"),
            "impot_prelevement_a_la_source": {
                "base": resultats_nets.get("net_imposable"),
                "taux": contexte.contrat.get("specificites_paie", {})
                .get("prelevement_a_la_source", {})
                .get("taux", 0.0),
                "montant": resultats_nets.get("montant_impot_pas"),
            },
            "remboursement_transport": resultats_nets.get("remboursement_transport"),
            "acompte_verse": resultats_nets.get(
                "acompte_verse", 0.0
            ),  # Montant des avances déduites
        },
        "primes_non_soumises": primes_non_soumises,
        "net_a_payer": resultats_nets.get("net_a_payer"),
        "pied_de_page": {
            "cout_total_employeur": round(
                salaire_brut + total_cotisations_patronales + total_primes_non_soumises,
                2,
            ),
            "cumuls_annuels": {
                "_commentaire": "Ces valeurs seraient calculées sur la base des bulletins précédents.",
                "brut_cumule": 0.0,
                "net_imposable_cumule": 0.0,
                "heures_supplementaires_cumulees": 0,
            },
        },
    }
    print("INFO: Bulletin de paie final assemblé.", file=sys.stderr)
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
    print("INFO: Assemblage du bulletin de sortie avec indemnités...", file=sys.stderr)

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

    print(
        f"INFO: Bulletin de sortie assemblé - Indemnités totales: {round(total_indemnites_soumises + total_indemnites_exonerees, 2)} €",
        file=sys.stderr,
    )

    return bulletin_base
