# Moteur d'écritures paie unifié — registre équilibré sans double comptabilisation.
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.modules.exports.domain.accounting_plan import (
    FAMILLE_ACOMPTE_VERSE,
    FAMILLE_ACTIVITE_PARTIELLE,
    FAMILLE_AVANCE,
    FAMILLE_AVANCE_PARTICIPATION,
    FAMILLE_CANTINE,
    FAMILLE_IJSS,
    FAMILLE_INCONNUE,
    FAMILLE_INDEMNITE_RUPTURE,
    FAMILLE_INTERETS_PRET,
    FAMILLE_NOTE_DE_FRAIS,
    FAMILLE_PANIER,
    FAMILLE_PARTICIPATION,
    FAMILLE_PARTICIPATION_PEE,
    FAMILLE_PPV,
    FAMILLE_PRET,
    FAMILLE_REGULARISATION_NET,
    FAMILLE_SAISIE,
    FAMILLE_TRANSPORT,
    FAMILY_MAPPING_ALIASES,
    ORGANISME_IJSS,
    ORGANISME_INCONNU,
    ORGANISME_MUTUELLE,
    ORGANISME_PREVOYANCE,
    ORGANISME_RETRAITE,
    ORGANISME_RETRAITE_SUP,
    ORGANISME_URSSAF,
    ORGANISMES,
    default_accounts_for,
    default_accounts_for_family,
    resolve_organisme_from_coti_id,
)
from app.modules.exports.domain.controle_comptable import (
    conseil_bulletin_incoherent,
    residu_du_bulletin,
)
from app.modules.exports.infrastructure.export_ecritures_comptables import (
    DEFAULT_MAPPINGS,
    get_accounting_mappings,
    get_default_mapping,
    get_payslip_data_for_od,
)
from app.shared.utils.export import format_period

Regroupement = Literal["global", "par_etablissement", "par_analytique"]
LedgerScope = Literal["full", "salaires", "charges_sociales", "pas", "auxiliaries"]

DEFAULT_LOAN_ACCOUNT = "274000"


def _round2(value: float) -> float:
    return round(value, 2)


class _BalanceTracker:
    """Trace débit/crédit par composante pour diagnostiquer un OD déséquilibrée."""

    def __init__(self) -> None:
        self.debit: Dict[str, float] = defaultdict(float)
        self.credit: Dict[str, float] = defaultdict(float)
        self.skipped: List[str] = []

    def add_debit(self, component: str, amount: float) -> None:
        if amount > 0:
            self.debit[component] += amount

    def add_credit(self, component: str, amount: float) -> None:
        if amount > 0:
            self.credit[component] += amount

    def skip(self, message: str) -> None:
        self.skipped.append(message)

    def finalize(
        self,
        *,
        payslips_count: int,
        ecritures_lines: int,
        payslip_source_totals: Dict[str, Any],
        period: str,
        payslip_list: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        total_debit = _round2(sum(self.debit.values()))
        total_credit = _round2(sum(self.credit.values()))
        ecart = _round2(abs(total_debit - total_credit))
        if total_debit > total_credit + 0.005:
            heavier_side = "debit"
            interpretation = (
                f"Excédent de débit de {ecart}€ : il manque {ecart}€ de crédits "
                f"pour équilibrer l'OD."
            )
        elif total_credit > total_debit + 0.005:
            heavier_side = "credit"
            interpretation = (
                f"Excédent de crédit de {ecart}€ : il manque {ecart}€ de débits "
                f"pour équilibrer l'OD."
            )
        else:
            heavier_side = "balanced"
            interpretation = "OD équilibrée."

        charges_pat_debit = _round2(self.debit.get("charges_patronales", 0))
        charges_pat_allegements = _round2(
            self.credit.get("charges_patronales_allegements", 0)
        )
        charges_pat_net = _round2(charges_pat_debit - charges_pat_allegements)
        dettes_credit = _round2(self.credit.get("dettes_organismes", 0))
        bulletin_charges_pat = _round2(
            float(payslip_source_totals.get("total_cotisations_patronales", 0) or 0)
        )
        gap_analysis = _build_gap_analysis(
            payslip_source_totals=payslip_source_totals,
            debit_by_component=dict(self.debit),
            credit_by_component=dict(self.credit),
            ecart=ecart,
            payslip_list=payslip_list,
        )

        return {
            "period": period,
            "formula": "ecart = |total_debit - total_credit|",
            "total_debit": total_debit,
            "total_credit": total_credit,
            "ecart": ecart,
            "heavier_side": heavier_side,
            "interpretation": interpretation,
            "payslips_included": payslips_count,
            "ecritures_lines": ecritures_lines,
            "debit_by_component": {
                k: _round2(v) for k, v in sorted(self.debit.items()) if v > 0
            },
            "credit_by_component": {
                k: _round2(v) for k, v in sorted(self.credit.items()) if v > 0
            },
            "payslip_source_totals": {
                k: _round2(float(v)) if isinstance(v, (int, float)) else v
                for k, v in payslip_source_totals.items()
            },
            "reconciliation": {
                "charges_patronales_debitees_645": charges_pat_debit,
                "allegements_credites_645": charges_pat_allegements,
                "charges_patronales_nettes_645": charges_pat_net,
                "dettes_organismes_creditees_431": dettes_credit,
                "charges_patronales_dans_bulletins": bulletin_charges_pat,
                "ecart_645_net_vs_431": _round2(abs(charges_pat_net - dettes_credit)),
                "ecart_bulletins_vs_645_net": _round2(
                    abs(bulletin_charges_pat - charges_pat_net)
                ),
            },
            "skipped_entries": self.skipped,
            "gap_analysis": gap_analysis,
        }


def _build_gap_analysis(
    *,
    payslip_source_totals: Dict[str, Any],
    debit_by_component: Dict[str, float],
    credit_by_component: Dict[str, float],
    ecart: float,
    payslip_list: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    brut = float(payslip_source_totals.get("total_brut", 0) or 0)
    net = float(payslip_source_totals.get("total_net_a_payer", 0) or 0)
    cot_sal_src = float(payslip_source_totals.get("total_cotisations_salariales", 0) or 0)
    pas_src = float(payslip_source_totals.get("total_pas", 0) or 0)
    cot_pat_src = float(payslip_source_totals.get("total_cotisations_patronales", 0) or 0)

    prets = float(credit_by_component.get("prets_employeur", 0) or 0)
    saisies = float(credit_by_component.get("saisies", 0) or 0)
    allegements_645 = float(
        credit_by_component.get("charges_patronales_allegements", 0) or 0
    )

    credited_net = float(credit_by_component.get("net_a_payer", 0) or 0)
    credited_cot_sal = float(credit_by_component.get("cotisations_salariales", 0) or 0)
    credited_pas = float(credit_by_component.get("pas", 0) or 0)

    aux_credits = _round2(prets + saisies)
    expected_salary_credits = _round2(net + cot_sal_src + pas_src + aux_credits)
    salary_residual = _round2(brut - expected_salary_credits)

    missing_in_od = {
        "cotisations_salariales": _round2(max(0.0, cot_sal_src - credited_cot_sal)),
        "pas": _round2(max(0.0, pas_src - credited_pas)),
        "net_a_payer": _round2(max(0.0, net - credited_net)),
    }
    charges_pat_brut_od = float(debit_by_component.get("charges_patronales", 0) or 0)
    charges_pat_net_od = _round2(charges_pat_brut_od - allegements_645)
    missing_charges_pat = _round2(max(0.0, cot_pat_src - charges_pat_net_od))
    missing_dettes_org = _round2(
        max(
            0.0,
            cot_pat_src - float(credit_by_component.get("dettes_organismes", 0) or 0),
        )
    )

    likely_causes: List[Dict[str, Any]] = []
    if brut > 0 and cot_sal_src == 0 and pas_src == 0:
        likely_causes.append(
            {
                "code": "bulletins_sans_cotisations_extraites",
                "label": "Cotisations et PAS lus à 0 dans les bulletins (format ou extraction)",
                "montant_estime": ecart,
            }
        )
    for key, label in (
        ("cotisations_salariales", "Cotisations salariales non créditées en OD"),
        ("pas", "PAS non crédité en OD"),
        ("net_a_payer", "Net à payer non crédité en OD"),
    ):
        amount = missing_in_od[key]
        if amount > 0.01:
            likely_causes.append(
                {"code": f"missing_{key}", "label": label, "montant": amount}
            )
    dettes_org = float(credit_by_component.get("dettes_organismes", 0) or 0)
    ecart_645_431 = _round2(abs(charges_pat_net_od - dettes_org))
    if ecart_645_431 > 0.01:
        likely_causes.append(
            {
                "code": "ecart_charges_645_vs_dettes_431",
                "label": "Écart charges patronales nettes (645) vs dettes organismes (431)",
                "montant": ecart_645_431,
            }
        )
    if allegements_645 > 0.01 and ecart_645_431 > 0.01:
        likely_causes.append(
            {
                "code": "allegements_patronaux",
                "label": f"Allègements patronaux crédités en 645 ({allegements_645}€) — vérifier le rapprochement",
                "montant": allegements_645,
            }
        )
    if missing_charges_pat > 0.01:
        likely_causes.append(
            {
                "code": "missing_charges_patronales",
                "label": "Charges patronales nettes (645) inférieures aux bulletins",
                "montant": missing_charges_pat,
            }
        )
    if missing_dettes_org > 0.01:
        likely_causes.append(
            {
                "code": "missing_dettes_organismes",
                "label": "Dettes organismes (431) non créditées",
                "montant": missing_dettes_org,
            }
        )

    payslips_breakdown: List[Dict[str, Any]] = []
    bulletins_sans_lignes = 0
    for payslip in payslip_list or []:
        detail_count = len(payslip.get("cotisations_detail") or [])
        cot_sal = float(payslip.get("cotisations_salariales", 0) or 0)
        pas = float(payslip.get("pas", 0) or 0)
        if cot_sal == 0 and pas == 0 and float(payslip.get("brut", 0) or 0) > 0:
            bulletins_sans_lignes += 1
        payslips_breakdown.append(
            {
                "employee_name": payslip.get("employee_name", ""),
                "brut": _round2(float(payslip.get("brut", 0) or 0)),
                "net_a_payer": _round2(float(payslip.get("net_a_payer", 0) or 0)),
                "cotisations_salariales": _round2(cot_sal),
                "cotisations_patronales": _round2(
                    float(payslip.get("cotisations_patronales", 0) or 0)
                ),
                "pas": _round2(pas),
                "lignes_cotisations": detail_count,
            }
        )

    return {
        "salary_equation": {
            "formula": "brut ≈ net + cotisations_salariales + PAS + prêts + saisies",
            "brut_bulletins": _round2(brut),
            "net_bulletins": _round2(net),
            "cotisations_salariales_bulletins": _round2(cot_sal_src),
            "pas_bulletins": _round2(pas_src),
            "prets_employeur_od": _round2(prets),
            "saisies_od": _round2(saisies),
            "note_acomptes": "Les remboursements d'acomptes sont un mouvement interne 425 (débit/crédit) sans impact sur l'équilibre OD",
            "credits_attendus_cote_salaire": expected_salary_credits,
            "residu_equation": salary_residual,
            "residu_proche_ecart_od": abs(salary_residual - ecart) < 0.02,
        },
        "missing_in_od_vs_bulletins": missing_in_od,
        "charges_patronales_manquantes_od": missing_charges_pat,
        "dettes_organismes_manquantes_od": missing_dettes_org,
        "likely_causes": likely_causes,
        "bulletins_sans_cotisations_extraites": bulletins_sans_lignes,
        "payslips_breakdown": payslips_breakdown,
    }


def _resolve_mapping(
    mappings: Dict[str, Dict[str, Any]], rubrique_code: str
) -> Dict[str, Any]:
    return mappings.get(rubrique_code) or get_default_mapping(rubrique_code) or DEFAULT_MAPPINGS.get(rubrique_code, {})  # type: ignore[return-value]


_ORGANISME_TO_RUBRIQUE = {
    ORGANISME_URSSAF: "organisme_urssaf",
    ORGANISME_RETRAITE: "organisme_retraite",
    ORGANISME_RETRAITE_SUP: "organisme_retraite_sup",
    ORGANISME_MUTUELLE: "organisme_mutuelle",
    ORGANISME_PREVOYANCE: "organisme_prevoyance",
    # La CSG sur IJSS réduit la somme à recevoir : même compte que les IJSS.
    ORGANISME_IJSS: FAMILLE_IJSS,
}


def _accounts_for_cotisation(
    coti: Dict[str, Any], mappings: Dict[str, Dict[str, Any]]
) -> Tuple[str, str, str]:
    """Retourne (organisme, compte de charge, compte de tiers) d'une cotisation.

    Cascade : mapping de la cotisation (`coti_id`, pour ventiler un organisme
    sur deux comptes, comme les deux prévoyances de l'OD de Colorplast) →
    mapping de l'organisme → défaut plateforme. Un organisme non rattaché
    retourne des comptes vides ; l'appelant doit le signaler, pas l'absorber.
    """
    organisme = resolve_organisme_from_coti_id(
        coti.get("coti_id"), str(coti.get("libelle") or "")
    )
    if organisme == ORGANISME_INCONNU:
        return organisme, "", ""

    par_coti = mappings.get(str(coti.get("coti_id") or "")) or {}
    if not (par_coti.get("compte_charge") or par_coti.get("compte_tiers")):
        par_coti = {}
    mapping = mappings.get(_ORGANISME_TO_RUBRIQUE.get(organisme, "")) or {}
    pair = default_accounts_for(organisme)

    compte_charge = str(
        par_coti.get("compte_charge")
        or mapping.get("compte_charge")
        or (pair.compte_charge if pair else "")
    )
    compte_tiers = str(
        par_coti.get("compte_tiers")
        or mapping.get("compte_tiers")
        or (pair.compte_tiers if pair else "")
    )
    return organisme, compte_charge, compte_tiers


def _compte_element(
    element: Dict[str, Any], mappings: Dict[str, Dict[str, Any]]
) -> str:
    """Compte d'un élément hors brut.

    Le plan comptable propre à la société prime ; puis le compte que porte
    l'élément (celui où l'avance a été versée, celui du type de saisie) ; puis
    le mapping plateforme ; puis le défaut de la famille. Vide si la famille
    doit être paramétrée : l'appelant le signale.
    """
    famille = str(element.get("famille") or FAMILLE_INCONNUE)
    if famille == FAMILLE_INCONNUE:
        return ""
    mapping = (
        mappings.get(famille)
        or mappings.get(FAMILY_MAPPING_ALIASES.get(famille, ""))
        or {}
    )
    compte_mapping = str(
        mapping.get("compte_charge")
        or mapping.get("compte_tiers")
        or mapping.get("compte_comptable")
        or ""
    )
    if compte_mapping and mapping.get("company_id"):
        return compte_mapping
    if element.get("compte"):
        return str(element["compte"])
    if compte_mapping:
        return compte_mapping
    pair = default_accounts_for_family(famille)
    return (pair.compte_charge or pair.compte_tiers) if pair else ""


def _period_end_date(period: str) -> str:
    year, month = map(int, period.split("-"))
    last_day = monthrange(year, month)[1]
    return f"{year}-{month:02d}-{last_day:02d}"


def _make_entry(
    *,
    date_ecriture: str,
    journal: str,
    compte: str,
    libelle: str,
    debit: float,
    credit: float,
    reference: str,
    period: str,
    analytique: Optional[str] = None,
    group_key: str = "global",
    nature: Optional[str] = None,
    compte_lib: Optional[str] = None,
) -> Dict[str, Any]:
    entry = {
        "date_ecriture": date_ecriture,
        "journal": journal,
        "compte_comptable": compte,
        "libelle": libelle,
        "debit": _round2(debit),
        "credit": _round2(credit),
        "analytique": analytique,
        "reference_export": reference,
        "periode_paie": period,
        "group_key": group_key,
    }
    if nature:
        entry["nature"] = nature
    if compte_lib:
        entry["compte_lib"] = compte_lib
    return entry


def list_loan_repayments_by_period(
    company_id: str, period: str
) -> List[Dict[str, Any]]:
    from app.core.database import supabase

    year, month = map(int, period.split("-"))
    loans_r = (
        supabase.table("employee_loans")
        .select("id, employee_id")
        .eq("company_id", company_id)
        .execute()
    )
    loans = {str(r["id"]): r for r in (loans_r.data or []) if r.get("id")}
    if not loans:
        return []

    rep_r = (
        supabase.table("employee_loan_repayments")
        .select("*")
        .in_("loan_id", list(loans.keys()))
        .eq("year", year)
        .eq("month", month)
        .execute()
    )
    employee_ids = list(
        {str(loans[str(r["loan_id"])]["employee_id"]) for r in (rep_r.data or []) if r.get("loan_id") and str(r["loan_id"]) in loans}
    )
    employees_map: Dict[str, str] = {}
    if employee_ids:
        emp_r = (
            supabase.table("employees")
            .select("id, first_name, last_name")
            .in_("id", employee_ids)
            .execute()
        )
        for emp in emp_r.data or []:
            eid = str(emp.get("id", ""))
            name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
            if eid and name:
                employees_map[eid] = name

    result: List[Dict[str, Any]] = []
    for rep in rep_r.data or []:
        loan_id = str(rep.get("loan_id", ""))
        loan = loans.get(loan_id)
        if not loan:
            continue
        capital = float(rep.get("capital_amount", 0) or 0)
        interest = float(rep.get("interest_amount", 0) or 0)
        total = capital + interest
        if total <= 0:
            continue
        eid = str(loan.get("employee_id", ""))
        result.append(
            {
                "employee_id": eid,
                "employee_name": employees_map.get(eid, ""),
                "capital_amount": capital,
                "interest_amount": interest,
                "total_amount": total,
                "loan_id": loan_id,
            }
        )
    return result


# --- Portées : l'OD globale et ses trois parts -------------------------------
#
# L'OD globale est la somme exacte de trois OD partielles, chacune équilibrée :
# - salaires : brut et éléments hors brut au débit ; net avant impôt, parts
#   salariales et retenues au crédit ;
# - charges sociales : parts patronales, charge au débit, dette au crédit ;
# - PAS : l'impôt retenu sur le net, du compte du net au compte de l'État.
# Les auxiliaires (acomptes, avances, saisies, prêts) sont la vue de détail
# de l'export « Prêts employeur ».

FULL = "full"
SALAIRES = "salaires"
CHARGES = "charges_sociales"
PAS = "pas"
AUXILIAIRES = "auxiliaries"

FAMILLES_AUXILIAIRES = frozenset(
    {
        FAMILLE_ACOMPTE_VERSE,
        FAMILLE_AVANCE,
        FAMILLE_SAISIE,
        FAMILLE_PRET,
        FAMILLE_INTERETS_PRET,
    }
)

LIBELLES_FAMILLES: Dict[str, str] = {
    FAMILLE_TRANSPORT: "Indemnités de transport",
    FAMILLE_NOTE_DE_FRAIS: "Notes de frais remboursées",
    FAMILLE_PPV: "Prime de partage de la valeur",
    FAMILLE_ACOMPTE_VERSE: "Acomptes",
    FAMILLE_AVANCE: "Avances sur salaire",
    FAMILLE_SAISIE: "Saisies sur salaire",
    FAMILLE_PRET: "Remboursement prêt employeur",
    FAMILLE_INTERETS_PRET: "Intérêts prêt employeur",
    FAMILLE_REGULARISATION_NET: "Régularisations du net",
    FAMILLE_PARTICIPATION: "Participation",
    FAMILLE_PARTICIPATION_PEE: "Participation placée sur un plan d'épargne",
    FAMILLE_AVANCE_PARTICIPATION: "Avances de participation",
    FAMILLE_IJSS: "IJSS subrogées",
    FAMILLE_INDEMNITE_RUPTURE: "Indemnités de rupture",
    FAMILLE_ACTIVITE_PARTIELLE: "Indemnité d'activité partielle",
    FAMILLE_PANIER: "Paniers",
    FAMILLE_CANTINE: "Cantine",
}

# Ordre des lignes : celui d'une OD de paie, salaires d'abord.
_RANG_NATURE = {"brut": 0, "net_a_payer": 1, "pas": 2, "charges": 3, "dettes": 4, "hors_brut": 5}


@dataclass(frozen=True)
class _Mouvement:
    """Un montant d'un bulletin, à un compte. Positif : débit ; négatif : crédit."""

    nature: str
    libelle: str
    compte: str
    montant: float
    portees: frozenset
    analytique: Optional[str] = None


def _mouvements_du_bulletin(
    payslip: Dict[str, Any],
    mappings: Dict[str, Dict[str, Any]],
    comptes: Dict[str, Dict[str, Any]],
) -> Tuple[List[_Mouvement], List[Dict[str, Any]]]:
    """Les mouvements d'un bulletin, et ce qui n'a pas de compte."""
    mouvements: List[_Mouvement] = []
    anomalies: List[Dict[str, Any]] = []
    brut = float(payslip.get("brut", 0) or 0)
    net = float(payslip.get("net_a_payer", 0) or 0)
    pas = float(payslip.get("pas", 0) or 0)
    m_brut, m_net, m_pas = comptes["salaire_brut"], comptes["net_a_payer"], comptes["pas"]
    compte_net = str(m_net.get("compte_comptable") or "")

    mouvements += [
        _Mouvement("brut", "Salaires", str(m_brut.get("compte_comptable") or ""), brut,
                   frozenset({FULL, SALAIRES}), m_brut.get("analytique")),
        _Mouvement("net_a_payer", "Net à payer", compte_net, -net,
                   frozenset({FULL}), m_net.get("analytique")),
        # OD salaires seule : le net avant impôt ; l'OD PAS en retire l'impôt.
        _Mouvement("net_a_payer", "Net à payer", compte_net, -(net + pas),
                   frozenset({SALAIRES}), m_net.get("analytique")),
        _Mouvement("pas", "PAS", str(m_pas.get("compte_comptable") or ""), -pas,
                   frozenset({FULL, PAS}), m_pas.get("analytique")),
        _Mouvement("net_a_payer", "PAS retenu sur le net", compte_net, pas,
                   frozenset({PAS}), m_net.get("analytique")),
    ]

    for coti in payslip.get("cotisations_detail") or []:
        if not isinstance(coti, dict):
            continue
        patronal = float(coti.get("montant_patronal", 0) or 0)
        salarial = float(coti.get("montant_salarial", 0) or 0)
        if patronal == 0 and salarial == 0:
            continue
        organisme, compte_charge, compte_tiers = _accounts_for_cotisation(coti, mappings)
        if not compte_charge or not compte_tiers:
            anomalies.append(
                {
                    "code": "organisme_non_rattache",
                    "label": "Cotisation sans compte comptable",
                    "detail": f"{coti.get('coti_id') or '?'} — {coti.get('libelle') or ''}",
                    "montant": _round2(abs(patronal) + abs(salarial)),
                }
            )
            continue
        nom = ORGANISMES.get(organisme, organisme)
        if patronal:
            mouvements += [
                _Mouvement(f"charges:{organisme}", f"Charges sociales {nom}", compte_charge,
                           patronal, frozenset({FULL, CHARGES})),
                _Mouvement(f"dettes:{organisme}", f"Dette {nom}", compte_tiers,
                           -patronal, frozenset({FULL, CHARGES})),
            ]
        if salarial:
            # Sa contrepartie est le brut, déjà débité.
            mouvements.append(
                _Mouvement(f"dettes:{organisme}", f"Dette {nom}", compte_tiers,
                           -salarial, frozenset({FULL, SALAIRES}))
            )

    for element in payslip.get("elements_hors_brut") or []:
        if not isinstance(element, dict):
            continue
        montant = float(element.get("montant", 0) or 0)
        if montant == 0:
            continue
        famille = str(element.get("famille") or FAMILLE_INCONNUE)
        libelle = str(element.get("libelle") or famille)
        compte = _compte_element(element, mappings)
        if not compte:
            anomalies.append(
                {
                    "code": "element_hors_brut_non_mappe",
                    "label": "Élément hors brut sans compte comptable",
                    "detail": f"{famille} — {libelle}",
                    "montant": _round2(abs(montant)),
                }
            )
            continue
        portees = {FULL, SALAIRES}
        if famille in FAMILLES_AUXILIAIRES:
            portees.add(AUXILIAIRES)
        mouvements.append(
            _Mouvement(f"hors_brut:{famille}", LIBELLES_FAMILLES.get(famille, libelle),
                       compte, montant, frozenset(portees))
        )
    return mouvements, anomalies


def _composante(nature: str, montant: float) -> str:
    """Poste du diagnostic d'équilibre (`balance_debug`) d'une ligne."""
    if nature == "brut":
        return "salaire_brut"
    if nature in ("net_a_payer", "pas"):
        return nature
    if nature.startswith("charges:"):
        return "charges_patronales" if montant > 0 else "charges_patronales_allegements"
    if nature.startswith("dettes:"):
        return "dettes_organismes" if montant < 0 else "dettes_organismes_allegements"
    famille = nature.split(":", 1)[-1]
    if famille in (FAMILLE_PRET, FAMILLE_INTERETS_PRET):
        return "prets_employeur"
    if famille == FAMILLE_SAISIE:
        return "saisies"
    if famille in (FAMILLE_ACOMPTE_VERSE, FAMILLE_AVANCE):
        return "acomptes"
    return "elements_hors_brut"


def build_payroll_ledger(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    regroupement: Regroupement = "global",
    scope: LedgerScope = "full",
) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, Any]]:
    """Registre d'écritures paie d'une période, lu sur les seuls bulletins.

    Chaque bulletin donne ses mouvements (brut, net, PAS, cotisations par
    organisme, éléments hors brut et retenues), agrégés ensuite par compte —
    une ligne par compte et par nature, comme l'OD d'un cabinet. Un bulletin
    dont le net ne se reconstruit pas au centime est signalé par son nom : l'OD
    ne peut pas s'équilibrer sans lui.

    Les notes de frais remboursées sur le bulletin y sont un élément hors brut
    (débit du compte des notes de frais) ; leur constatation en charge relève
    de l'export « Notes de frais », pas de l'OD de paie.
    """
    payslip_list, totals = get_payslip_data_for_od(
        company_id, period, employee_ids, "od_globale"
    )
    mappings = get_accounting_mappings(company_id)
    if not date_ecriture:
        date_ecriture = _period_end_date(period)

    period_label = format_period(period)
    reference = f"OD_PAIE_{period}"
    tracker = _BalanceTracker()
    comptes = {
        code: _resolve_mapping(mappings, code)
        for code in ("salaire_brut", "net_a_payer", "pas")
    }
    # Une OD, un journal : celui de la société.
    journal = str(comptes["salaire_brut"].get("journal") or "OD")

    group_key = "global"
    if regroupement == "par_analytique" and comptes["salaire_brut"].get("analytique"):
        group_key = str(comptes["salaire_brut"].get("analytique"))

    anomalies: List[Dict[str, Any]] = []
    sommes: Dict[Tuple[str, str, str, str, Optional[str]], float] = defaultdict(float)
    for payslip in payslip_list:
        grp = (
            str(payslip.get("establishment_label") or "Principal")
            if regroupement == "par_etablissement"
            else group_key
        )
        mouvements, manquants = _mouvements_du_bulletin(payslip, mappings, comptes)
        anomalies.extend(manquants)
        residu = residu_du_bulletin(payslip)
        if abs(residu) >= 0.005:
            nom = payslip.get("employee_name") or payslip.get("employee_id") or "?"
            anomalies.append(
                {
                    "code": "bulletin_incoherent",
                    "label": "Bulletin dont le net ne se retrouve pas",
                    "detail": (
                        f"{nom} : le net à payer ({_round2(float(payslip.get('net_a_payer', 0) or 0))} €) "
                        f"diffère de {residu} € du brut moins les cotisations et l'impôt, "
                        f"plus les éléments hors brut — "
                        f"{conseil_bulletin_incoherent(bool(payslip.get('reprise')))}"
                    ),
                    "montant": abs(residu),
                }
            )
        for mv in mouvements:
            if scope in mv.portees and mv.montant:
                sommes[(grp, mv.nature, mv.libelle, mv.compte, mv.analytique)] += mv.montant

    for anomalie in anomalies:
        tracker.skip(f"{anomalie['label']} : {anomalie['detail']} ({anomalie['montant']} €)")

    def _rang(cle: Tuple[str, str, str, str, Optional[str]]) -> Tuple[Any, ...]:
        grp, nature, libelle, compte, _ = cle
        return (grp, _RANG_NATURE.get(nature.split(":", 1)[0], 9), nature, compte, libelle)

    ecritures: List[Dict[str, Any]] = []
    for cle in sorted(sommes, key=_rang):
        grp, nature, libelle, compte, analytique = cle
        montant = _round2(sommes[cle])
        if abs(montant) < 0.005:
            continue
        organisme = nature.split(":", 1)[-1]
        nom = ORGANISMES.get(organisme, organisme)
        if nature.startswith("charges:") and montant < 0:
            libelle = f"Allègements {nom}"
        elif nature.startswith("dettes:") and montant > 0:
            libelle = f"Dette {nom} (allègements)"
        suffixe = (
            f" — {grp}"
            if regroupement == "par_etablissement" and nature in ("brut", "net_a_payer", "pas")
            else ""
        )
        ecritures.append(
            _make_entry(
                date_ecriture=date_ecriture,
                journal=journal,
                compte=compte,
                libelle=f"{libelle} {period_label}{suffixe}",
                debit=montant if montant > 0 else 0.0,
                credit=-montant if montant < 0 else 0.0,
                reference=reference,
                period=period,
                analytique=analytique,
                group_key=grp,
                nature=nature,
                compte_lib=libelle,
            )
        )
        composante = _composante(nature, montant)
        if montant > 0:
            tracker.add_debit(composante, montant)
        else:
            tracker.add_credit(composante, -montant)

    total_debit = sum(e["debit"] for e in ecritures)
    total_credit = sum(e["credit"] for e in ecritures)
    balance_debug = tracker.finalize(
        payslips_count=len(payslip_list),
        ecritures_lines=len(ecritures),
        payslip_source_totals=totals,
        period=period,
        payslip_list=payslip_list,
    )
    ecart = _round2(abs(total_debit - total_credit))
    od_totals = {
        "total_debit": _round2(total_debit),
        "total_credit": _round2(total_credit),
        # Au centime : un écart d'un centime est un écart. Un bulletin incohérent
        # bloque même si un autre compense son écart.
        "equilibre": ecart == 0
        and not any(a["code"] == "bulletin_incoherent" for a in anomalies),
        "ecart": ecart,
        "anomalies": anomalies,
        "balance_debug": balance_debug,
    }
    return ecritures, od_totals, mappings


def ledger_to_od_export_rows(ecritures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convertit les écritures registre vers le format export OD standard."""
    return [
        {
            "date_ecriture": e["date_ecriture"],
            "journal": e["journal"],
            "compte_comptable": e["compte_comptable"],
            "libelle": e["libelle"],
            "debit": e["debit"],
            "credit": e["credit"],
            "analytique": e.get("analytique"),
            "reference_export": e.get("reference_export", ""),
            "periode_paie": e["periode_paie"],
        }
        for e in ecritures
    ]


class LedgerImbalanceError(ValueError):
    """L'OD ne s'équilibre pas — le fichier n'est pas produit."""


def assert_ledger_balanced(od_totals: Dict[str, Any]) -> None:
    """Refuse un registre déséquilibré, avec le détail de ce qui manque.

    Un fichier d'écritures déséquilibré est rejeté par tout logiciel comptable.
    Sortir un fichier faux coûte plus cher qu'un export refusé, à condition que
    le message dise quoi corriger.
    """
    if od_totals.get("equilibre"):
        return

    ecart = od_totals.get("ecart", 0)
    lignes = [f"L'écriture ne s'équilibre pas : écart de {ecart} €."]

    anomalies = od_totals.get("anomalies") or []
    incoherents = [a for a in anomalies if a.get("code") == "bulletin_incoherent"]
    sans_compte = [a for a in anomalies if a.get("code") != "bulletin_incoherent"]
    if incoherents:
        lignes.append("Bulletins dont le net ne se retrouve pas :")
        for anomalie in incoherents:
            lignes.append(f"  — {anomalie.get('detail', '')}")
    if sans_compte:
        lignes.append("Éléments sans compte comptable :")
        for anomalie in sans_compte:
            lignes.append(
                f"  — {anomalie.get('detail', '')} ({anomalie.get('montant', 0)} €)"
            )
        lignes.append(
            "Renseignez les comptes manquants dans Exports > Comptes comptables."
        )
    if not anomalies:
        lignes.append(
            "Aucun élément non rattaché n'a été détecté : vérifiez le détail de "
            "l'équilibre dans le panneau de diagnostic de l'OD."
        )
    raise LedgerImbalanceError("\n".join(lignes))
