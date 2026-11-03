# Export « État de provision des congés payés » — valorisation en euros de la dette de CP.
# Modèle : état Cegid transmis par Elsa le 27/07/2026 (CARTOL, 71 salariés, 394 121,22 €).
from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.absences.application.queries import _leave_context, _parse_hire_date
from app.modules.absences.domain.rules import compute_cp_balances_for_bulletin
from app.modules.absences.infrastructure import fractionnement_repository as frac_repo
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.exports.domain.provision_cp import (
    FENETRE_REFERENCE_MOIS,
    LigneProvision,
    calculer_ligne,
    calculer_totaux,
    en_jours_ouvres,
    mois_de_reference,
    patronal_du_bulletin,
    present_a_la_date,
    reference_du_salarie,
)
from app.shared.reprise_paie import lire_bascule as _lire_bascule
from app.shared.reprise_paie import rang_du_mois
from app.shared.utils.export import generate_csv, generate_xlsx
from app.shared.domain.pluriel import accord, pluriel

#: PostgREST tronque une réponse à 1000 lignes sans le dire — on pagine en deçà.
TAILLE_PAGE = 500

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
    company_id: str,
    employee_ids: Optional[List[str]] = None,
    ref_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Les salariés présents à la fin du mois demandé (`present_a_la_date`), quel que soit leur
    statut d'aujourd'hui : un salarié parti en juin est dans la provision de mai. Sans date
    d'entrée, seul un salarié actif est gardé, pour être signalé."""
    requete = (
        supabase.table("employees")
        .select(
            "id, matricule, first_name, last_name, hire_date, "
            "employment_status, salaire_de_base"
        )
        .eq("company_id", company_id)
    )
    if employee_ids:
        requete = requete.in_("id", employee_ids)
    salaries = requete.execute().data or []
    sorties: Dict[str, List[date]] = {}
    ids = [s["id"] for s in salaries]
    if ids:
        for sortie in (
            supabase.table("employee_exits")
            .select("employee_id, last_working_day, exit_type")
            .in_("employee_id", ids)
            .execute()
            .data
            or []
        ):
            if sortie.get("exit_type") == "transfert" or not sortie.get("last_working_day"):
                continue
            sorties.setdefault(sortie["employee_id"], []).append(
                date.fromisoformat(str(sortie["last_working_day"])[:10])
            )
    ref = ref_date or date.today()
    lignes = [
        s for s in salaries
        if (not s.get("hire_date") and s.get("employment_status") == "actif")
        or (
            s.get("hire_date")
            and present_a_la_date(
                date.fromisoformat(str(s["hire_date"])[:10]), sorties.get(s["id"], []), ref
            )
        )
    ]
    return sorted(lignes, key=lambda e: (e.get("last_name") or "", e.get("first_name") or ""))


def _lire_bulletins(
    company_id: str, mois_cibles: List[Tuple[int, int]]
) -> Dict[str, Dict[Tuple[int, int], Tuple[float, float]]]:
    """Brut et cotisations patronales par salarié et par mois, sur la fenêtre demandée.

    La lecture est paginée : PostgREST plafonne une réponse à 1000 lignes sans
    le signaler. Une société de 90 salariés dépasse ce seuil dès douze mois
    d'historique, et les bulletins tombés dans la troncature ne sont pas
    « manquants » — ils font chuter le salaire de référence, donc la provision,
    sans la moindre anomalie affichée.
    """
    annees = sorted({a for a, _ in mois_cibles})
    lignes: List[Dict[str, Any]] = []
    decalage = 0
    while True:
        lot = (
            supabase.table("payslips")
            .select("employee_id, year, month, payslip_data")
            .eq("company_id", company_id)
            .in_("year", annees)
            .range(decalage, decalage + TAILLE_PAGE - 1)
            .execute()
        ).data or []
        lignes.extend(lot)
        if len(lot) < TAILLE_PAGE:
            break
        decalage += TAILLE_PAGE

    attendus = set(mois_cibles)
    resultat: Dict[str, Dict[Tuple[int, int], Tuple[float, float]]] = {}
    for ligne in lignes:
        cle = (ligne["year"], ligne["month"])
        if cle not in attendus:
            continue
        donnees = ligne.get("payslip_data") or {}
        brut = float(donnees.get("salaire_brut") or 0)
        patronal = patronal_du_bulletin(donnees)
        # Un mois à deux contrats a deux bulletins : la provision les somme (D3).
        deja_brut, deja_patronal = resultat.setdefault(ligne["employee_id"], {}).get(cle, (0.0, 0.0))
        resultat[ligne["employee_id"]][cle] = (deja_brut + brut, deja_patronal + patronal)
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
    # Le solde est dans l'unité de la société : seul un solde en ouvrables se convertit.
    unite = getattr(policy, "cp_counting_unit", None)
    n1 = en_jours_ouvres(float(soldes["periode_precedente"].get("solde") or 0), unite, ratio)
    n = en_jours_ouvres(float(soldes["periode_courante"].get("solde") or 0), unite, ratio)
    return (n1, n)


def collecter_lignes(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None
) -> Tuple[List[LigneProvision], List[str]]:
    ref_date = _fin_de_mois(period)
    mois_cibles = mois_de_reference(ref_date.year, ref_date.month)
    salaries = _lire_salaries(company_id, employee_ids, ref_date=ref_date)
    bascule = _lire_bascule(company_id)
    # À partir du mois de la reprise, les soldes sont ceux du logiciel précédent.
    soldes_repris = bool(bascule) and rang_du_mois(ref_date.year, ref_date.month) >= bascule.rang
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
        reference = reference_du_salarie(
            bulletins.get(salarie["id"], {}),
            mois_cibles,
            _montant_contractuel(salarie),
            date.fromisoformat(str(salarie["hire_date"])[:10]),
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
    if lignes and not soldes_repris:
        # Les congés antérieurs à janvier 2026 ne sont pas dans MARTINE : le solde de la
        # période précédente est un droit recalculé, pas un report repris du cabinet.
        # Mesuré le 07/08/2026 sur Cartol : 20,8 à 22,5 j chez nous contre 3 à 88 j
        # sur l'état du cabinet. Tant que les reports ne sont pas chargés, la provision
        # est sous-évaluée. Ne jamais laisser sortir ce chiffre sans le dire.
        avertissements.append(
            "Solde de la période précédente recalculé par Martine et non repris de "
            "la paie actuelle : les congés antérieurs à janvier 2026 n'y sont pas. La provision "
            "est indicative tant que les reports n'ont pas été chargés."
        )
    if lignes and mois_max < FENETRE_REFERENCE_MOIS:
        avertissements.append(
            f"Salaire de référence calculé sur {mois_max} mois sur "
            f"{FENETRE_REFERENCE_MOIS} — Martine ne contient de la paie que depuis "
            "janvier 2026."
        )
    if sans_date:
        avertissements.append(
            f"{pluriel(sans_date, 'salarié')} {accord(sans_date, 'exclu')} : aucune date d'entrée renseignée."
        )
    return lignes, avertissements


def preview_provision_cp(
    company_id: str, period: str, employee_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    lignes, avertissements = collecter_lignes(company_id, period, employee_ids)
    totaux = calculer_totaux(lignes)

    anomalies: List[Dict[str, Any]] = []
    bascule = _lire_bascule(company_id)
    annee, mois = map(int, period.split("-"))
    if bascule and rang_du_mois(annee, mois) < bascule.rang:
        # Avant la reprise, Martine n'a pas les soldes du logiciel précédent : elle n'aurait
        # que des droits recalculés depuis l'embauche, sans les congés pris (MAJI mai 2026).
        logiciel = bascule.logiciel_precedent or "le logiciel précédent"
        anomalies.append(
            {
                "type": "error",
                "message": (
                    f"Martine tient les congés de cette société depuis la reprise de "
                    f"{bascule.libelle} : la provision se calcule à partir de ce mois. "
                    f"Avant, les soldes sont dans {logiciel}."
                ),
                "severity": "blocking",
            }
        )
    if not bascule and lignes and all(l.anomalie.startswith("aucun bulletin") for l in lignes):
        # Ni reprise ni bulletin : la paie est encore ailleurs (Cartol, LEWIS, Mont Blanc au
        # 03/11/2026). Les soldes seraient des droits recalculés sans les congés pris, le
        # salaire celui de la fiche et les charges à zéro : un chiffre faux, pas indicatif.
        anomalies.append(
            {
                "type": "error",
                "message": (
                    "Martine n'a aucun bulletin ni reprise des congés pour cette société : "
                    "la paie et les soldes de congés sont encore dans le logiciel précédent. "
                    "La provision se fera dans Martine après la reprise."
                ),
                "severity": "blocking",
            }
        )
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
                "message": f"{pluriel(nb_anomalies, 'ligne')} {accord(nb_anomalies, 'signalée')} dans la colonne Anomalie",
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
