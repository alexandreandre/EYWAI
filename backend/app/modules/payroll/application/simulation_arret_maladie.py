"""
Simulation arrêt maladie — alignée sur calculer_maintien (même moteur que le bulletin).
"""

from __future__ import annotations

import calendar
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Callable, Dict, List

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
from app.modules.payroll.engine import legal_constants as lc
from app.modules.payroll.engine.calcul_brut import (
    _get_salaire_horaire_base,
    _heures_journalieres_contrat,
)
from app.modules.payroll.engine.calcul_brut_forfait import _diviseur_jour_absence
from app.modules.payroll.engine.calcul_inverse import _calculer_bulletin_avec_brut_override
from app.modules.payroll.engine.contexte import ChargerContexte, ContextePaie
from app.modules.payroll.engine.ijss_bulletin import compute_ijss_csg_lines
from app.modules.payroll.engine.maintien_salaire_service import (
    _quote_part_hs_structurelles_journaliere,
    calculer_maintien,
)
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


def _jours_ouvres(debut: date, fin: date) -> int:
    return sum(
        1 for k in range((fin - debut).days + 1) if (debut + timedelta(days=k)).weekday() < 5
    )


def salaire_perdu_sur_la_periode(contexte: ContextePaie, debut: date, fin: date) -> float:
    """Ce que le bulletin retient pour les jours d'arrêt de la période, arrondi une fois
    comme sa ligne de retenue (`calcul_brut`) : chaque jour ouvré à la référence journalière
    légale au taux horaire de base, plus la quote-part d'heures sup structurelles de la
    journée (« Réduction HS structurelles ») ; au forfait jours, le salaire au diviseur
    d'absence de la société (`calcul_brut_forfait`)."""
    jours = _jours_ouvres(debut, fin)
    if contexte.is_forfait_jour:
        salaire = float(contexte.salaire_base_mensuel or 0.0)
        return round(jours * salaire / _diviseur_jour_absence(contexte), 2)
    duree = float(contexte.duree_hebdo_contrat or lc.DUREE_LEGALE_HEBDO)
    taux = _get_salaire_horaire_base(contexte, duree)
    par_jour = _heures_journalieres_contrat(duree) * taux + _quote_part_hs_structurelles_journaliere(
        contexte, duree, taux
    )
    return round(jours * par_jour, 2)


@dataclass(frozen=True)
class ImpactDuMois:
    annee: int
    mois: int
    salaire_perdu: float
    maintien_verse: float
    ijss: float
    ijss_nettes: float
    impact: float


def _mois_de_l_arret(debut: date, fin: date) -> List[tuple[int, int, date, date]]:
    """Les mois que touche l'arrêt : (année, mois, premier et dernier jour d'arrêt du mois)."""
    sortie = []
    jour = debut
    while jour <= fin:
        dernier = date(jour.year, jour.month, calendar.monthrange(jour.year, jour.month)[1])
        borne = min(dernier, fin)
        sortie.append((jour.year, jour.month, jour, borne))
        jour = borne + timedelta(days=1)
    return sortie


def impact_net_de_l_arret(
    contexte: ContextePaie,
    arret: Dict[str, Any],
    settings: Dict[str, Any],
    debut: date,
    fin: date,
    net_avant_impot: Callable[[float, int, int], float],
) -> List[ImpactDuMois]:
    """Impact de l'arrêt sur le net avant impôt du salarié, mois par mois, comme le bulletin :
    le net du mois avec l'arrêt (salaire moins la retenue des jours d'arrêt, plus le maintien
    employeur) moins le net sans arrêt, plus les IJSS nettes de leur CSG/CRDS (versées par
    l'employeur en subrogation, par la CPAM sinon : le salarié les touche dans les deux cas).

    `net_avant_impot(brut, annee, mois)` donne le net d'un mois pour un brut : le bulletin
    d'essai du moteur dans la simulation, une fonction simple dans les tests.
    """
    salaire = float(contexte.salaire_base_mensuel or 0.0)
    baremes_maladie = (contexte.baremes or {}).get("maladie")
    sortie: List[ImpactDuMois] = []
    for annee, mois, d, f in _mois_de_l_arret(debut, fin):
        resultats = calculer_maintien(arret, contexte, settings, d, f)
        maintien = float((resultats.get("maintien") or {}).get("maintien_verse") or 0.0)
        ijss = float((resultats.get("ijss") or {}).get("ijss_theorique") or 0.0)
        perdu = salaire_perdu_sur_la_periode(contexte, d, f)
        _, _, ijss_nettes = compute_ijss_csg_lines(ijss, baremes_maladie)
        impact = (
            net_avant_impot(salaire - perdu + maintien, annee, mois)
            - net_avant_impot(salaire, annee, mois)
            + ijss_nettes
        )
        sortie.append(
            ImpactDuMois(annee, mois, perdu, round(maintien, 2), round(ijss, 2), ijss_nettes, round(impact, 2))
        )
    return sortie


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

    # Le net d'un mois pour un brut : le bulletin d'essai du moteur (celui du calcul
    # inverse), sur une copie du contexte. Il retirait autrefois tout le salaire du mois
    # du seul maintien : −2 142,19 € pour 14 jours d'arrêt subrogé sur 2 200 € (19/10/2026).
    def net_avant_impot(brut: float, annee: int, mois: int) -> float:
        bulletin = _calculer_bulletin_avec_brut_override(
            brut,
            employee_map,
            company_map,
            baremes,
            {},
            {},
            month=mois,
            year=annee,
            contexte_de_base=contexte,
        )
        return float((bulletin.get("synthese_net") or {}).get("net_social_avant_impot") or 0.0)

    impact_par_mois = impact_net_de_l_arret(
        contexte, arret_data, settings_dict, date_debut_periode, date_fin_periode, net_avant_impot
    )
    impact_net_salarie = sum(m.impact for m in impact_par_mois)
    salaire_perdu = sum(m.salaire_perdu for m in impact_par_mois)
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
            "salaire_perdu": round(salaire_perdu, 2),
            "impact_net_par_mois": [asdict(m) for m in impact_par_mois],
            "cout_employeur_complement": round(complement, 2),
            "charges_patronales_estimees": round(charges_patronales_estimees, 2),
            "cout_employeur_total": round(cout_employeur_total, 2),
            "ijss_theorique": round(ijss, 2),
            "maintien_verse": round(maintien_verse, 2),
            "prevoyance_montant": round(prevoyance_montant, 2),
        },
        "alertes": list(resultats_maintien.get("alertes") or []),
    }
