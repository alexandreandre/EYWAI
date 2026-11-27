"""Vider le calendrier d'un mois pour un salarié (retour d'Elsa, 27/11).

Aperçu d'abord (rien n'est écrit : l'écran dit combien de jours seront vidés
et combien restent), puis exécution sur la révision lue, par le même chemin
qu'un enregistrement de l'écran (`calendar_edit.save_calendar` : verrous des
bulletins, révision, synchronisation des absences). Les règles sont dans
`domain.vider_mois`.
"""

from __future__ import annotations

import calendar
from datetime import date
import logging
from typing import Any
from uuid import UUID

from app.modules.payroll.application.periode_variables_service import (
    resoudre_fenetre_variables,
)
from app.modules.schedules.application import calendar_edit
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.domain.vider_mois import jours_lus_par_les_bulletins, plan_de_vidage
from app.modules.schedules.infrastructure.vider_mois_queries import (
    absences_validees_du_salarie,
    bulletins_du_salarie,
    jours_dans_le_mois,
)
from app.modules.schedules.schemas.requests import (
    ActualHoursEntry,
    CalendarSaveRequest,
    PlannedCalendarEntry,
)
from app.shared.domain.pluriel import pluriel


logger = logging.getLogger(__name__)

MESSAGE_LECTURE = (
    "Le calendrier, les absences ou les bulletins de ce mois n'ont pas pu être lus : "
    "rien n'a été vidé. Réessayez dans un instant."
)
MESSAGE_ECRITURE = (
    "Le vidage n'a pas pu être enregistré : rien n'a été vidé, ou seulement en partie. "
    "Rechargez le calendrier pour voir son état, puis réessayez."
)


def _refus(code: str, message: str) -> ScheduleAppError:
    return ScheduleAppError(code, message, 503, {"code": code, "message": message})


def _voisins(annee: int, mois: int) -> list[tuple[int, int]]:
    avant = (annee, mois - 1) if mois > 1 else (annee - 1, 12)
    apres = (annee, mois + 1) if mois < 12 else (annee + 1, 1)
    return [avant, (annee, mois), apres]


def jours_d_absence_validee(employee_id: str, annee: int, mois: int) -> set[int]:
    debut = date(annee, mois, 1)
    fin = date(annee, mois, calendar.monthrange(annee, mois)[1])
    jours: set[int] = set()
    for demande in absences_validees_du_salarie(employee_id):
        jours |= jours_dans_le_mois(demande.get("selected_days"), debut, fin)
    return jours


def jours_des_bulletins_valides(employee_id: str, company_id: str, annee: int, mois: int) -> set[int]:
    """Jours du mois lus par un bulletin validé ou repris (mois d'avant, du mois, d'après)."""
    voisins = _voisins(annee, mois)
    figes = {
        (int(b["year"]), int(b["month"]))
        for b in bulletins_du_salarie(employee_id, [a for a, _ in voisins])
        if (int(b.get("year") or 0), int(b.get("month") or 0)) in voisins
        and (str(b.get("status") or "") == "valide" or str(b.get("origine") or "") == "importe")
    }
    fenetres = {}
    for a, m in figes:
        fenetre = resoudre_fenetre_variables(str(company_id), a, m)
        fenetres[(a, m)] = (fenetre.debut, fenetre.fin)
    return jours_lus_par_les_bulletins(annee, mois, fenetres)


def _message(apercu: bool, vides: int, absences: int, bulletins: int) -> str:
    gardes = []
    if absences:
        gardes.append(f"{pluriel(absences, 'jour')} d'arrêt, de congé ou d'absence posé{'s' if absences > 1 else ''}")
    if bulletins:
        gardes.append(f"{pluriel(bulletins, 'jour')} lu{'s' if bulletins > 1 else ''} par un bulletin validé")
    suite = f" Gardés : {' et '.join(gardes)}." if gardes else ""
    if vides == 0:
        return f"Rien à vider : aucun jour saisi en dehors des absences posées et des bulletins validés.{suite}"
    verbe = ("sera vidé" if vides == 1 else "seront vidés") if apercu else ("vidé" if vides == 1 else "vidés")
    return f"{pluriel(vides, 'jour')} {verbe} (prévu et réel).{suite}"


def vider_mois(
    employee_id: str,
    company_id: str,
    annee: int,
    mois: int,
    *,
    expected_revision: UUID | str | None,
    apercu: bool,
) -> dict[str, Any]:
    try:
        snapshot = calendar_edit.get_snapshot(employee_id, company_id, annee, mois)
        plan = plan_de_vidage(
            annee,
            mois,
            snapshot.get("calendrier_prevu") or [],
            snapshot.get("calendrier_reel") or [],
            jours_absence_validee=jours_d_absence_validee(employee_id, annee, mois),
            jours_bulletin=jours_des_bulletins_valides(employee_id, company_id, annee, mois),
        )
    except ScheduleAppError:
        raise
    except Exception as exc:  # noqa: BLE001 — dit à l'écran, jamais un 500 muet
        logger.exception("Vidage du calendrier illisible (%s, %02d/%d)", employee_id, mois, annee)
        raise _refus("vider_mois_illisible", MESSAGE_LECTURE) from exc
    resume: dict[str, Any] = {
        "year": annee,
        "month": mois,
        "apercu": apercu,
        "jours_vides": list(plan.jours_vides),
        "jours_gardes_absence": list(plan.jours_gardes_absence),
        "jours_gardes_bulletin": list(plan.jours_gardes_bulletin),
        "revision": snapshot.get("revision"),
        "message": _message(
            apercu, len(plan.jours_vides), len(plan.jours_gardes_absence), len(plan.jours_gardes_bulletin)
        ),
    }
    if apercu or not plan.jours_vides:
        return resume
    revision = expected_revision if expected_revision is not None else snapshot.get("revision")
    try:
        saved = _enregistrer(employee_id, company_id, annee, mois, revision, plan)
    except ScheduleAppError:
        raise
    except Exception as exc:  # noqa: BLE001 — dit à l'écran, jamais un 500 muet
        logger.exception("Vidage du calendrier non enregistré (%s, %02d/%d)", employee_id, mois, annee)
        raise _refus("vider_mois_non_enregistre", MESSAGE_ECRITURE) from exc
    resume["revision"] = saved.get("revision")
    return resume


def _enregistrer(employee_id, company_id, annee, mois, revision, plan) -> dict[str, Any]:
    return calendar_edit.save_calendar(
        employee_id,
        company_id,
        CalendarSaveRequest(
            year=annee,
            month=mois,
            expected_revision=revision,
            calendrier_prevu=[PlannedCalendarEntry(**e) for e in plan.calendrier_prevu],
            calendrier_reel=[_entree_reel(e) for e in plan.calendrier_reel],
        ),
    )


def _entree_reel(entree: dict[str, Any]) -> ActualHoursEntry:
    """Un jour du réel réécrit tel quel ; un horaire stocké illisible n'est pas
    renvoyé (le serveur garde alors le sien) plutôt que de bloquer le vidage."""
    from app.modules.schedules.domain.horaires_pointes import en_hhmm

    champs = {k: v for k, v in entree.items() if k in ActualHoursEntry.model_fields}
    for cle in ("debut", "fin"):
        if cle in champs and champs[cle] and en_hhmm(champs[cle]) is None:
            champs.pop(cle)
    return ActualHoursEntry(**champs)
