"""
Agrégation des anomalies pré-paie (revue avant lancement).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.shared.domain.pluriel import pluriel
from app.core.database import supabase
from app.modules.badgeuse.application import punch_service as badgeuse_service
from app.modules.payroll.application.periode_variables_service import (
    bulletins_sur_une_autre_fenetre,
    resoudre_fenetre_variables,
)
from app.modules.payroll.infrastructure import preflight_repository
from app.modules.payroll.schemas.preflight_responses import (
    HeuresSurArretSalarie,
    PreflightAnomaly,
    PreflightAnomalyCounts,
    PreflightAnomalyResolution,
    PreflightAnomaliesResponse,
    PreflightDayEcartDetail,
)
from app.modules.schedules.application.periode_a_saisir_service import (
    charger_periodes_a_saisir,
    resume_api,
)
from app.modules.schedules.domain.ecart_rules import (
    compute_day_ecarts,
    compute_heures_supplementaires,
    compute_row_status,
    detect_absence_conflict_days,
    month_period_bounds,
    sum_hours,
    validated_absence_days_in_month,
)
from app.modules.schedules.domain.periode_a_saisir import libelle_plages, raisons_en_clair
from app.shared.domain.employment_rules import is_forfait_jour
from app.shared.domain.periode_variables import semaines_iso

OPEN_STATUSES = frozenset({"a_traiter"})


def _anomaly_id(employee_id: str, anomaly_type: str) -> str:
    return f"{employee_id}:{anomaly_type}"


def _employee_name(first: Any, last: Any) -> str:
    return f"{str(first or '').strip()} {str(last or '').strip()}".strip()


def _resolution_key(employee_id: str, anomaly_type: str) -> str:
    return f"{employee_id}:{anomaly_type}"


def _merge_resolution(
    anomaly: PreflightAnomaly,
    resolution_row: Optional[Dict[str, Any]],
) -> PreflightAnomaly:
    if not resolution_row:
        return anomaly
    status = str(resolution_row.get("status") or "justifie")
    if status not in ("justifie", "resolu"):
        status = "justifie"
    anomaly.status = status  # type: ignore[assignment]
    anomaly.resolution = PreflightAnomalyResolution(
        status=status,  # type: ignore[arg-type]
        motif=resolution_row.get("motif"),
        commentaire=resolution_row.get("commentaire"),
        resolved_by=str(resolution_row.get("resolved_by") or "") or None,
        resolved_at=resolution_row.get("resolved_at"),
    )
    return anomaly


def _build_counts(anomalies: List[PreflightAnomaly]) -> PreflightAnomalyCounts:
    counts = PreflightAnomalyCounts()
    for a in anomalies:
        if a.type == "ecart_heures":
            counts.ecart_heures += 1
        elif a.type == "heures_non_saisies":
            counts.heures_non_saisies += 1
        elif a.type == "pointage":
            counts.pointage += 1
        elif a.type == "conflit_absence":
            counts.conflit_absence += 1
        elif a.type == "hs_routing_pending":
            counts.hs_routing_pending += 1
        elif a.type == "hs_pointage_a_valider":
            counts.hs_pointage_a_valider += 1
        elif a.type == "fenetre_modifiee":
            counts.fenetre_modifiee += 1
        if a.severity == "bloquant":
            counts.bloquant += 1
        else:
            counts.a_verifier += 1
    return counts


def build_preflight_anomalies(
    company_id: str, year: int, month: int
) -> PreflightAnomaliesResponse:
    emp_res = (
        supabase.table("employees")
        # Entrée et fin de contrat : la période à saisir s'arrête à la sortie,
        # comme au garde-fou de génération.
        .select(
            "id, first_name, last_name, statut, is_forfait_jour, team_id, "
            "hire_date, contract_end_date"
        )
        .eq("company_id", company_id)
        # En sortie : départ créé, dernier bulletin encore à faire ; ses heures
        # et ses conflits se contrôlent comme ceux d'un actif.
        .in_("employment_status", ["actif", "en_sortie"])
        .execute()
    )
    employees = emp_res.data or []
    if not employees:
        return PreflightAnomaliesResponse(
            year=year,
            month=month,
            total=0,
            total_open=0,
            total_treated=0,
            counts=PreflightAnomalyCounts(),
            anomalies=[],
        )

    employee_ids = [str(e["id"]) for e in employees]
    emp_by_id = {str(e["id"]): e for e in employees}

    sched_res = (
        supabase.table("employee_schedules")
        .select("employee_id, planned_calendar, actual_hours")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
        .in_("employee_id", employee_ids)
        .execute()
    )
    schedule_by_emp = {str(r["employee_id"]): r for r in (sched_res.data or [])}
    # Un seul juge de « ce qui manque » : mois civil ∪ fenêtre des variables,
    # comme le moteur et le garde-fou de génération.
    periodes = charger_periodes_a_saisir(company_id, employees, year, month)
    # L'écart d'heures se juge lui aussi sur la fenêtre des variables, pas sur
    # le mois civil : les jours d'après l'arrêté relèvent du mois suivant (une
    # salariée pointée à 0 h du 21 au 25/09 était marquée bloquante en septembre).
    jours_de_la_fenetre = _jours_de_la_fenetre(
        company_id, employee_ids, periodes, year, month, schedule_by_emp
    )

    absences: List[Dict[str, Any]] = []
    try:
        from app.modules.absences.infrastructure.repository import absence_repository

        absences = absence_repository.list_validated_for_employees(employee_ids)
    except Exception:
        absences = []

    absences_by_emp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in absences:
        absences_by_emp[str(a.get("employee_id", ""))].append(a)

    start, end = month_period_bounds(year, month)
    badgeuse_summaries = badgeuse_service.get_company_period_summary(
        company_id=company_id,
        start=start,
        end=end,
        employee_ids=employee_ids,
    )

    resolution_rows = preflight_repository.list_resolutions(company_id, year, month)
    resolutions_by_key = {
        _resolution_key(str(r["employee_id"]), str(r["anomaly_type"])): r
        for r in resolution_rows
    }

    from app.modules.schedules.infrastructure import punch_accounting_repository as par

    pending_punch_reviews = par.list_overtime_reviews(
        company_id, year=year, month=month, status="pending"
    )
    pending_by_emp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in pending_punch_reviews:
        pending_by_emp[str(row["employee_id"])].append(row)

    anomalies: List[PreflightAnomaly] = []
    heures_sur_arret: List[HeuresSurArretSalarie] = []

    for emp in employees:
        eid = str(emp["id"])
        name = _employee_name(emp.get("first_name"), emp.get("last_name"))
        team_id = str(emp["team_id"]) if emp.get("team_id") else None
        forfait = is_forfait_jour(emp.get("statut"), emp.get("is_forfait_jour"))

        par_mois = jours_de_la_fenetre.get(eid)
        if par_mois is None:
            par_mois = [_jours_du_calendrier(schedule_by_emp.get(eid))]
        planned_days = [d for prevus, _ in par_mois for d in prevus]
        actual_days = [d for _, reels in par_mois for d in reels]

        heures_prevues = sum_hours([d.get("heures_prevues") for d in planned_days])
        heures_faites = sum_hours([d.get("heures_faites") for d in actual_days])
        ecart = heures_faites - heures_prevues
        periode = periodes.get(eid)
        if periode is not None and periode.conflits:
            heures_sur_arret.append(
                HeuresSurArretSalarie(
                    employee_id=eid,
                    jours=[c.en_detail() for c in periode.conflits],
                )
            )
        row_status = compute_row_status(
            planned_days,
            actual_days,
            year,
            month,
            forfait,
            a_saisir=(periode.statut == "a_saisir") if periode is not None else None,
        )

        if row_status == "a_saisir":
            resume = resume_api(periode) if periode is not None else {}
            bloquants = [j.jour for j in periode.bloquants] if periode is not None else []
            if bloquants:
                debut, fin = periode.fenetre
                message = (
                    f"{pluriel(len(bloquants), 'jour')} à saisir dans la fenêtre des variables "
                    f"({debut:%d/%m} → {fin:%d/%m}) : {libelle_plages(bloquants)} "
                    f"({raisons_en_clair(periode.bloquants)})."
                )
            else:
                message = "Calendrier du mois incomplet — heures planifiées manquantes."
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "heures_non_saisies"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="heures_non_saisies",
                severity="bloquant",
                status="a_traiter",
                heures_prevues=heures_prevues,
                heures_faites=heures_faites,
                ecart=ecart,
                is_forfait_jour=forfait,
                jours_manquants=resume.get("jours_manquants", []),
                fenetre=resume.get("fenetre"),
                message=message,
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(_resolution_key(eid, "heures_non_saisies")),
                )
            )

        if row_status == "saisi_avec_ecart":
            # Jour par jour, mois par mois : les numéros de jour se répètent
            # d'un mois à l'autre dans une fenêtre à cheval.
            day_details = [
                d
                for prevus, reels in par_mois
                for d in compute_day_ecarts(prevus, reels, forfait=forfait)
            ]
            heures_sup = sum(
                compute_heures_supplementaires(prevus, reels) for prevus, reels in par_mois
            )
            sub_type = "heures_sup" if heures_sup > 0 else None
            unit = "j" if forfait else "h"
            message = (
                f"Écart significatif entre planifié et réel "
                f"({ecart:+.1f}{unit})."
            )
            if heures_sup > 0:
                message += f" Heures sup. détectées : {heures_sup:.1f}h."

            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "ecart_heures"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="ecart_heures",
                severity="bloquant",
                status="a_traiter",
                heures_prevues=heures_prevues,
                heures_faites=heures_faites,
                ecart=ecart if not forfait else None,
                is_forfait_jour=forfait,
                sub_type=sub_type,
                detail_jours=[
                    PreflightDayEcartDetail(**d) for d in day_details
                ],
                message=message,
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(_resolution_key(eid, "ecart_heures")),
                )
            )

        validated_days = validated_absence_days_in_month(
            absences_by_emp.get(eid, []), year, month
        )
        conflict_days = detect_absence_conflict_days(
            planned_days, validated_days, year, month
        )
        if conflict_days:
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "conflit_absence"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="conflit_absence",
                severity="a_verifier",
                status="a_traiter",
                conflict_days=conflict_days,
                message=(
                    f"Conflit entre absences validées et calendrier "
                    f"({pluriel(len(conflict_days), 'jour')})."
                ),
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(_resolution_key(eid, "conflit_absence")),
                )
            )

        badge_summary = badgeuse_summaries.get(eid)
        if badge_summary and badge_summary.days_with_anomalies > 0:
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "pointage"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="pointage",
                severity="a_verifier",
                status="a_traiter",
                days_with_pointage_anomalies=badge_summary.days_with_anomalies,
                message=(
                    f"{pluriel(badge_summary.days_with_anomalies, 'jour')} avec pointage "
                    "incohérent (entrée/sortie)."
                ),
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(_resolution_key(eid, "pointage")),
                )
            )

        emp_pending = pending_by_emp.get(eid) or []
        if emp_pending:
            total_hs = round(
                sum(float(r.get("overtime_hours") or 0) for r in emp_pending), 2
            )
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "hs_pointage_a_valider"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="hs_pointage_a_valider",
                severity="a_verifier",
                status="a_traiter",
                ecart=total_hs,
                message=(
                    f"{pluriel(len(emp_pending), 'jour')} avec HS pointage à valider "
                    f"({total_hs:.2f} h)."
                ),
            )
            anomalies.append(
                _merge_resolution(
                    anomaly,
                    resolutions_by_key.get(
                        _resolution_key(eid, "hs_pointage_a_valider")
                    ),
                )
            )

    from app.modules.modulation.application import overtime_routing_queries as otr_q
    from app.modules.modulation.infrastructure import repository as mod_repo

    mod_settings = mod_repo.get_modulation_settings(company_id)
    if mod_settings.hs_routing_policy == "manual":
        routing_rows = otr_q.list_overtime_routing(company_id, year, month)
        for row in routing_rows:
            if row.get("status") == "validated":
                continue
            eid = str(row["employee_id"])
            emp = emp_by_id.get(eid) or {}
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "hs_routing_pending"),
                employee_id=eid,
                employee_name=str(row.get("employee_name") or _employee_name(
                    emp.get("first_name"), emp.get("last_name")
                )),
                team_id=str(emp["team_id"]) if emp.get("team_id") else None,
                type="hs_routing_pending",
                severity="bloquant",
                status="a_traiter",
                message=(
                    f"{float(row.get('total_hs_hours') or 0):.1f} h sup. — "
                    "décision payer / compteur requise."
                ),
            )
            anomalies.append(anomaly)

    # Bulletins du mois calculés sur une fenêtre qui a changé depuis : la paie
    # n'est plus celle que la gestionnaire croit avoir lancée.
    fenetre = resoudre_fenetre_variables(company_id, year, month)
    for ligne in bulletins_sur_une_autre_fenetre(company_id, year, month, fenetre):
        eid = str(ligne.get("employee_id") or "")
        emp = emp_by_id.get(eid)
        if not emp:
            continue
        ancien_debut, ancienne_fin = str(ligne.get("debut") or ""), str(ligne.get("fin") or "")
        ancienne = (
            f"{ancien_debut[8:10]}/{ancien_debut[5:7]} → {ancienne_fin[8:10]}/{ancienne_fin[5:7]}"
        )
        anomalies.append(
            PreflightAnomaly(
                id=_anomaly_id(eid, "fenetre_modifiee"),
                employee_id=eid,
                employee_name=_employee_name(emp.get("first_name"), emp.get("last_name")),
                team_id=str(emp["team_id"]) if emp.get("team_id") else None,
                type="fenetre_modifiee",
                severity="a_verifier",
                status="a_traiter",
                is_forfait_jour=is_forfait_jour(emp.get("statut"), emp.get("is_forfait_jour")),
                fenetre={
                    "debut": fenetre.debut.isoformat(),
                    "fin": fenetre.fin.isoformat(),
                    "semaines": semaines_iso(fenetre.debut, fenetre.fin),
                    "origine": fenetre.origine,
                },
                message=(
                    f"Bulletin calculé sur la fenêtre {ancienne} ; celle du mois est "
                    f"{fenetre.debut:%d/%m} → {fenetre.fin:%d/%m} : à régénérer."
                ),
            )
        )

    counts = _build_counts(anomalies)
    total_open = sum(1 for a in anomalies if a.status in OPEN_STATUSES)
    total_treated = len(anomalies) - total_open

    return PreflightAnomaliesResponse(
        year=year,
        month=month,
        total=len(anomalies),
        total_open=total_open,
        total_treated=total_treated,
        counts=counts,
        anomalies=anomalies,
        heures_sur_arret=heures_sur_arret,
    )


def justify_anomaly(
    *,
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    anomaly_type: str,
    motif: str,
    commentaire: Optional[str],
    resolved_by: str,
) -> Dict[str, Any]:
    if motif == "autre" and not (commentaire or "").strip():
        raise ValueError("Un commentaire est obligatoire pour le motif « Autre ».")
    return preflight_repository.upsert_resolution(
        company_id=company_id,
        employee_id=employee_id,
        year=year,
        month=month,
        anomaly_type=anomaly_type,
        status="justifie",
        motif=motif,
        commentaire=commentaire,
        resolved_by=resolved_by,
    )


def remove_anomaly_justification(
    *,
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    anomaly_type: str,
) -> None:
    preflight_repository.delete_resolution(
        company_id=company_id,
        employee_id=employee_id,
        year=year,
        month=month,
        anomaly_type=anomaly_type,
    )


def acknowledge_preflight_launch(
    *,
    company_id: str,
    year: int,
    month: int,
    open_anomalies_count: int,
    anomaly_types_summary: List[str],
    commentaire: Optional[str],
    acknowledged_by: str,
) -> Dict[str, Any]:
    return preflight_repository.insert_acknowledgement(
        company_id=company_id,
        year=year,
        month=month,
        open_anomalies_count=open_anomalies_count,
        anomaly_types_summary=anomaly_types_summary,
        commentaire=commentaire,
        acknowledged_by=acknowledged_by,
    )


def _jours_du_calendrier(ligne: Optional[Dict[str, Any]]) -> tuple[list, list]:
    """(jours prévus, jours réels) d'une ligne employee_schedules."""
    ligne = ligne or {}
    prevu = ligne.get("planned_calendar") or {}
    reel = ligne.get("actual_hours") or {}
    return (
        list(prevu.get("calendrier_prevu", []) if isinstance(prevu, dict) else []),
        list(reel.get("calendrier_reel", []) if isinstance(reel, dict) else []),
    )


def _jours_de_la_fenetre(
    company_id: str,
    employee_ids: List[str],
    periodes: Dict[str, Any],
    year: int,
    month: int,
    schedule_by_emp: Dict[str, Dict[str, Any]],
) -> Dict[str, List[tuple[list, list]]]:
    """Par salarié, les (prévus, réels) de chaque mois, bornés à la fenêtre des variables."""
    from datetime import date

    fenetre = next((p.fenetre for p in periodes.values() if p is not None), None)
    if fenetre is None:
        return {}
    debut, fin = fenetre
    mois_couverts: List[tuple[int, int]] = []
    a, m = debut.year, debut.month
    while (a, m) <= (fin.year, fin.month):
        mois_couverts.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)

    lignes: Dict[tuple[int, int], Dict[str, Dict[str, Any]]] = {(year, month): schedule_by_emp}
    for cle in mois_couverts:
        if cle in lignes:
            continue
        res = (
            supabase.table("employee_schedules")
            .select("employee_id, planned_calendar, actual_hours")
            .eq("company_id", company_id)
            .eq("year", cle[0])
            .eq("month", cle[1])
            .in_("employee_id", employee_ids)
            .execute()
        )
        lignes[cle] = {str(r["employee_id"]): r for r in (res.data or [])}

    def dans_la_fenetre(cle: tuple[int, int], jour: Dict[str, Any]) -> bool:
        try:
            return debut <= date(cle[0], cle[1], int(jour.get("jour") or 0)) <= fin
        except (TypeError, ValueError):
            return False

    resultat: Dict[str, List[tuple[list, list]]] = {}
    for eid in employee_ids:
        par_mois = []
        for cle in mois_couverts:
            prevus, reels = _jours_du_calendrier(lignes.get(cle, {}).get(eid))
            par_mois.append(
                (
                    [j for j in prevus if dans_la_fenetre(cle, j)],
                    [j for j in reels if dans_la_fenetre(cle, j)],
                )
            )
        resultat[eid] = par_mois
    return resultat
