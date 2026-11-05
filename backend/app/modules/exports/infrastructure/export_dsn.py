# Générateur DSN mensuelle NEODeS P26V01 (fichier plat).
from app.modules.dsn_export.domain.fiche_a_completer import fiche_a_completer
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.dsn_export.application.builder import (
    DsnBuildError,
    build_parsed_dsn_from_payroll,
)
from app.modules.dsn_export.domain.changement_pcs import avis_changements_pcs
from app.modules.pcs_ese.infrastructure.transmissions import periodes_deposees
from app.modules.dsn_export.domain.affiliations import Collegue, deduire_affiliations
from app.modules.dsn_export.domain.contract_map import numero_du_contrat
from app.modules.dsn_export.domain.deux_contrats import evenements_du_contrat
from app.modules.dsn_export.domain.etat_conformite import (
    DEPOSABLE,
    SUFFIXE_NON_DEPOSABLE,
    anomalie_non_deposable,
)
from app.modules.dsn_export.domain.settings import DsnSettings
from app.modules.dsn_export.domain.versements_complementaires import (
    cotisations_par_contrat,
    est_fin_de_trimestre,
    mois_precedents_du_trimestre,
)
from app.modules.dsn_export.domain.writer import encode_dsn_bytes
from app.modules.dsn_export.infrastructure import settings_repository
from app.modules.dsn_import.domain.parser import parse_dsn_content
from app.modules.dsn_import.domain.validation import validate_parsed_dsn
from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_cotisations_from_payslip,
    extract_pas_amount,
)
from app.modules.employees.application.contrat_du_mois import (
    debut_du_contrat,
    fiche_du_mois,
    lecteur_contrats,
)
from app.modules.oeth_settings.application import queries as oeth_queries
from app.modules.payroll.application.monthly_specificites import (
    resolve_monthly_specificites,
)
from app.shared.domain.employment_rules import is_cadre
from app.shared.reprise_paie import lire_bascule
from app.shared.dsn_validation import validate_nir, validate_nir_dsn, validate_siret

DSN_NORME = "P26V01"


def get_company_data(company_id: str) -> Dict[str, Any]:
    response = (
        supabase.table("companies").select("*").eq("id", company_id).single().execute()
    )
    data = response.data if response.data else {}
    if not data:
        return {}
    # Normalise les alias attendus par le builder P26
    if not data.get("name"):
        data["name"] = data.get("company_name") or data.get("raison_sociale") or ""
    if not data.get("address") or not isinstance(data.get("address"), dict):
        data["address"] = {
            "rue": data.get("adresse_rue") or "",
            "code_postal": data.get("adresse_code_postal") or "",
            "ville": data.get("adresse_ville") or "",
        }
    if not data.get("code_naf"):
        data["code_naf"] = data.get("naf_ape") or ""
    return data


def _evenements_dsn(
    company_id: str,
    period: str,
    employee_ids: List[str],
    fiches: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Arrêts, sortie et taux PAS reçus de chaque salarié, pour la DSN du mois.

    - ``absences_dsn`` : les demandes d'arrêt validées de l'année écoulée
      jusqu'à la fin du mois — un arrêt prolongé se déclare depuis son début ;
    - ``sortie_dsn`` : la sortie dont le dernier jour tombe dans le mois
      (``sorties_dsn`` : toutes, pour un mois à deux contrats) ;
    - ``pas_type_taux`` / ``pas_identifiant_taux`` : le dernier taux reçu.
    """
    from datetime import timedelta

    from app.modules.dsn_export.application.builder import (
        heures_cumulees_avant,
        taux_pas_du_mois,
    )
    from app.modules.dsn_export.domain.contract_map import period_bounds
    from app.modules.dsn_export.domain.evenements import MOTIF_ARRET, date_dsn

    resultat: Dict[str, Dict[str, Any]] = {eid: {} for eid in employee_ids}
    if not employee_ids:
        return resultat
    fiches = fiches or {}
    debut_dsn, fin_dsn = period_bounds(period)
    debut_mois, fin_mois = date_dsn(debut_dsn), date_dsn(fin_dsn)
    plancher = debut_mois - timedelta(days=366)

    taux = (
        supabase.table("employee_pas_rates")
        .select("employee_id,periode,taux,type_taux,identifiant_taux")
        .eq("company_id", company_id)
        .lte("periode", period)
        .execute()
    ).data or []
    par_salarie: Dict[str, List[Dict[str, Any]]] = {}
    for ligne in taux:
        par_salarie.setdefault(str(ligne.get("employee_id")), []).append(ligne)
    for eid, lignes in par_salarie.items():
        if eid in resultat:
            resultat[eid].update(taux_pas_du_mois(lignes, period))

    arrets = (
        supabase.table("absence_requests")
        .select("employee_id,type,status,selected_days,subrogation_active,arret_type")
        .eq("company_id", company_id)
        .eq("status", "validated")
        .in_("type", sorted(MOTIF_ARRET))
        .execute()
    ).data or []
    for arret in arrets:
        eid = str(arret.get("employee_id"))
        jours = sorted(str(j)[:10] for j in arret.get("selected_days") or [])
        if eid not in resultat or not jours:
            continue
        if jours[0] > fin_mois.isoformat() or jours[-1] < plancher.isoformat():
            continue
        resultat[eid].setdefault("absences_dsn", []).append(arret)

    sorties = (
        supabase.table("employee_exits")
        .select(
            "employee_id,exit_type,status,last_working_day,exit_request_date,"
            "exit_reason,is_gross_misconduct,exit_notes"
        )
        .eq("company_id", company_id)
        .neq("status", "annulee")
        .execute()
    ).data or []
    for sortie in sorties:
        eid = str(sortie.get("employee_id"))
        jour = str(sortie.get("last_working_day") or "")[:10]
        if eid in resultat and debut_mois.isoformat() <= jour <= fin_mois.isoformat():
            resultat[eid]["sortie_dsn"] = sortie
            # Toutes, pour un mois à deux contrats : chacun la sienne (D3.2).
            resultat[eid].setdefault("sorties_dsn", []).append(sortie)

    # SMIC de la réduction générale d'un bulletin qui ne le porte pas : de
    # quoi le refaire comme le moteur (SMIC horaire de référence, cumul des
    # heures au bulletin précédent de l'année).
    reduction = (
        supabase.table("payroll_config")
        .select("config_data")
        .eq("config_key", "reduction_generale")
        .eq("is_active", True)
        .execute()
    ).data or []
    horaire = next(
        (
            (r.get("config_data") or {}).get("smic_reference_horaire")
            for r in reduction
            if isinstance(r.get("config_data"), dict)
        ),
        None,
    )
    if horaire:
        annee, mois = map(int, period.split("-"))
        anterieurs = (
            supabase.table("payslips")
            .select("employee_id,month,cumuls:payslip_data->cumuls")
            .eq("company_id", company_id)
            .eq("year", annee)
            .lt("month", mois)
            .in_("employee_id", employee_ids)
            .execute()
        ).data or []
        par_salarie_bulletins: Dict[str, List[Dict[str, Any]]] = {}
        for bulletin in anterieurs:
            par_salarie_bulletins.setdefault(str(bulletin.get("employee_id")), []).append(
                bulletin
            )
        for eid in resultat:
            resultat[eid]["smic_horaire_reduction"] = float(horaire)
            resultat[eid]["heures_cumulees_avant"] = heures_cumulees_avant(
                par_salarie_bulletins.get(eid, []), annee, mois, fiches.get(eid, {})
            )
    return resultat


def _specificites(employee: Dict[str, Any]) -> Dict[str, Any]:
    specificites = employee.get("specificites_paie")
    return specificites if isinstance(specificites, dict) else {}


def _affiliations(employee: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Celles du builder : au niveau racine, sinon sous specificites_paie."""
    brutes = employee.get("affiliations_psc") or _specificites(employee).get("affiliations_psc")
    return [a for a in (brutes or []) if isinstance(a, dict)]


def _collegue(employee: Dict[str, Any], year: int, month: int) -> Collegue:
    """Population comme le moteur (prévoyance cadre / non-cadre), adhésion du mois."""
    mutuelle = resolve_monthly_specificites(_specificites(employee), year, month).get("mutuelle")
    return Collegue(
        cadre=is_cadre(employee.get("statut")),
        adherent_mutuelle=isinstance(mutuelle, dict) and bool(mutuelle.get("adhesion")),
        affiliations=_affiliations(employee),
    )


def _collegues_affilies(
    company_id: str,
    employees: List[Dict[str, Any]],
    employee_ids: Optional[List[str]],
    year: int,
    month: int,
) -> List[Collegue]:
    """Les salariés de la société qui ont des affiliations, même hors de l'export."""
    fiches = employees
    if employee_ids:
        fiches = (
            supabase.table("employees")
            .select("id,statut,specificites_paie")
            .eq("company_id", company_id)
            .execute()
        ).data or []
    return [_collegue(f, year, month) for f in fiches if _affiliations(f)]


def _avec_affiliations_deduites(
    employee: Dict[str, Any], collegues: List[Collegue], year: int, month: int
) -> Dict[str, Any]:
    """Sans affiliations, celles de ses collègues comparables, le temps de
    l'export : rien n'est écrit sur la fiche. Sans modèle, la fiche reste telle
    quelle et le builder garde son avertissement."""
    lui = _collegue(employee, year, month)
    deduites = deduire_affiliations(
        cadre=lui.cadre, adherent_mutuelle=lui.adherent_mutuelle, collegues=collegues
    )
    if not deduites:
        return employee
    return {**employee, "affiliations_psc": deduites, "affiliations_psc_deduites": True}


def get_dsn_employees_data(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    year, month = map(int, period.split("-"))

    query = (
        supabase.table("employees")
        .select(
            """
        id,
        first_name,
        last_name,
        nir,
        sexe,
        date_naissance,
        lieu_naissance,
        adresse,
        contract_type,
        hire_date,
        statut,
        company_id,
        specificites_paie,
        matricule,
        job_title,
        is_temps_partiel,
        duree_hebdomadaire,
        classification_conventionnelle,
        nom_usage,
        nationalite,
        is_forfait_jour,
        contract_end_date,
        employment_status
        """
        )
        .eq("company_id", company_id)
    )
    if employee_ids:
        query = query.in_("id", employee_ids)
    employees_response = query.execute()
    employees = employees_response.data or []

    payslips_query = (
        supabase.table("payslips")
        .select(
            """
        id,
        employee_id,
        month,
        year,
        payslip_data,
        contract_period_id
        """
        )
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
    )
    if employee_ids:
        payslips_query = payslips_query.in_("employee_id", employee_ids)
    payslips_response = payslips_query.execute()
    payslips = payslips_response.data or []
    payslips_by_employee, ranges_par_salarie = _bulletins_par_salarie(payslips)
    # La fiche du mois : un mois qui appartient tout entier à un contrat rangé
    # par « Nouveau contrat » se déclare sur la fiche de ce contrat, comme son
    # bulletin se calcule [D4] ; sinon, la fiche du jour.
    employees = [fiche_du_mois(e, year, month) for e in employees]
    fiches_par_id = {str(e["id"]): e for e in employees}
    evenements = _evenements_dsn(
        company_id,
        period,
        sorted(set(payslips_by_employee) | set(ranges_par_salarie)),
        fiches_par_id,
    )

    employees_data = []
    collegues: Optional[List[Collegue]] = None
    totals = {
        "nombre_salaries": 0,
        "nombre_contrats": 0,
        "masse_salariale_brute": 0.0,
        "total_charges": 0.0,
        "total_net_imposable": 0.0,
        "total_pas": 0.0,
        "total_cotisations_salariales": 0.0,
        "total_cotisations_patronales": 0.0,
    }

    def _declarable(fiche: Dict[str, Any], bulletin: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """La fiche et les montants d'un bulletin, comme la DSN les déclare."""
        nonlocal collegues
        payslip_data = bulletin.get("payslip_data", {})
        if not isinstance(payslip_data, dict):
            return None
        fiche = _fiche_dsn(fiche, period)
        # Embauché après la reprise des DSN de l'ancien logiciel : pas
        # d'affiliations prévoyance / santé, que DSN-VAL exige (bloc 70).
        if not _affiliations(fiche):
            if collegues is None:
                collegues = _collegues_affilies(
                    company_id, employees, employee_ids, year, month
                )
            fiche = _avec_affiliations_deduites(fiche, collegues, year, month)
        return {"employee": fiche, "payslip": bulletin, "payslip_data": payslip_data, **_montants(payslip_data)}

    for employee in employees:
        eid = employee["id"]
        payslip = payslips_by_employee.get(eid)
        range_ = ranges_par_salarie.get(eid)
        if not payslip and not range_:
            continue
        # Arrêts, sortie et taux PAS reçus : ce que la DSN déclare et que le
        # bulletin ne porte pas (blocs 60, 62, rubriques 50.007 / 50.008).
        # Dans un mois à deux contrats, chacun reçoit ceux de ses dates (D3.2).
        evenements_salarie = evenements.get(eid, {})
        precedent: Optional[Dict[str, Any]] = None
        refus: Optional[str] = None
        if range_:
            periode = lecteur_contrats.contrat_range(str(range_["contract_period_id"])) or {}
            try:
                fiche_rangee = fiche_du_mois(employee, year, month, range_["contract_period_id"])
            except ValueError:
                refus = (
                    "la fiche de son contrat précédent n'a pas été rangée : "
                    "la DSN ne peut pas déclarer ce contrat."
                )
            else:
                precedent = _declarable(
                    {
                        **fiche_rangee,
                        **evenements_du_contrat(
                            evenements_salarie,
                            _jour(periode.get("date_debut")) or date(year, month, 1),
                            _jour(periode.get("date_fin")),
                            contrat_de_la_fiche=False,
                        ),
                    },
                    range_,
                )
        if payslip:
            evenements_fiche = (
                evenements_du_contrat(
                    evenements_salarie, debut_du_contrat(employee) or date(year, month, 1), None
                )
                if range_
                else evenements_salarie
            )
            ligne = _declarable({**employee, **evenements_fiche}, payslip)
            if ligne is None:
                continue
            if precedent:
                ligne["contrat_precedent"] = precedent
        elif precedent:
            # Le bulletin du nouveau contrat n'est pas encore généré : l'ancien
            # contrat se déclare seul, sur sa fiche rangée.
            ligne = precedent
            precedent = None
        else:
            ligne = {"employee": _fiche_dsn(dict(employee), period), "payslip": range_, **_montants({})}
        if refus:
            ligne["contrat_precedent_refus"] = refus
        employees_data.append(ligne)
        totals["nombre_salaries"] += 1
        for declare in (ligne, precedent):
            if not declare:
                continue
            totals["nombre_contrats"] += 1
            totals["masse_salariale_brute"] += declare["brut"]
            totals["total_charges"] += declare["cotisations_salariales"] + declare["cotisations_patronales"]
            totals["total_net_imposable"] += declare["net_imposable"]
            totals["total_pas"] += declare["pas"]
            totals["total_cotisations_salariales"] += declare["cotisations_salariales"]
            totals["total_cotisations_patronales"] += declare["cotisations_patronales"]

    return employees_data, totals


def _jour(valeur: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valeur or "")[:10])
    except ValueError:
        return None


def _fiche_dsn(employee: Dict[str, Any], period: str) -> Dict[str, Any]:
    """La fiche enrichie de ce que la DSN lit hors colonnes : IDCC et PCS de la
    classification, code BOETH du mois."""
    if not employee.get("idcc"):
        employee["idcc"] = ""
    classif = employee.get("classification_conventionnelle")
    if isinstance(classif, dict):
        employee.setdefault("pcs", classif.get("pcs") or classif.get("code_pcs") or "")
        employee.setdefault("idcc", classif.get("idcc") or employee.get("idcc") or "")
    try:
        boeth = oeth_queries.get_boeth_code_for_employee(employee.get("id", ""), period)
        if boeth:
            employee = {**employee, "boeth_code": boeth}
    except Exception:
        pass
    return employee


def _montants(payslip_data: Dict[str, Any]) -> Dict[str, Any]:
    """Brut, net imposable, PAS et cotisations d'un bulletin."""
    synthese = payslip_data.get("synthese_net")
    cot_sal, cot_pat, cotisations_list, _meta = extract_cotisations_from_payslip(payslip_data)
    return {
        "brut": float(payslip_data.get("salaire_brut", 0) or 0),
        "net_imposable": float(
            synthese.get("net_imposable", 0) if isinstance(synthese, dict) else 0
        ),
        "pas": extract_pas_amount(synthese) if isinstance(synthese, dict) else 0.0,
        "cotisations_salariales": cot_sal,
        "cotisations_patronales": cot_pat,
        "cotisations_detail": cotisations_list,
    }


#: Dit à l'aperçu d'un fichier d'essai : le verrou du dépôt réel ne le bloque pas.
AVERTISSEMENT_ESSAI = (
    "Fichier d'essai (S10.G00.00.005 = 01) : à déposer en mode test sur "
    "net-entreprises, il ne vaut pas déclaration. Le fichier réel reste bloqué."
)


_MOIS_DSN = (
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
    "Août", "Septembre", "Octobre", "Novembre", "Décembre",
)


def _bulletins_par_salarie(
    payslips: List[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Le bulletin du contrat de la fiche de chaque salarié, et celui du
    contrat rangé d'un mois partagé (`contract_period_id` rempli, D3)."""
    par_salarie: Dict[str, Dict[str, Any]] = {}
    ranges: Dict[str, Dict[str, Any]] = {}
    for bulletin in payslips:
        cible = ranges if bulletin.get("contract_period_id") else par_salarie
        cible[bulletin["employee_id"]] = bulletin
    return par_salarie, ranges


def check_dsn_data(
    company_id: str,
    period: str,
    employees_data: List[Dict[str, Any]],
    company_data: Dict[str, Any],
    *,
    essai: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    anomalies = []
    warnings = []

    siret = company_data.get("siret")
    siret_valid, siret_error = validate_siret(siret)
    if not siret_valid:
        anomalies.append(
            {
                "type": "error",
                "message": f"SIRET établissement : {siret_error}",
                "severity": "blocking",
                "employee_id": None,
                "employee_name": None,
            }
        )
    code_naf = company_data.get("code_naf")
    if not code_naf:
        anomalies.append(
            {
                "type": "error",
                "message": "Code NAF manquant pour l'établissement",
                "severity": "blocking",
                "employee_id": None,
                "employee_name": None,
            }
        )
    address = company_data.get("address")
    if not address or not isinstance(address, dict):
        warnings.append("Adresse établissement incomplète")
    else:
        if (
            not address.get("rue")
            or not address.get("ville")
            or not address.get("code_postal")
        ):
            warnings.append(
                "Adresse établissement incomplète (rue, ville ou code postal manquant)"
            )

    if essai:
        warnings.append(AVERTISSEMENT_ESSAI)
    elif not DEPOSABLE:
        anomalies.append(anomalie_non_deposable())

    for emp_data in employees_data:
        employee = emp_data["employee"]
        employee_id = employee.get("id")
        employee_name = (
            f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip()
        )
        annee_dsn, mois_dsn = (int(x) for x in period.split("-"))
        mois_partage = f"{_MOIS_DSN[mois_dsn]} {annee_dsn} : {employee_name} a deux contrats dans le mois"
        precedent = emp_data.get("contrat_precedent") or {}
        if emp_data.get("contrat_precedent_refus"):
            anomalies.append(
                {
                    "type": "error",
                    "message": f"{mois_partage}, mais {emp_data['contrat_precedent_refus']}",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
        if precedent and numero_du_contrat(precedent.get("employee") or {}) == numero_du_contrat(employee):
            # CT 40.009 CCH-12 : deux contrats d'un individu, deux numéros.
            anomalies.append(
                {
                    "type": "error",
                    "message": (
                        f"{mois_partage}, sous le même numéro de contrat DSN "
                        f"({numero_du_contrat(employee)}) : la DSN ne peut pas les distinguer. "
                        "Le numéro du nouveau contrat se change par le support."
                    ),
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
        if precedent and float(precedent.get("brut") or 0) <= 0:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié {employee_name} : brut ≤ 0 sur le bulletin du contrat précédent",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
        nir = employee.get("nir")
        nir_valid, nir_error = validate_nir_dsn(nir)
        if not nir_valid:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié {employee_name} : {nir_error}",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
        contract_type = employee.get("contract_type")
        if not contract_type:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié {employee_name} : type de contrat manquant",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
        adresse = employee.get("adresse")
        if not adresse or not isinstance(adresse, dict):
            warnings.append(f"Salarié {employee_name} : adresse incomplète")
        else:
            if (
                not adresse.get("rue")
                or not adresse.get("ville")
                or not adresse.get("code_postal")
            ):
                warnings.append(f"Salarié {employee_name} : adresse incomplète")
        brut = emp_data.get("brut", 0)
        net_imposable = emp_data.get("net_imposable", 0)
        if brut <= 0:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié {employee_name} : brut ≤ 0",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
        if net_imposable > brut:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Salarié {employee_name} : net imposable > brut (incohérence)",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                }
            )
        # La fiche du mois (adhésion datée comprise), comme le reste de l'export ;
        # un `null` en base vaut « pas de mutuelle », pas une erreur.
        annee_dsn, mois_dsn = map(int, period.split("-"))
        specificites = resolve_monthly_specificites(
            employee.get("specificites_paie"), annee_dsn, mois_dsn
        )
        if isinstance(specificites, dict):
            mutuelle = specificites.get("mutuelle") or {}
            prevoyance = specificites.get("prevoyance") or {}
            if contract_type in ["CDI", "CDD"] and not mutuelle.get("adhesion"):
                warnings.append(
                    f"Salarié {employee_name} : mutuelle absente alors que contrat actif"
                )
            if contract_type in ["CDI", "CDD"] and not prevoyance.get("adhesion"):
                warnings.append(
                    f"Salarié {employee_name} : prévoyance absente alors que contrat actif"
                )
        for manque in fiche_a_completer(employee):
            warnings.append(f"Salarié {employee_name} : {manque}")
        hire_date = employee.get("hire_date")
        if hire_date:
            try:
                year, month = map(int, period.split("-"))
                hire_dt = (
                    datetime.strptime(hire_date, "%Y-%m-%d")
                    if isinstance(hire_date, str)
                    else hire_date
                )
                period_dt = datetime(year, month, 1)
                if hire_dt.month == period_dt.month and hire_dt.year == period_dt.year:
                    warnings.append(
                        f"Salarié {employee_name} : entré en cours de mois ({hire_date})"
                    )
            except Exception:
                pass

    return anomalies, warnings


def preview_dsn(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]] = None,
    establishment_id: Optional[str] = None,
    *,
    essai: bool = False,
) -> Dict[str, Any]:
    company_data = get_company_data(company_id)
    employees_data, totals = get_dsn_employees_data(company_id, period, employee_ids)
    anomalies, warnings = check_dsn_data(
        company_id, period, employees_data, company_data, essai=essai
    )
    avis_pcs = avis_changements_pcs(employees_data, period, periodes_deposees(company_id))
    if avis_pcs:
        warnings = [*warnings, avis_pcs]

    employees_preview = []
    # Une ligne par bulletin : un mois à deux contrats en a deux (D3.2).
    bulletins_declares = [
        declare
        for emp_data in employees_data
        for declare in (emp_data.get("contrat_precedent"), emp_data)
        if declare
    ]
    for emp_data in bulletins_declares:
        employee = emp_data["employee"]
        cotisations_detail = emp_data.get("cotisations_detail", [])
        organismes = set()
        for coti in cotisations_detail:
            if isinstance(coti, dict):
                libelle = coti.get("libelle", "")
                if "URSSAF" in libelle.upper():
                    organismes.add("URSSAF")
                elif (
                    "RETRAITE" in libelle.upper()
                    or "AGIRC" in libelle.upper()
                    or "ARRCO" in libelle.upper()
                ):
                    organismes.add("RETRAITE")
                elif "PREVOYANCE" in libelle.upper():
                    organismes.add("PREVOYANCE")
                elif "MUTUELLE" in libelle.upper():
                    organismes.add("MUTUELLE")
        employees_preview.append(
            {
                "employee_id": employee.get("id"),
                "nom": employee.get("last_name", ""),
                "prenom": employee.get("first_name", ""),
                "nir": employee.get("nir"),
                "contrat_type": employee.get("contract_type"),
                "brut": emp_data.get("brut", 0),
                "net_imposable": emp_data.get("net_imposable", 0),
                "pas": emp_data.get("pas", 0),
                "cotisations_salariales": emp_data.get("cotisations_salariales", 0),
                "cotisations_patronales": emp_data.get("cotisations_patronales", 0),
                "organismes": list(organismes),
            }
        )

    organismes_summary = {}
    for emp_data in bulletins_declares:
        cotisations_detail = emp_data.get("cotisations_detail", [])
        for coti in cotisations_detail:
            if isinstance(coti, dict):
                libelle = coti.get("libelle", "")
                organisme = "AUTRE"
                if "URSSAF" in libelle.upper():
                    organisme = "URSSAF"
                elif (
                    "RETRAITE" in libelle.upper()
                    or "AGIRC" in libelle.upper()
                    or "ARRCO" in libelle.upper()
                ):
                    organisme = "RETRAITE"
                elif "PREVOYANCE" in libelle.upper():
                    organisme = "PREVOYANCE"
                elif "MUTUELLE" in libelle.upper():
                    organisme = "MUTUELLE"
                if organisme not in organismes_summary:
                    organismes_summary[organisme] = {
                        "organisme": organisme,
                        "code_organisme": None,
                        "nombre_salaries": set(),
                        "total_cotisations_salariales": 0.0,
                        "total_cotisations_patronales": 0.0,
                    }
                organismes_summary[organisme]["nombre_salaries"].add(
                    emp_data["employee"]["id"]
                )
                organismes_summary[organisme]["total_cotisations_salariales"] += float(
                    coti.get("montant_salarial", 0) or 0
                )
                organismes_summary[organisme]["total_cotisations_patronales"] += float(
                    coti.get("montant_patronal", 0) or 0
                )

    organismes_list = [
        {
            "organisme": org["organisme"],
            "code_organisme": org["code_organisme"],
            "nombre_salaries": len(org["nombre_salaries"]),
            "total_cotisations_salariales": org["total_cotisations_salariales"],
            "total_cotisations_patronales": org["total_cotisations_patronales"],
        }
        for org in organismes_summary.values()
    ]

    return {
        "period": period,
        "dsn_type": dsn_type,
        "establishment_siret": company_data.get("siret"),
        "nombre_salaries": totals["nombre_salaries"],
        "nombre_contrats": totals["nombre_contrats"],
        "masse_salariale_brute": totals["masse_salariale_brute"],
        "total_charges": totals["total_charges"],
        "total_net_imposable": totals["total_net_imposable"],
        "total_pas": totals["total_pas"],
        "organismes_concernes": organismes_list,
        "employees_preview": employees_preview,
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len([a for a in anomalies if a.get("severity") == "blocking"])
        == 0,
    }


def _neodes_norme_version() -> str:
    return DSN_NORME


def cotisations_complementaires_avant(
    company_id: str,
    company_data: Dict[str, Any],
    period: str,
    parametres: DsnSettings,
) -> Optional[Dict[str, Decimal]]:
    """Les cotisations de prévoyance et de santé des mois précédents du
    trimestre, par contrat, recalculées comme leur DSN depuis leurs bulletins.

    None hors fin de trimestre, ou si l'un de ces mois a été payé par l'ancien
    logiciel (bascule) : ses cotisations ne sont pas celles que Martine a
    déclarées, et le versement du trimestre se fait à la main.
    """
    if not est_fin_de_trimestre(period):
        return None
    bascule = lire_bascule(company_id)
    totaux: Dict[str, Decimal] = {}
    for mois in mois_precedents_du_trimestre(period):
        annee, numero = map(int, mois.split("-"))
        if bascule is not None and bascule.couvre(annee, numero):
            return None
        donnees, _ = get_dsn_employees_data(company_id, mois)
        if not donnees:
            continue
        try:
            dsn_du_mois, _ = build_parsed_dsn_from_payroll(
                company_data, donnees, mois, settings=parametres
            )
        except DsnBuildError:
            continue
        for ordre, montant in cotisations_par_contrat(dsn_du_mois.etablissement).items():
            totaux[ordre] = totaux.get(ordre, Decimal("0")) + montant
    return totaux


def generate_dsn_file(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]] = None,
    establishment_id: Optional[str] = None,
    *,
    essai: bool = False,
) -> bytes:
    """Génère un fichier DSN plat P26V01, relu et validé avant retour."""
    company_data = get_company_data(company_id)
    if establishment_id:
        # Filtre multi-établissement : si la fiche société expose des établissements
        establishments = company_data.get("establishments") or []
        if isinstance(establishments, list):
            for etab in establishments:
                if isinstance(etab, dict) and str(etab.get("id")) == str(establishment_id):
                    company_data = {
                        **company_data,
                        "siret": etab.get("siret") or company_data.get("siret"),
                        "code_naf": etab.get("code_naf") or company_data.get("code_naf"),
                        "address": etab.get("address") or company_data.get("address"),
                        "name": etab.get("name") or company_data.get("name"),
                    }
                    break

    employees_data, _totals = get_dsn_employees_data(company_id, period, employee_ids)
    period_formatted = period.replace("-", "_")
    if essai:
        file_name = f"dsn_essai_mensuelle_{period_formatted}.dsn"
    else:
        suffixe = "" if DEPOSABLE else SUFFIXE_NON_DEPOSABLE
        file_name = f"dsn_mensuelle_{period_formatted}{suffixe}.dsn"
    parametres = settings_repository.charger(company_id)
    try:
        dsn_file, build_warnings = build_parsed_dsn_from_payroll(
            company_data,
            employees_data,
            period,
            dsn_type=dsn_type,
            essai=essai,
            file_name=file_name,
            require_cotisation_codes=False,
            settings=parametres,
            cotisations_complementaires_avant=cotisations_complementaires_avant(
                company_id, company_data, period, parametres
            ),
            periodes_declarees=periodes_deposees(company_id),
        )
    except DsnBuildError as exc:
        raise ValueError(str(exc)) from exc

    # OETH annuelle (avril) : codes BOETH déjà injectés via get_dsn_employees_data ;
    # les totaux établissement OETH restent en avertissement si absents du modèle plat.
    year, month = map(int, period.split("-"))
    if month == 4:
        try:
            dsn_oeth = oeth_queries.build_dsn_payload(company_id, year - 1)
            if dsn_oeth.complement_oeth or dsn_oeth.cotisations_etablissement:
                build_warnings.append(
                    "Compléments OETH disponibles : vérifier le dépôt annuel complémentaire."
                )
        except Exception:
            pass

    content = encode_dsn_bytes(dsn_file)
    # Relecture + validation structurelle
    parsed = parse_dsn_content(content, file_name=file_name)
    if parsed.envoi.norme != DSN_NORME:
        raise ValueError(f"Norme DSN inattendue après génération : {parsed.envoi.norme}")
    from app.modules.dsn_import.domain.model import ParsedDsnSet

    anomalies = validate_parsed_dsn(ParsedDsnSet(files=[parsed], warnings=list(build_warnings)))
    blocking = [a for a in anomalies if a.get("severity") == "blocking"]
    if blocking:
        messages = "; ".join(a.get("message", "") for a in blocking[:5])
        raise ValueError(f"DSN générée invalide : {messages}")
    return content


def generate_dsn_xml(
    company_id: str,
    period: str,
    dsn_type: str,
    employee_ids: Optional[List[str]] = None,
    establishment_id: Optional[str] = None,
    *,
    essai: bool = False,
) -> bytes:
    """Alias historique : produit désormais un fichier plat P26V01 (.dsn)."""
    return generate_dsn_file(
        company_id, period, dsn_type, employee_ids, establishment_id, essai=essai
    )
