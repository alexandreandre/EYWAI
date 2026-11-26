"""Activité partielle posée en masse : aperçu (rien n'est écrit) et enregistrement.

Besoin du 26/11 (LEWIS) : tous les vendredis, tout le monde est en activité
partielle. La gestionnaire choisit des dates et des salariés ; le serveur juge
chaque jour (`domain.activite_partielle_en_masse`) et l'enregistre par LE MÊME
chemin que le calendrier d'un salarié : `calendar_edit.save_calendar`
(réservation du mois sur sa révision, prévu, réel, calcul des événements de
paie). Un salarié en heures et un forfait jours y sont traités pareil.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Iterable, Sequence

from app.core.logging import get_logger
from app.modules.schedules.application import calendar_edit
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.domain.activite_partielle_en_masse import (
    LIBELLES_RAISONS,
    RAISON_ECHEC,
    ContexteSalarie,
    decompte,
    juger_le_mois,
)
from app.modules.schedules.domain.ecart_rules import parse_iso_date
from app.modules.schedules.infrastructure import activite_partielle_en_masse_queries as lectures
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
from app.modules.schedules.infrastructure.repository import schedule_repository
from app.modules.schedules.schemas.requests import (
    ActualHoursEntry,
    CalendarSaveRequest,
    PlannedCalendarEntry,
)
from app.shared.domain.employment_rules import is_forfait_jour
from app.shared.public_holidays import observed_holiday_dates_for_month

logger = get_logger(__name__)

#: Enregistrements menés en même temps (un par salarié et par mois).
_FILS = 4


def _mois_des_dates(dates: Iterable[date]) -> list[tuple[int, int]]:
    return sorted({(d.year, d.month) for d in dates})


def _nom(e: dict[str, Any]) -> str:
    nom = (e.get("nom_usage") or e.get("last_name") or "").strip()
    return f"{nom} {(e.get('first_name') or '').strip()}".strip() or "Salarié"


def _sortie(e: dict[str, Any]) -> date | None:
    """La sortie comme le bulletin la lit (dossier de sortie, sinon fin de contrat)."""
    from app.modules.payroll.documents.payslip_generator import resolve_date_sortie

    return parse_iso_date(resolve_date_sortie(e))


def _jours_d_arret(arrets: Iterable[dict[str, Any]]) -> frozenset[date]:
    jours: set[date] = set()
    for arret in arrets or []:
        for brut in arret.get("selected_days") or []:
            quand = parse_iso_date(brut)
            if quand:
                jours.add(quand)
    return frozenset(jours)


def salaries_de_la_societe(company_id: str, employee_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Garde société : tous les salariés demandés sont de la société active,
    sinon rien n'est lu ni écrit (404, sans dire lesquels existent ailleurs)."""
    if not employee_ids:
        raise ScheduleAppError("validation", "Choisissez au moins un salarié.", 400)
    salaries = lectures.salaries_de_la_societe(company_id, employee_ids)
    if any(str(eid) not in salaries for eid in employee_ids):
        raise ScheduleAppError("not_found", "Salarié introuvable dans cette société.", 404)
    return salaries


def _contextes(
    company_id: str, salaries: dict[str, dict[str, Any]], dates: Sequence[date]
) -> dict[str, ContexteSalarie]:
    mois = _mois_des_dates(dates)
    ids = list(salaries)
    figes = lectures.mois_figes(ids, mois)
    arrets = arrets_valides_reader.par_salarie(ids, min(dates), max(dates))
    feries: set[date] = set()
    for annee, m in mois:
        feries |= observed_holiday_dates_for_month(annee, m, company_id)
    return {
        eid: ContexteSalarie(
            forfait_jours=is_forfait_jour(e.get("statut"), e.get("is_forfait_jour")),
            entree=parse_iso_date(e.get("hire_date")),
            sortie=_sortie(e),
            mois_figes=frozenset(figes.get(eid, set())),
            jours_d_arret=_jours_d_arret(arrets.get(eid, [])),
            feries=frozenset(feries),
        )
        for eid, e in salaries.items()
    }


def _calendriers(ligne: dict[str, Any] | None) -> tuple[list, list]:
    ligne = ligne or {}
    prevu = (ligne.get("planned_calendar") or {}).get("calendrier_prevu") or []
    reel = (ligne.get("actual_hours") or {}).get("calendrier_reel") or []
    return list(prevu), list(reel)


def _resume(
    dates: Sequence[date],
    salaries: dict[str, dict[str, Any]],
    contextes: dict[str, ContexteSalarie],
    passes: dict[str, list[date]],
    laisses: dict[str, list[tuple[date, str]]],
    erreurs: dict[str, list[str]],
    *,
    enregistre: bool,
    avertissement: str | None = None,
) -> dict[str, Any]:
    tous_laisses = [l for liste in laisses.values() for l in liste]
    lignes = []
    for eid in sorted(salaries, key=lambda i: _nom(salaries[i]).lower()):
        lignes.append({
            "employee_id": eid,
            "nom": _nom(salaries[eid]),
            "forfait_jours": contextes[eid].forfait_jours,
            "passes": [d.isoformat() for d in sorted(passes.get(eid, []))],
            "laisses": [
                {"date": d.isoformat(), "raison": r}
                for d, r in sorted(laisses.get(eid, []))
            ],
            "erreurs": erreurs.get(eid, []),
        })
    return {
        "enregistre": enregistre,
        "dates": [d.isoformat() for d in sorted(dates)],
        "total_passes": sum(len(v) for v in passes.values()),
        "total_laisses": len(tous_laisses),
        "laisses_par_raison": decompte(tous_laisses),
        "libelles_raisons": dict(LIBELLES_RAISONS),
        "salaries": lignes,
        "avertissement": avertissement,
    }


def _dates_propres(dates: Sequence[date]) -> list[date]:
    propres = sorted(set(dates))
    if not propres:
        raise ScheduleAppError("validation", "Choisissez au moins un jour.", 400)
    return propres


def _reglage_actif(company_id: str) -> dict[str, Any]:
    """Comme au calendrier : le type n'existe que si la société l'a activé."""
    from app.modules.activite_partielle.application.service import lire_reglage

    reglage = lire_reglage(company_id)
    if not reglage.get("active"):
        raise ScheduleAppError(
            "validation",
            "L'activité partielle n'est pas activée pour cette société (Paramètres, Paie).",
            400,
        )
    return reglage


def avertissement_periode(reglage: dict[str, Any], dates: Sequence[date]) -> str | None:
    """Des dates hors de la période déclarée : posées quand même, comme au
    calendrier d'un salarié, mais dites avant d'enregistrer."""
    debut = parse_iso_date(reglage.get("date_debut"))
    fin = parse_iso_date(reglage.get("date_fin"))
    hors = [d for d in dates if (debut and d < debut) or (fin and d > fin)]
    if not hors:
        return None
    if debut and fin:
        periode = f"du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}"
    elif debut:
        periode = f"à partir du {debut:%d/%m/%Y}"
    else:
        periode = f"jusqu'au {fin:%d/%m/%Y}"
    n = len(hors)
    return (
        f"{n} {'dates sont' if n > 1 else 'date est'} hors de la période d'activité "
        f"partielle de la société ({periode}). Elles seront posées quand même : "
        "vérifiez la période dans Paramètres, Paie."
    )


def apercu(company_id: str, employee_ids: Sequence[str], dates: Sequence[date]) -> dict[str, Any]:
    """Ce que l'enregistrement ferait, jour par jour. Rien n'est écrit."""
    dates = _dates_propres(dates)
    reglage = _reglage_actif(company_id)
    salaries = salaries_de_la_societe(company_id, employee_ids)
    contextes = _contextes(company_id, salaries, dates)
    ids = list(salaries)
    passes: dict[str, list[date]] = {}
    laisses: dict[str, list[tuple[date, str]]] = {}
    for annee, mois in _mois_des_dates(dates):
        lignes = schedule_repository.list_schedules_for_employees(ids, annee, mois)
        for eid in ids:
            prevu, reel = _calendriers(lignes.get(eid))
            res = juger_le_mois(annee, mois, dates, prevu, reel, contextes[eid])
            passes.setdefault(eid, []).extend(res.passes)
            laisses.setdefault(eid, []).extend(res.laisses)
    return _resume(
        dates, salaries, contextes, passes, laisses, {},
        enregistre=False, avertissement=avertissement_periode(reglage, dates),
    )


def _enregistrer_un_mois(
    company_id: str, eid: str, annee: int, mois: int, dates: Sequence[date], ctx: ContexteSalarie
) -> tuple[list[date], list[tuple[date, str]], str | None]:
    """Relit le mois sur sa révision, le rejuge, puis l'enregistre par le
    chemin du calendrier unitaire. Un échec laisse les jours qui devaient
    passer (raison « echec ») ; les autres gardent leur raison."""
    du_mois = [d for d in dates if d.year == annee and d.month == mois]
    res = None
    try:
        snap = calendar_edit.get_snapshot(eid, company_id, annee, mois)
        res = juger_le_mois(
            annee, mois, du_mois, snap["calendrier_prevu"], snap["calendrier_reel"], ctx
        )
        if not res.passes:
            return [], res.laisses, None
        calendar_edit.save_calendar(eid, company_id, CalendarSaveRequest(
            year=annee,
            month=mois,
            expected_revision=snap["revision"],
            calendrier_prevu=[PlannedCalendarEntry(**e) for e in res.prevu_a_ecrire],
            calendrier_reel=[ActualHoursEntry(**e) for e in res.reel_a_ecrire],
            recalculate_payroll=True,
        ))
        return res.passes, res.laisses, None
    except ScheduleAppError as exc:
        message = exc.message
    except Exception:  # noqa: BLE001 — un mois en échec n'arrête pas les autres
        logger.exception("Activité partielle en masse : %s %02d/%d non enregistré", eid, mois, annee)
        message = "Le calendrier n'a pas pu être enregistré."
    if res is None:
        laisses = [(d, RAISON_ECHEC) for d in du_mois]
    else:
        laisses = res.laisses + [(d, RAISON_ECHEC) for d in res.passes]
    return [], laisses, f"{mois:02d}/{annee} : {message}"


def appliquer(company_id: str, employee_ids: Sequence[str], dates: Sequence[date]) -> dict[str, Any]:
    """Enregistre l'activité partielle des jours qui passent et rend le même
    décompte que l'aperçu, jugé à nouveau sur le calendrier relu."""
    dates = _dates_propres(dates)
    reglage = _reglage_actif(company_id)
    salaries = salaries_de_la_societe(company_id, employee_ids)
    contextes = _contextes(company_id, salaries, dates)
    taches = [
        (eid, annee, mois)
        for eid in salaries
        for annee, mois in _mois_des_dates(dates)
    ]
    with ThreadPoolExecutor(max_workers=_FILS) as pool:
        resultats = list(pool.map(
            lambda t: _enregistrer_un_mois(company_id, t[0], t[1], t[2], dates, contextes[t[0]]),
            taches,
        ))
    passes: dict[str, list[date]] = {}
    laisses: dict[str, list[tuple[date, str]]] = {}
    erreurs: dict[str, list[str]] = {}
    for (eid, _, _), (p, l, err) in zip(taches, resultats):
        passes.setdefault(eid, []).extend(p)
        laisses.setdefault(eid, []).extend(l)
        if err:
            erreurs.setdefault(eid, []).append(err)
    return _resume(
        dates, salaries, contextes, passes, laisses, erreurs,
        enregistre=True, avertissement=avertissement_periode(reglage, dates),
    )
