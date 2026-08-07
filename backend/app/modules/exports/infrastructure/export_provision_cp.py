# Export « État de provision des congés payés » — valorisation en euros de la dette de CP.
# Modèle : état Cegid transmis par Elsa le 27/07/2026 (CARTOL, 71 salariés, 394 121,22 €).
from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.absences.application.queries import _leave_context, _parse_hire_date
from app.modules.absences.domain.fractionnement import ouvrables_to_ouvres
from app.modules.absences.domain.rules import compute_cp_balances_for_bulletin
from app.modules.absences.infrastructure import fractionnement_repository as frac_repo
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.exports.domain.provision_cp import (
    FENETRE_REFERENCE_MOIS,
    LigneProvision,
    calculer_ligne,
    calculer_totaux,
    mois_de_reference,
    resoudre_reference,
)
from app.shared.utils.export import generate_csv, generate_xlsx

EXPORT_HEADERS = [
    "Matricule",
    "Nom de l'employé",
    "Date d'entrée",
    "Solde jrs N-1",
    "Solde jrs N",
    "Solde jours",
    "Salaire de référence",
    "Taux Ch. soc.",
    "Montant charges sociales",
    "Provision",
    "Total",
    "Mois retenus",
    "Anomalie",
]


def _fin_de_mois(period: str) -> date:
    annee, mois = map(int, period.split("-"))
    return date(annee, mois, calendar.monthrange(annee, mois)[1])


def _montant_contractuel(salarie: Dict[str, Any]) -> Optional[float]:
    brut = salarie.get("salaire_de_base")
    if isinstance(brut, dict):
        # La base stocke {"type": "mensuel", "valeur": 2049.76} : c'est « valeur » qui
        # porte le montant. Les autres clés sont des variantes rencontrées à l'import.
        for cle in ("valeur", "montant", "value", "brut_mensuel", "amount"):
            valeur = brut.get(cle)
            if isinstance(valeur, (int, float)):
                return float(valeur)
        return None
    return float(brut) if isinstance(brut, (int, float)) else None


def _lire_salaries(
    company_id: str, employee_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    requete = (
        supabase.table("employees")
        .select(
            "id, matricule, first_name, last_name, hire_date, "
            "employment_status, salaire_de_base"
        )
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
    )
    if employee_ids:
        requete = requete.in_("id", employee_ids)
    lignes = requete.execute().data or []
    return sorted(lignes, key=lambda e: (e.get("last_name") or "", e.get("first_name") or ""))


def _lire_bulletins(
    company_id: str, mois_cibles: List[Tuple[int, int]]
) -> Dict[str, Dict[Tuple[int, int], Tuple[float, float]]]:
    """Brut et cotisations patronales par salarié et par mois, sur la fenêtre demandée."""
    annees = sorted({a for a, _ in mois_cibles})
    reponse = (
        supabase.table("payslips")
        .select("employee_id, year, month, payslip_data")
        .eq("company_id", company_id)
        .in_("year", annees)
        .execute()
    )
    attendus = set(mois_cibles)
    resultat: Dict[str, Dict[Tuple[int, int], Tuple[float, float]]] = {}
    for ligne in reponse.data or []:
        cle = (ligne["year"], ligne["month"])
        if cle not in attendus:
            continue
        donnees = ligne.get("payslip_data") or {}
        brut = float(donnees.get("salaire_brut") or 0)
        patronal = sum(
            float(c.get("total_patronal") or 0)
            for c in (donnees.get("cotisations_officielles") or [])
        )
        resultat.setdefault(ligne["employee_id"], {})[cle] = (brut, patronal)
    return resultat


def _lire_soldes_ouvres(
    employee_id: str, company_id: str, ref_date: date
) -> Tuple[float, float]:
    """Soldes CP période précédente et période en cours, en jours ouvrés."""
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return (0.0, 0.0)
    policy, adjustment, _, cp_seniority = _leave_context(
        employee_id, ref_date.year, company_id
    )
    from app.modules.absences.application.fractionnement_prefill import (
        build_employee_cp_seniority_context_from_db,
    )

    contexte = build_employee_cp_seniority_context_from_db(employee_id)
    validees = absence_repository.list_validated_for_employees([employee_id])
    soldes = compute_cp_balances_for_bulletin(
        hire_date,
        validees,
        ref_date,
        policy=policy,
        adjustment=adjustment,
        cp_seniority=cp_seniority,
        employee_ctx=contexte,
    )
    reglages = frac_repo.get_fractionnement_settings_row(company_id) or {}
    ratio = float(reglages.get("ouvres_to_ouvrables_ratio") or 1.2)
    n1 = ouvrables_to_ouvres(float(soldes["periode_precedente"].get("solde") or 0), ratio)
    n = ouvrables_to_ouvres(float(soldes["periode_courante"].get("solde") or 0), ratio)
    return (n1, n)


def collecter_lignes(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None
) -> Tuple[List[LigneProvision], List[str]]:
    ref_date = _fin_de_mois(period)
    mois_cibles = mois_de_reference(ref_date.year, ref_date.month)
    salaries = _lire_salaries(company_id, employee_ids)
    bulletins = _lire_bulletins(company_id, mois_cibles)

    lignes: List[LigneProvision] = []
    sans_date = 0
    mois_max = 0

    for salarie in salaries:
        if not salarie.get("hire_date"):
            sans_date += 1
            continue
        n1, n = _lire_soldes_ouvres(salarie["id"], company_id, ref_date)
        if round(n1 + n, 2) == 0:
            continue
        reference = resoudre_reference(
            bulletins=bulletins.get(salarie["id"], {}),
            mois_cibles=mois_cibles,
            salaire_contractuel=_montant_contractuel(salarie),
            taux_societe=None,
        )
        mois_max = max(mois_max, int(reference.mois_retenus.split("/")[0]))
        anomalie = reference.anomalie
        if round(n1 + n, 2) < 0:
            anomalie = "; ".join(
                filter(None, [anomalie, "solde négatif : congés pris d'avance"])
            )
        lignes.append(
            calculer_ligne(
                matricule=salarie.get("matricule") or "",
                nom=f"{salarie.get('first_name') or ''} {salarie.get('last_name') or ''}".strip(),
                date_entree=str(salarie["hire_date"])[:10],
                solde_n1=n1,
                solde_n=n,
                salaire_reference=reference.salaire_reference,
                taux_charges=reference.taux_charges,
                mois_retenus=reference.mois_retenus,
                anomalie=anomalie,
            )
        )

    avertissements: List[str] = []
    if lignes:
        # Les congés antérieurs à janvier 2026 ne sont pas dans EYWAI : le solde de la
        # période précédente est un droit recalculé, pas un report repris du cabinet.
        # Mesuré le 07/08/2026 sur Cartol : 20,8 à 22,5 j chez nous contre 3 à 88 j
        # sur l'état du cabinet. Tant que les reports ne sont pas chargés, la provision
        # est sous-évaluée. Ne jamais laisser sortir ce chiffre sans le dire.
        avertissements.append(
            "Solde de la période précédente recalculé par EYWAI et non repris du "
            "cabinet : les congés antérieurs à janvier 2026 n'y sont pas. La provision "
            "est indicative tant que les reports n'ont pas été chargés."
        )
    if lignes and mois_max < FENETRE_REFERENCE_MOIS:
        avertissements.append(
            f"Salaire de référence calculé sur {mois_max} mois sur "
            f"{FENETRE_REFERENCE_MOIS} — EYWAI ne contient de la paie que depuis "
            "janvier 2026."
        )
    if sans_date:
        avertissements.append(
            f"{sans_date} salarié(s) exclu(s) : aucune date d'entrée renseignée."
        )
    return lignes, avertissements


def preview_provision_cp(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    lignes, avertissements = collecter_lignes(company_id, period, employee_ids)
    totaux = calculer_totaux(lignes)

    anomalies: List[Dict[str, Any]] = []
    if not lignes:
        anomalies.append(
            {
                "type": "error",
                "message": "Aucun salarié avec un solde de congés à cette date",
                "severity": "blocking",
            }
        )
    elif totaux["provision"] == 0:
        # Des soldes existent (une ligne à solde nul est hors périmètre) mais rien n'a pu
        # être valorisé : ni bulletin, ni salaire contractuel. Un fichier entièrement à
        # zéro se lirait comme « aucune dette », ce qui est faux.
        anomalies.append(
            {
                "type": "error",
                "message": (
                    "Aucun salaire de référence disponible : ni bulletin ni salaire "
                    "contractuel pour les salariés concernés"
                ),
                "severity": "blocking",
            }
        )
    nb_anomalies = sum(1 for l in lignes if l.anomalie)
    if nb_anomalies:
        anomalies.append(
            {
                "type": "warning",
                "message": f"{nb_anomalies} ligne(s) signalée(s) dans la colonne Anomalie",
                "severity": "warning",
            }
        )

    return {
        "employees_count": len(lignes),
        "totals": {
            "employees_count": len(lignes),
            "total_amount": totaux["total"],
        },
        "anomalies": anomalies,
        "warnings": avertissements,
        "can_generate": all(a.get("severity") != "blocking" for a in anomalies),
        "details": {
            "provision": totaux["provision"],
            "montant_charges": totaux["montant_charges"],
            "total": totaux["total"],
            "solde_jours": totaux["solde_jours"],
            "taux_charges_moyen": totaux["taux_charges"],
        },
    }


def _lignes_export(lignes: List[LigneProvision]) -> List[Dict[str, Any]]:
    donnees = [
        {
            "Matricule": l.matricule,
            "Nom de l'employé": l.nom,
            "Date d'entrée": l.date_entree,
            "Solde jrs N-1": l.solde_n1,
            "Solde jrs N": l.solde_n,
            "Solde jours": l.solde_jours,
            "Salaire de référence": l.salaire_reference,
            "Taux Ch. soc.": l.taux_charges,
            "Montant charges sociales": l.montant_charges,
            "Provision": l.provision,
            "Total": l.total,
            "Mois retenus": l.mois_retenus,
            "Anomalie": l.anomalie,
        }
        for l in lignes
    ]
    totaux = calculer_totaux(lignes)
    donnees.append(
        {
            "Matricule": "",
            "Nom de l'employé": "Total",
            "Date d'entrée": "",
            "Solde jrs N-1": totaux["solde_n1"],
            "Solde jrs N": totaux["solde_n"],
            "Solde jours": totaux["solde_jours"],
            "Salaire de référence": totaux["salaire_reference"],
            "Taux Ch. soc.": totaux["taux_charges"],
            "Montant charges sociales": totaux["montant_charges"],
            "Provision": totaux["provision"],
            "Total": totaux["total"],
            "Mois retenus": "",
            "Anomalie": "",
        }
    )
    return donnees


def generate_provision_cp_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    file_format: str = "xlsx",
) -> bytes:
    lignes, _ = collecter_lignes(company_id, period, employee_ids)
    donnees = _lignes_export(lignes)
    if file_format == "xlsx":
        return generate_xlsx(donnees, EXPORT_HEADERS, f"Provision CP {period}")
    return generate_csv(donnees, EXPORT_HEADERS)
