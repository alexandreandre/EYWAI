"""
Simulation arrêt maladie — alignée sur calculer_maintien (même moteur que le bulletin).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

from app.core.database import supabase
from app.modules.maintenance_settings.application.queries import get_maintenance_settings
from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien
from app.modules.payroll.schemas.requests import SimulationArretMaladieRequest
from app.modules.users.schemas.responses import User


def _company_payload_for_contexte(company_row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "entreprise": {
            "identification": {
                "raison_sociale": company_row.get("name")
                or company_row.get("legal_name")
                or "",
                "siret": str(company_row.get("siret") or ""),
                "adresse": company_row.get("address")
                or company_row.get("headquarters_address")
                or "",
            },
            "parametres_paie": {
                "effectif": int(
                    company_row.get("effectif")
                    or company_row.get("employee_count")
                    or 0
                ),
            },
        }
    }


def _employee_payload_for_contexte(emp: Dict[str, Any]) -> Dict[str, Any]:
    sdb = emp.get("salaire_de_base") or {}
    if isinstance(sdb, dict):
        salaire_base = float(sdb.get("valeur") or 0)
    else:
        salaire_base = float(emp.get("salaire_base_mensuel") or 0)
    return {
        "first_name": emp.get("first_name") or "",
        "last_name": emp.get("last_name") or "",
        "nir": emp.get("nir") or "",
        "statut": emp.get("statut") or "Non-Cadre",
        "emploi": emp.get("job_title") or "",
        "duree_hebdomadaire": float(emp.get("duree_hebdomadaire") or 35),
        "date_entree": emp.get("hire_date") or "",
        "salaire_base": salaire_base,
        "taux_prelevement_source": float(emp.get("taux_prelevement_source") or 0),
        "prevoyance": emp.get("prevoyance") or "NON",
        "is_temps_partiel": bool(emp.get("is_temps_partiel")),
        "avantages_en_nature": emp.get("avantages_en_nature") or {},
        "convention_collective": emp.get("convention_collective") or {},
        "classification_conventionnelle": emp.get("classification_conventionnelle")
        or {},
        "mutuelle": emp.get("mutuelle") or {},
        "titres_restaurant": emp.get("titres_restaurant") or {},
        "transport": emp.get("transport") or {},
        "is_alsace_moselle": bool(emp.get("is_alsace_moselle", False)),
    }


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
    if not current_user.is_super_admin and not current_user.has_rh_access_in_company(
        str(active_cid)
    ):
        raise PermissionError(
            "Accès refusé : droits RH requis pour la simulation arrêt maladie."
        )

    emp_res = (
        supabase.table("employees")
        .select("*")
        .eq("id", body.employee_id)
        .maybe_single()
        .execute()
    )
    if not emp_res.data:
        raise LookupError("Employé introuvable.")

    employee_row = emp_res.data
    emp_company = str(employee_row.get("company_id") or "")
    if emp_company != str(active_cid):
        raise LookupError("Employé introuvable.")

    co_res = (
        supabase.table("companies")
        .select("*")
        .eq("id", emp_company)
        .maybe_single()
        .execute()
    )
    company_row = co_res.data or {}

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

    employee_map = _employee_payload_for_contexte(employee_row)
    company_map = _company_payload_for_contexte(company_row)
    contexte = ChargerContexte(employee_map, company_map, {})

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

    impact_net_salarie = maintien_verse - salaire_mensuel
    charges_patronales_estimees = complement * 0.42
    cout_employeur_total = complement + charges_patronales_estimees

    return {
        "scenario": "arret_maladie",
        "parametres": {
            "duree_jours": body.duree_jours,
            "arret_type": body.arret_type,
            "subrogation_active": body.subrogation_active,
            "date_debut": body.date_debut.isoformat(),
            "nombre_enfants": body.nombre_enfants,
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
        },
        "alertes": list(resultats_maintien.get("alertes") or []),
    }
