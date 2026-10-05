"""Extraction comptable depuis payslip_data (formats bulletin récents et legacy)."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def extract_pas_amount(synthese_net: Any) -> float:
    if not isinstance(synthese_net, dict):
        return 0.0
    pas_obj = synthese_net.get("impot_prelevement_a_la_source")
    if isinstance(pas_obj, dict):
        return float(pas_obj.get("montant", 0) or 0)
    legacy = synthese_net.get("impot_preleve_a_la_source")
    if legacy is not None:
        return float(legacy or 0)
    return 0.0


def _flatten_cotisation_lines(structure_cotisations: Dict[str, Any]) -> List[Dict[str, Any]]:
    lines: List[Dict[str, Any]] = []

    legacy = structure_cotisations.get("cotisations")
    if isinstance(legacy, list) and legacy:
        return [c for c in legacy if isinstance(c, dict)]

    for key in ("bloc_principales", "bloc_allegements", "bloc_csg_non_deductible"):
        bloc = structure_cotisations.get(key)
        if isinstance(bloc, list):
            lines.extend(c for c in bloc if isinstance(c, dict))

    autres = structure_cotisations.get("bloc_autres_contributions")
    if isinstance(autres, dict):
        extra = autres.get("lignes")
        if isinstance(extra, list):
            lines.extend(c for c in extra if isinstance(c, dict))

    return lines


#: Marque l'élément tiré de `synthese_net.acompte_verse`, que les variables du
#: mois permettent de décomposer.
SOURCE_ACOMPTE_VERSE = "acompte_verse"


def _retenues_des_modules(payslip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Saisies, avances et prêts retenus par les modules, lus sur le bulletin.

    Le bulletin fait foi : ses tables d'historique peuvent diverger (bulletin
    supprimé puis refait, écriture d'historique en échec) et ne connaissent
    pas le filtre de salariés de l'export.
    """
    from app.modules.exports.domain.accounting_plan import (
        FAMILLE_AVANCE,
        FAMILLE_INTERETS_PRET,
        FAMILLE_PRET,
        FAMILLE_SAISIE,
    )

    elements: List[Dict[str, Any]] = []

    saisies = payslip_data.get("retenues_saisies")
    if isinstance(saisies, dict):
        detail = [s for s in saisies.get("saisies") or [] if isinstance(s, dict)]
        if not detail and float(saisies.get("total_preleve", 0) or 0):
            detail = [{"montant": saisies.get("total_preleve")}]
        for saisie in detail:
            montant = float(saisie.get("montant", 0) or 0)
            if montant == 0:
                continue
            creancier = str(saisie.get("creditor_name") or "").strip()
            element: Dict[str, Any] = {
                "famille": FAMILLE_SAISIE,
                "libelle": "Saisie sur salaire" + (f" — {creancier}" if creancier else ""),
                "montant": -montant,
            }
            if saisie.get("type"):
                element["type_saisie"] = str(saisie["type"])
            elements.append(element)

    avances = payslip_data.get("remboursements_avances")
    if isinstance(avances, dict):
        detail = [a for a in avances.get("avances") or [] if isinstance(a, dict)]
        if not detail and float(avances.get("total_rembourse", 0) or 0):
            detail = [{"montant": avances.get("total_rembourse")}]
        for avance in detail:
            montant = float(avance.get("montant", 0) or 0)
            if montant == 0:
                continue
            element = {
                "famille": FAMILLE_AVANCE,
                "libelle": str(avance.get("type_label") or "Avance sur salaire"),
                "montant": -montant,
            }
            # Le versement de l'avance a été passé sur ce compte : le
            # remboursement doit solder le même.
            if avance.get("compte"):
                element["compte"] = str(avance["compte"])
            elements.append(element)

    prets = payslip_data.get("remboursements_prets")
    if isinstance(prets, dict):
        capital = float(prets.get("total_capital", 0) or 0)
        interets = float(prets.get("total_interets", 0) or 0)
        if capital == 0 and interets == 0:
            capital = float(prets.get("total_rembourse", 0) or 0)
        if capital != 0:
            elements.append(
                {
                    "famille": FAMILLE_PRET,
                    "libelle": "Remboursement prêt employeur",
                    "montant": -capital,
                }
            )
        # L'intérêt est un produit de l'employeur, pas un remboursement de la
        # créance : il ne va pas au compte du prêt.
        if interets != 0:
            elements.append(
                {
                    "famille": FAMILLE_INTERETS_PRET,
                    "libelle": "Intérêts prêt employeur",
                    "montant": -interets,
                }
            )

    return elements


def extract_elements_hors_brut(payslip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Éléments qui s'ajoutent au net à payer sans transiter par le brut.

    Primes non soumises, retenues, et participation. Sans contrepartie au débit,
    l'OD est déséquilibrée d'exactement leur total — c'est la cause de l'écart
    constaté sur les OD générées jusqu'ici.

    Chaque élément porte sa `famille`, clé stable de rattachement comptable :
    `prime_id` et le libellé sont du texte libre saisi par la RH et ne peuvent
    pas servir de clé.
    """
    from app.modules.exports.domain.accounting_plan import (
        FAMILLE_ACOMPTE_VERSE,
        FAMILLE_AVANCE_PARTICIPATION,
        FAMILLE_PARTICIPATION,
        FAMILLE_PARTICIPATION_PEE,
        FAMILLE_TRANSPORT,
        resolve_element_family,
    )

    elements: List[Dict[str, Any]] = []
    synthese = payslip_data.get("synthese_net")
    if not isinstance(synthese, dict):
        synthese = {}

    retenues_reprises = payslip_data.get("retenues_sur_net")
    if isinstance(retenues_reprises, list):
        # Bulletin repris de l'ancien logiciel : chaque retenue sur le net y est
        # détaillée (acompte, saisie, report d'un net négatif). `acompte_verse`
        # y répète l'acompte : le lire aussi le compterait deux fois.
        for retenue in retenues_reprises:
            if not isinstance(retenue, dict) or retenue.get("sans_effet_sur_le_net"):
                continue
            montant = float(retenue.get("montant", 0) or 0)
            if montant == 0:
                continue
            libelle = str(retenue.get("libelle") or "")
            elements.append(
                {
                    "famille": resolve_element_family(libelle),
                    "libelle": libelle or "Retenue sur le net",
                    "montant": -montant,
                }
            )
    else:
        # Ce que les variables du mois retiennent sur le net, additionné par le
        # moteur (acompte, saisie, report d'un net négatif…). Décomposé plus
        # loin d'après les variables du mois (merge_monthly_inputs_hors_brut).
        acompte = float(synthese.get("acompte_verse", 0) or 0)
        if acompte != 0:
            elements.append(
                {
                    "famille": FAMILLE_ACOMPTE_VERSE,
                    "libelle": "Acompte déjà versé",
                    "montant": -acompte,
                    "source": SOURCE_ACOMPTE_VERSE,
                }
            )

    elements.extend(_retenues_des_modules(payslip_data))

    # Prise en charge de l'abonnement de transport prévue au contrat : ajoutée
    # au net par le moteur, hors brut.
    transport = float(synthese.get("remboursement_transport", 0) or 0)
    if transport != 0:
        elements.append(
            {
                "famille": FAMILLE_TRANSPORT,
                "libelle": "Prise en charge des frais de transport",
                "montant": transport,
            }
        )

    # Indemnités de rupture exonérées : ajoutées au net d'un bulletin de sortie,
    # hors brut (les indemnités soumises y sont déjà).
    sortie = payslip_data.get("indemnites_sortie")
    if isinstance(sortie, dict):
        for ligne in sortie.get("lignes_exonerees") or []:
            if not isinstance(ligne, dict):
                continue
            montant = float(ligne.get("montant", 0) or 0)
            if montant == 0:
                continue
            libelle = str(ligne.get("libelle") or "Indemnité de rupture")
            elements.append(
                {
                    "famille": resolve_element_family(libelle),
                    "libelle": libelle,
                    "montant": montant,
                }
            )

    # Revenus non soumis à cotisations mais imposables : indemnité d'activité
    # partielle, IJSS imposables… Le bulletin les expose ici depuis l'ajout de la
    # clé ; les bulletins plus anciens ne la portent pas, d'où le repli sur les
    # saisies mensuelles (voir merge_monthly_inputs_hors_brut).
    for revenu in payslip_data.get("revenus_hors_brut_imposables") or []:
        if not isinstance(revenu, dict):
            continue
        montant = float(revenu.get("montant", 0) or 0)
        if montant == 0:
            continue
        libelle = str(revenu.get("libelle") or "")
        elements.append(
            {
                "famille": resolve_element_family(libelle, revenu.get("prime_id")),
                "libelle": libelle or "Revenu hors brut imposable",
                "montant": montant,
            }
        )

    for prime in payslip_data.get("primes_non_soumises") or []:
        if not isinstance(prime, dict):
            continue
        montant = float(prime.get("montant", 0) or 0)
        if montant == 0:
            continue
        libelle = str(prime.get("libelle") or "")
        prime_id = prime.get("prime_id")
        elements.append(
            {
                "famille": resolve_element_family(libelle, prime_id),
                "libelle": libelle or "Élément hors brut",
                "montant": montant,
            }
        )

    participations = payslip_data.get("participations") or []
    if not participations:
        # Certains bulletins ne portent la participation que dans `calcul_du_brut`,
        # en ligne informative — elle est exonérée, donc hors du brut soumis.
        # Observé sur 44 bulletins de Mont Blanc et 3 de Cartol en mai 2026 ; sans
        # cette reprise, l'OD est déséquilibrée de leur montant.
        for ligne in payslip_data.get("calcul_du_brut") or []:
            if not isinstance(ligne, dict) or not ligne.get("is_informative"):
                continue
            gain = float(ligne.get("gain", 0) or 0)
            if gain == 0:
                continue
            libelle = str(ligne.get("libelle") or "Élément informatif")
            elements.append(
                {
                    "famille": resolve_element_family(libelle),
                    "libelle": libelle,
                    "montant": gain,
                }
            )
            # Participation placée sur un plan d'épargne : elle ne va pas au net
            # à payer. Seule la CSG/CRDS (9,7 %) est prélevée sur le salaire, et
            # figure déjà parmi les cotisations.
            if "PEE" in libelle.upper():
                elements.append(
                    {
                        "famille": FAMILLE_PARTICIPATION_PEE,
                        "libelle": f"{libelle} — part placée sur un plan d'épargne",
                        "montant": -round(gain * (1 - 0.097), 2),
                    }
                )

    for part in participations:
        if not isinstance(part, dict):
            continue
        brut = float(part.get("brut", 0) or 0)
        part_pee = float(part.get("part_pee", 0) or 0)
        csg_total = float(part.get("csg_total", 0) or 0)
        libelle = str(part.get("libelle") or "Participation")
        # Certaines lignes de participation placée sur un plan d'épargne portent
        # l'information dans leur seul libellé, `part_pee` restant à zéro. Sans
        # cette reprise, le montant est traité comme versé au salarié.
        if part_pee == 0 and "PEE" in libelle.upper():
            part_pee = brut
        # Le versement éteint la dette de participation provisionnée à la clôture
        # précédente ; la CSG figure déjà parmi les cotisations.
        if brut != 0:
            elements.append(
                {
                    "famille": FAMILLE_PARTICIPATION,
                    "libelle": libelle,
                    "montant": brut,
                }
            )
        # Acompte de participation déjà versé : retenu du net, il solde le compte
        # de l'avance.
        acompte_part = float(part.get("acompte", 0) or 0)
        if acompte_part != 0:
            elements.append(
                {
                    "famille": FAMILLE_AVANCE_PARTICIPATION,
                    "libelle": f"{libelle} — acompte déjà versé",
                    "montant": -acompte_part,
                }
            )
        if part_pee != 0:
            # `part_pee` est brut de CSG : la contribution est prélevée avant le
            # placement. Sans cette déduction, l'OD est déséquilibrée du montant
            # de la CSG portant sur la part placée.
            csg_sur_part_pee = csg_total * (part_pee / brut) if brut else 0.0
            montant_place = part_pee - csg_sur_part_pee
            elements.append(
                {
                    "famille": FAMILLE_PARTICIPATION_PEE,
                    "libelle": f"{libelle} — part placée sur un plan d'épargne",
                    "montant": -round(montant_place, 2),
                }
            )

    return elements


def extract_cotisations_from_payslip(
    payslip_data: Dict[str, Any],
) -> Tuple[float, float, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Retourne (cot_sal, cot_pat, lignes détail, meta diagnostic).
    """
    meta: Dict[str, Any] = {"format": "unknown", "warnings": []}
    sc = payslip_data.get("structure_cotisations")
    if not isinstance(sc, dict):
        meta["warnings"].append("structure_cotisations absente ou invalide")
        return 0.0, 0.0, [], meta

    legacy_list = sc.get("cotisations")
    if isinstance(legacy_list, list) and legacy_list:
        meta["format"] = "legacy_cotisations_list"
        cot_sal = sum(float(c.get("montant_salarial", 0) or 0) for c in legacy_list if isinstance(c, dict))
        cot_pat = sum(float(c.get("montant_patronal", 0) or 0) for c in legacy_list if isinstance(c, dict))
        return cot_sal, cot_pat, [c for c in legacy_list if isinstance(c, dict)], meta

    meta["format"] = "bulletin_blocs"
    cot_sal = float(sc.get("total_salarial", 0) or 0)
    cot_pat = float(sc.get("total_patronal", 0) or 0)
    detail = _flatten_cotisation_lines(sc)

    if cot_sal == 0 and cot_pat == 0 and not detail:
        meta["warnings"].append(
            "total_salarial/total_patronal à 0 et aucune ligne de cotisation extraite"
        )

    return cot_sal, cot_pat, detail, meta


def _decomposer_acompte_verse(
    elements: List[Dict[str, Any]],
    saisies: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Remplace `acompte_verse` par les variables du mois qui le composent.

    Le moteur additionne dans `acompte_verse` tout ce que les variables du mois
    retiennent sur le net (acompte, saisie, report d'un net négatif…) ou y
    ajoutent hors assiette (panier, déplacement). Chacun a son compte : une
    saisie va au 427, pas au compte des acomptes.

    Les variables candidates sont celles que le bulletin ne porte pas déjà
    ailleurs. On ne décompose que si elles redonnent l'acompte au centime ;
    sinon (variables changées depuis le calcul) l'acompte reste entier.
    """
    from app.modules.exports.domain.accounting_plan import (
        FAMILLE_ACOMPTE_VERSE,
        FAMILLE_INCONNUE,
        resolve_element_family,
    )

    acompte = next(
        (e for e in elements if e.get("source") == SOURCE_ACOMPTE_VERSE), None
    )
    if acompte is None:
        return elements

    deja_au_bulletin = {
        round(float(e.get("montant", 0) or 0), 2) for e in elements if e is not acompte
    }
    composantes: List[Dict[str, Any]] = []
    for saisie in saisies:
        montant = round(float(saisie.get("amount", 0) or 0), 2)
        if montant == 0 or montant in deja_au_bulletin:
            continue
        libelle = str(saisie.get("name") or "")
        famille = resolve_element_family(libelle)
        composantes.append(
            {
                "famille": FAMILLE_ACOMPTE_VERSE if famille == FAMILLE_INCONNUE else famille,
                "libelle": libelle or "Retenue sur le net",
                "montant": montant,
            }
        )

    attendu = round(float(acompte.get("montant", 0) or 0), 2)
    if not composantes or round(sum(c["montant"] for c in composantes), 2) != attendu:
        return elements
    return [e for e in elements if e is not acompte] + composantes


def merge_monthly_inputs_hors_brut(
    elements: List[Dict[str, Any]],
    saisies: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Complète les éléments du bulletin par les saisies mensuelles absentes.

    Certaines saisies non soumises à cotisations sont incluses dans le net à
    payer sans être recopiées dans `payslip_data` — l'indemnité d'activité
    partielle notamment, 17 510,65 € sur LEWIS en juin 2026. Sans elles, l'OD
    est déséquilibrée de leur montant.

    Deux sources de double comptage sont écartées : les saisies déjà présentes
    dans le bulletin (même famille et même montant), et celles dont la famille
    est portée par un autre champ — `synthese_net.acompte_verse` agrège les
    acomptes et les saisies sur salaire.
    """
    from app.modules.exports.domain.accounting_plan import (
        FAMILLE_INCONNUE,
        FAMILLES_DEJA_COUVERTES,
        resolve_element_family,
    )

    elements = _decomposer_acompte_verse(elements, saisies)

    # Comparaison sur le montant seul : les libellés du bulletin et de la saisie
    # ne coïncident pas toujours, alors que le montant, lui, est le même.
    montants_presents = {
        round(float(e.get("montant", 0) or 0), 2) for e in elements
    }
    complement: List[Dict[str, Any]] = []

    for saisie in saisies:
        montant = float(saisie.get("amount", 0) or 0)
        if montant == 0:
            continue
        libelle = str(saisie.get("name") or "")
        famille = resolve_element_family(libelle)
        if famille in FAMILLES_DEJA_COUVERTES:
            continue
        # Une saisie non rattachée est le plus souvent déjà reflétée dans le
        # bulletin sous un autre libellé : la reprendre créerait un doublon.
        # On ne complète que ce qu'on sait identifier.
        if famille == FAMILLE_INCONNUE:
            continue
        if round(montant, 2) in montants_presents:
            continue
        complement.append(
            {
                "famille": famille,
                "libelle": libelle or "Saisie mensuelle",
                "montant": montant,
            }
        )

    return elements + complement
