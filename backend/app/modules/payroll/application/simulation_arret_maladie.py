"""
Simulation arrêt maladie — alignée sur calculer_maintien (même moteur que le bulletin).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

from app.modules.employees.domain.salary_timeline import salaire_actif_a_date
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.maintenance_settings.application.queries import get_maintenance_settings
from app.modules.payroll.application.simulation_queries import (
    company_to_payroll_payload,
    employee_to_payroll_payload,
    load_baremes,
    load_company,
    load_employee,
)
from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien
from app.modules.payroll.schemas.requests import SimulationArretMaladieRequest
from app.modules.users.schemas.responses import User


def _hire_date_pour_anciennete(reference: date, mois: int) -> date:
    """Date d'embauche synthétique donnant ``mois`` mois d'ancienneté à ``reference``."""
    total_mois = reference.year * 12 + (reference.month - 1) - max(0, mois)
    annee, mois_idx = divmod(total_mois, 12)
    return date(annee, mois_idx + 1, 1)


def _employee_payload_for_contexte(
    emp: Dict[str, Any],
    company: Dict[str, Any],
    *,
    salaire_a_date: date,
) -> Dict[str, Any]:
    """Aligné sur les autres simulations paie + champs requis par calculer_maintien."""
    employee_map = employee_to_payroll_payload(emp, company)
    timeline = EmployeeRepository().get_salary_history(
        str(emp.get("id") or ""),
        str(emp.get("company_id") or ""),
    )
    employee_map["salaire_base"] = salaire_actif_a_date(
        timeline,
        salaire_a_date,
        float(employee_map.get("salaire_base") or 0.0),
    )
    employee_map.update(
        {
            "nir": emp.get("nir") or "",
            "prevoyance": emp.get("prevoyance") or "NON",
            "is_temps_partiel": bool(emp.get("is_temps_partiel")),
            "avantages_en_nature": emp.get("avantages_en_nature") or {},
            "mutuelle": emp.get("mutuelle") or {},
            "titres_restaurant": emp.get("titres_restaurant") or {},
            "transport": emp.get("transport") or {},
            "is_alsace_moselle": bool(emp.get("is_alsace_moselle", False)),
        }
    )
    return employee_map


def run_simulation_arret_maladie(
    body: SimulationArretMaladieRequest,
    current_user: User,
) -> Dict[str, Any]:
    """
    Charge employé + entreprise, contexte paie, exécute calculer_maintien sur la période d'arrêt.
    Contrôle : entreprise active + droit RH sur cette entreprise ; employé de l'entreprise active.
    """
    active_cid = current_user.active_company_id
    if not active_cid:
        raise ValueError(
            "Sélectionnez une entreprise active pour lancer la simulation."
        )
    if not current_user.is_platform_admin and not current_user.has_rh_access_in_company(
        str(active_cid)
    ):
        raise PermissionError(
            "Accès refusé : droits RH requis pour la simulation arrêt maladie."
        )

    emp_company = str(active_cid)
    employee_row = load_employee(body.employee_id, emp_company)
    company_row = load_company(emp_company)
    baremes = load_baremes()

    settings_model = get_maintenance_settings(emp_company)
    settings_dict = settings_model.model_dump(mode="json")

    date_fin_arret = body.date_debut + timedelta(days=max(0, body.duree_jours - 1))
    date_debut_periode = body.date_debut
    date_fin_periode = date_fin_arret

    temps_travail_row = (
        employee_row.get("temps_travail")
        if isinstance(employee_row.get("temps_travail"), dict)
        else {}
    )
    arret_data: Dict[str, Any] = {
        "arret_type": body.arret_type,
        "date_debut": body.date_debut.isoformat(),
        "date_fin": date_fin_arret.isoformat(),
        "subrogation_active": bool(body.subrogation_active),
        "nombre_enfants": int(body.nombre_enfants),
        "is_temps_partiel": bool(
            employee_row.get("is_temps_partiel")
            or temps_travail_row.get("is_temps_partiel")
            or False
        ),
        "quotite_temps_partiel": float(temps_travail_row.get("quotite") or 1.0),
        "historique_arrets_annee": [],
        "date_dernier_arret": None,
        "salaire_periode_reelle": 0.0,
    }

    employee_map = _employee_payload_for_contexte(
        employee_row,
        company_row,
        salaire_a_date=body.date_debut,
    )

    # Overrides « what-if » : n'altèrent que la simulation (pas la fiche salarié).
    if body.salaire_base_override is not None:
        employee_map["salaire_base"] = float(body.salaire_base_override)
    if body.statut_override is not None:
        employee_map["statut"] = body.statut_override
    if body.anciennete_mois_override is not None:
        employee_map["date_entree"] = _hire_date_pour_anciennete(
            body.date_debut, int(body.anciennete_mois_override)
        ).isoformat()

    company_map = company_to_payroll_payload(company_row)
    contexte = ChargerContexte(employee_map, company_map, baremes)

    resultats_maintien = calculer_maintien(
        arret_data,
        contexte,
        settings_dict,
        date_debut_periode,
        date_fin_periode,
    )

    salaire_mensuel = float(contexte.salaire_base_mensuel or 0.0)
    ijss = float(resultats_maintien.get("ijss", {}).get("ijss_theorique") or 0.0)
    maintien_verse = float(
        resultats_maintien.get("maintien", {}).get("maintien_verse") or 0.0
    )
    complement = float(
        resultats_maintien.get("maintien", {}).get("complement_employeur") or 0.0
    )

    prevoyance = resultats_maintien.get("prevoyance", {}) or {}
    prevoyance_montant = float(prevoyance.get("montant") or 0.0)
    maintien_info = resultats_maintien.get("maintien", {}) or {}

    impact_net_salarie = maintien_verse - salaire_mensuel
    charges_patronales_estimees = complement * 0.42
    cout_employeur_total = complement + charges_patronales_estimees

    anciennete_mois = int(resultats_maintien.get("anciennete_mois") or 0)

    return {
        "scenario": "arret_maladie",
        "parametres": {
            "duree_jours": body.duree_jours,
            "arret_type": body.arret_type,
            "subrogation_active": body.subrogation_active,
            "date_debut": body.date_debut.isoformat(),
            "nombre_enfants": body.nombre_enfants,
            "salaire_base_override": body.salaire_base_override,
            "statut_override": body.statut_override,
            "anciennete_mois_override": body.anciennete_mois_override,
        },
        "profil": {
            "statut": resultats_maintien.get("statut") or "",
            "est_cadre": bool(resultats_maintien.get("est_cadre")),
            "anciennete_mois": anciennete_mois,
            "anciennete_annees": round(anciennete_mois / 12, 1),
            "duree_maintien_legale_jours": int(
                maintien_info.get("duree_maintien_legale_jours") or 0
            ),
            "duree_par_taux_jours": int(maintien_info.get("duree_par_taux_jours") or 0),
            "carence_employeur_jours": int(
                maintien_info.get("carence_employeur_jours") or 0
            ),
        },
        "resultats_maintien": resultats_maintien,
        "synthese": {
            "salaire_mensuel_base": round(salaire_mensuel, 2),
            "impact_net_salarie": round(impact_net_salarie, 2),
            "cout_employeur_complement": round(complement, 2),
            "charges_patronales_estimees": round(charges_patronales_estimees, 2),
            "cout_employeur_total": round(cout_employeur_total, 2),
            "ijss_theorique": round(ijss, 2),
            "maintien_verse": round(maintien_verse, 2),
            "prevoyance_montant": round(prevoyance_montant, 2),
        },
        "alertes": list(resultats_maintien.get("alertes") or []),
    }
