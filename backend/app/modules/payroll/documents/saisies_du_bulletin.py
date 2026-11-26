"""Les saisies du mois rangées pour le moteur : une seule fonction, deux générateurs.

Le générateur des heures et celui du forfait jours rangeaient chacun les saisies
du mois (primes, frais, participations, IJSS, acomptes) avec leur propre copie
de la même boucle. Les copies avaient divergé : au forfait, une prime perdait
son lien au catalogue (`catalog_prime_id`), son code d'export et son type
« panier ». Audit du 17/11/2026 : c'est la famille d'erreur de Lyon (une règle
branchée d'un seul côté). Les deux générateurs appellent maintenant celle-ci ;
le test de parité le vérifie.
"""

from __future__ import annotations

from typing import Any


def ranger_les_saisies(
    lignes: list[dict[str, Any]] | None,
    saisies_data: dict[str, Any],
    company_data: dict[str, Any],
) -> tuple[float, list[dict[str, Any]]]:
    """Range les saisies du mois dans `saisies_data` (primes, participations,
    IJSS, corrections) et rend (acomptes et corrections du net, reports de net
    négatif). Mêmes règles qu'au générateur des heures, ligne pour ligne.
    """
    # Import tardif : le générateur des heures importe ce module.
    from app.modules.ijss_tracking.domain.saisie_ijss import est_saisie_ijss_validees
    from app.modules.monthly_inputs.domain.rules import est_saisie_retiree
    from app.modules.payroll.documents.payslip_generator import (
        _is_cantine_input,
        _is_frais_pro_non_soumis_input,
        _is_heures_sup_conjoncturelle_input,
        _is_ijss_override_input,
        _is_net_a_payer_only_correction_input,
        _is_participation_numeraire_input,
        _is_participation_pee_input,
        entree_de_frais_non_soumis,
    )
    from app.modules.payroll.domain.report_nap_negatif import reports_du_mois
    from app.modules.payroll.engine.corrections_manuelles import ranger_correction_manuelle

    acomptes = 0.0
    reports_nap_negatif: list[dict[str, Any]] = []
    for row in lignes or []:
        if est_saisie_retiree(row):
            # Prime de règle automatique retirée : gardée à 0 pour ne pas
            # revenir, elle n'est pas une ligne du bulletin.
            continue
        if ranger_correction_manuelle(row, saisies_data):
            # Régularisation de cotisation ou correction de ligne saisie depuis
            # le bulletin : ce n'est pas une prime, le moteur la rejoue.
            continue
        if est_saisie_ijss_validees(row):
            # Montant validé au suivi IJSS : les IJSS subrogées du mois, rien d'autre.
            saisies_data["ijss_brut_override"] = abs(float(row["amount"]))
            continue
        if _is_heures_sup_conjoncturelle_input(row):
            continue
        if _is_cantine_input(row):
            # Retenue repas : réduit MNS + net à payer, hors brut/imposable.
            saisies_data["primes"].append({
                "prime_id": row.get("catalog_prime_id") or row["name"].replace(" ", "_").lower(),
                "libelle": row["name"],
                "montant": float(row["amount"]),
                "soumise_a_cotisations": False,
                "soumise_a_impot": False,
            })
            continue
        if _is_net_a_payer_only_correction_input(row):
            acomptes += -float(row["amount"])
            reports_nap_negatif.extend(reports_du_mois([row]))
            continue
        if _is_frais_pro_non_soumis_input(row):
            # Ligne à son libellé, au net, hors MNS (D1), sauf panier selon le réglage (R-333).
            saisies_data["primes"].append(entree_de_frais_non_soumis(row, company_data))
            continue
        if _is_ijss_override_input(row):
            saisies_data["ijss_brut_override"] = abs(float(row["amount"]))
            saisies_data["maintien_base_ouvree"] = True
            continue
        if _is_participation_pee_input(row):
            saisies_data.setdefault("participations", []).append(
                {
                    "libelle": row["name"],
                    "brut": float(row["amount"]),
                    "part_pee": float(row["amount"]),
                }
            )
            continue
        if _is_participation_numeraire_input(row):
            saisies_data.setdefault("participations", []).append(
                {
                    "libelle": row["name"],
                    "brut": float(row["amount"]),
                }
            )
            continue
        saisies_data["primes"].append(entree_de_prime(row))
    return acomptes, reports_nap_negatif


def entree_de_prime(row: dict[str, Any]) -> dict[str, Any]:
    """Une prime saisie, avec son lien au catalogue, son code d'export et ce que
    le moteur lit pour le plafond d'un panier (quantité, situation du repas)."""
    catalog_id = row.get("catalog_prime_id")
    prime_id = catalog_id or row["name"].replace(" ", "_").lower()
    prime_entry: dict[str, Any] = {
        "prime_id": prime_id,
        "libelle": row["name"],
        "montant": row["amount"],
        "soumise_a_cotisations": row.get("is_socially_taxed", True),
        "soumise_a_impot": row.get("is_taxable", True),
    }
    if row.get("id"):
        prime_entry["saisie_id"] = str(row["id"])
    if row.get("export_code"):
        prime_entry["export_code"] = row["export_code"]
        prime_entry["libelle"] = f"{row['name']} ({row['export_code']})"
    if row.get("payroll_quantity") is not None:
        prime_entry["quantity"] = float(row["payroll_quantity"])
    # Sans ces deux clés, valeur_unitaire et le plafond situationnel
    # seraient du code mort côté moteur.
    if row.get("quantity_kind"):
        prime_entry["quantity_kind"] = row["quantity_kind"]
    if row.get("situation_repas"):
        prime_entry["situation_repas"] = row["situation_repas"]
    # L'indemnité d'activité partielle calculée au calendrier (jamais une saisie
    # à la main) : de quoi la recalculer avec la prime d'ancienneté (R5122-18).
    from app.modules.activite_partielle.domain.calcul import CLE_CALCUL_INDEMNITE

    if isinstance(row.get(CLE_CALCUL_INDEMNITE), dict):
        prime_entry[CLE_CALCUL_INDEMNITE] = dict(row[CLE_CALCUL_INDEMNITE])
    if catalog_id and ("panier" in str(catalog_id).lower() or "repas" in str(catalog_id).lower()):
        prime_entry["type"] = "panier"
    return prime_entry
