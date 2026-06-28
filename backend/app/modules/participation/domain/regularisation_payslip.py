"""Construction des données d'un bulletin de régularisation « participation ».

Régime social/fiscal de la participation aux bénéfices (BOSS / BOFiP, art. L3325-1
et s. du Code du travail) :

- **Exonérée de toutes cotisations** sociales (salariales ET patronales) : ce n'est
  pas du salaire.
- **Soumise à CSG/CRDS au taux global de 9,7 %** (CSG 9,2 % + CRDS 0,5 %), sans
  abattement, dès le premier euro, sur la **totalité** des sommes (part numéraire
  ET part placée sur PEE). La CSG est **non déductible** ici.
- Part **numéraire** (versement immédiat) : **imposable** à l'impôt sur le revenu.
- Part **PEE** : **exonérée** d'impôt sur le revenu (blocage 5 ans).

Ce module ne calcule donc **aucune** cotisation classique : il s'appuie sur les
montants déjà arrêtés au moment de la campagne (brut, CSG, net) et construit une
structure `payslip_data` minimale, compatible avec le rendu PDF dédié et l'export
DSN simplifié (brut, net imposable, cotisations CSG).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.participation.domain.bulletin_rules import (
    CSG_DEDUCTIBLE_RATE,
    CSG_NON_DEDUCTIBLE_RATE,
    dispositif_label,
)

REGULARISATION_KIND = "regularisation_participation"

_MOIS_FR = [
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


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _periode_label(year: int, month: int) -> str:
    if 1 <= month <= 12:
        return f"{_MOIS_FR[month - 1]} {year}"
    return f"{month:02d}/{year}"


def build_regularisation_participation_payslip_data(
    *,
    bulletin: Dict[str, Any],
    employee: Dict[str, Any],
    company: Dict[str, Any],
    year: int,
    month: int,
    exercise_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Construit la structure `payslip_data` d'un bulletin de régularisation participation.

    `bulletin` est une ligne `participation_bulletins` (montants déjà arrêtés :
    brut, CSG déductible/non déductible, répartition numéraire/PEE, acompte).
    """
    dispositif = str(bulletin.get("dispositif_type") or "participation")
    label = dispositif_label(dispositif)
    exercise = str(exercise_label or bulletin.get("exercise_label") or "").strip()
    exercise_suffix = f" {exercise}" if exercise else ""

    gross = _money(bulletin.get("gross_amount"))
    csg_nd = _money(bulletin.get("csg_non_deductible"))
    csg_ded = _money(bulletin.get("csg_deductible"))
    csg_total = round(csg_nd + csg_ded, 2)

    advance = _money(bulletin.get("advance_amount"))
    advance_label = str(bulletin.get("advance_label") or "")

    choice_type = bulletin.get("choice_type")
    # Numéraire = part versée (imposable IR) ; PEE = part placée (exonérée IR).
    cash_net = bulletin.get("choice_cash_amount")
    if cash_net is None:
        cash_net = bulletin.get("cash_amount")
    cash_net = _money(cash_net)
    pee_net = _money(bulletin.get("pee_amount"))

    # Sans réponse exploitable, on retombe sur le net global comme part numéraire.
    if cash_net <= 0 and pee_net <= 0:
        cash_net = _money(bulletin.get("net_amount"))

    # Net à payer au salarié = part numéraire (la part PEE est investie, pas versée).
    net_a_payer = round(max(0.0, cash_net), 2)
    # Base imposable IR : seule la part numéraire est imposable.
    net_imposable = round(max(0.0, cash_net), 2)

    lignes_cotisations = [
        {
            "libelle": "CSG déductible (participation)",
            "base": gross,
            "taux_salarial": round(float(CSG_DEDUCTIBLE_RATE) * 100, 3),
            "taux_patronal": 0.0,
            "montant_salarial": csg_ded,
            "montant_patronal": 0.0,
        },
        {
            "libelle": "CSG/CRDS non déductible (participation)",
            "base": gross,
            "taux_salarial": round(float(CSG_NON_DEDUCTIBLE_RATE) * 100, 3),
            "taux_patronal": 0.0,
            "montant_salarial": csg_nd,
            "montant_patronal": 0.0,
        },
    ]

    salarie = {
        "nom_complet": f"{employee.get('first_name') or ''} {employee.get('last_name') or ''}".strip(),
        "nir": employee.get("nir"),
        "emploi": employee.get("job_title"),
        "matricule": employee.get("matricule"),
    }
    entreprise = {
        "raison_sociale": company.get("raison_sociale") or company.get("company_name"),
        "siret": company.get("siret"),
    }

    return {
        "bulletin_kind": REGULARISATION_KIND,
        "is_regularisation": True,
        "en_tete": {
            "periode": _periode_label(year, month),
            "type_bulletin": f"Régularisation — {label}",
            "entreprise": entreprise,
            "salarie": salarie,
        },
        "regularisation": {
            "dispositif": dispositif,
            "dispositif_label": label,
            "exercise_label": exercise,
            "brut": gross,
            "csg_deductible": csg_ded,
            "csg_non_deductible": csg_nd,
            "csg_total": csg_total,
            "part_numeraire": cash_net,
            "part_pee": pee_net,
            "acompte": advance,
            "acompte_label": advance_label,
            "choice_type": choice_type,
        },
        "calcul_du_brut": [
            {
                "libelle": f"{label}{exercise_suffix} (brut)",
                "gain": gross,
                "perte": None,
            }
        ],
        "salaire_brut": gross,
        "structure_cotisations": {
            "cotisations": lignes_cotisations,
            "bloc_principales": lignes_cotisations,
            "bloc_allegements": [],
            "bloc_autres_contributions": {"lignes": [], "total": 0.0},
            "bloc_csg_non_deductible": [lignes_cotisations[1]],
            "total_salarial": csg_total,
            "total_patronal": 0.0,
        },
        "cotisations_officielles": lignes_cotisations,
        "total_exonerations": 0.0,
        "primes_non_soumises": [],
        "synthese_net": {
            "net_social_avant_impot": net_a_payer,
            "montant_net_social": net_a_payer,
            "net_imposable": net_imposable,
            "impot_prelevement_a_la_source": {
                "base": net_imposable,
                "taux": 0.0,
                "montant": 0.0,
            },
            # Compat export DSN (lecture impot_preleve_a_la_source).
            "impot_preleve_a_la_source": 0.0,
            "acompte_verse": advance,
        },
        "net_a_payer": net_a_payer,
        "pied_de_page": {
            "cout_total_employeur": gross,
            "mentions_legales": {
                "participation": (
                    "Sommes versées au titre de la participation/intéressement : "
                    "exonérées de cotisations sociales, soumises à CSG/CRDS (9,7 %). "
                    "Part numéraire imposable à l'impôt sur le revenu ; part placée "
                    "sur un plan d'épargne salariale exonérée d'impôt sur le revenu."
                ),
            },
        },
    }
