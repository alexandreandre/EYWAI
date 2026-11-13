"""Réservation en base d'une saisie RH ; aucun repli sur une écriture aveugle."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Event, Thread
from time import monotonic
from typing import Any
from uuid import uuid4

from app.core.calendar_write_context import calendar_write_token
from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.schedules.application.exceptions import ScheduleAppError

logger = get_logger(__name__)
LEASE_SECONDS = 60
RENEW_INTERVAL = 20.0
MAX_SECONDS = 300


def _rpc(name: str, params: dict[str, Any]) -> Any:
    return get_supabase_admin_client().rpc(name, params).execute().data


def _unavailable() -> ScheduleAppError:
    message = "La protection de l’enregistrement est indisponible. Rien ne peut être confirmé ; réessayez après rechargement du calendrier."
    return ScheduleAppError("calendar_unavailable", message, 503, {"code": "calendar_unavailable", "message": message})


def read_snapshot(employee_id: str, company_id: str, year: int, month: int) -> dict[str, Any]:
    try:
        result = _rpc("read_calendar_snapshot", {
            "p_employee_id": employee_id, "p_company_id": company_id,
            "p_year": year, "p_month": month,
        })
    except Exception as exc:
        logger.exception("Lecture de la révision du calendrier impossible")
        raise _unavailable() from exc
    if result is None:
        raise ScheduleAppError("not_found", "Calendrier introuvable dans cette société.", 404)
    if not isinstance(result, dict) or not {"revision", "busy", "planned_calendar", "actual_hours"} <= result.keys():
        raise _unavailable()
    return result


@dataclass
class CalendarLease:
    params: dict[str, Any]
    started: float = field(default_factory=monotonic)

    def ensure_alive(self) -> None:
        if monotonic() - self.started >= MAX_SECONDS:
            raise _unavailable()
        try:
            alive = _rpc("renew_calendar_edit", {**self.params, "p_seconds": LEASE_SECONDS})
        except Exception as exc:
            raise _unavailable() from exc
        if alive is not True:
            raise _unavailable()


def _renew_while_alive(lease: CalendarLease, done: Event) -> None:
    started = monotonic()
    while not done.wait(RENEW_INTERVAL):
        if monotonic() - started >= MAX_SECONDS:
            return
        try:
            lease.ensure_alive()
        except ScheduleAppError:
            # Les contrôles synchrones et le trigger refusent ensuite toute
            # écriture dont le jeton a expiré, même si cette requête vit encore.
            logger.warning("Réservation du calendrier non prolongée")
            return


@contextmanager
def calendar_edit(employee_id: str, company_id: str, year: int, month: int, expected_revision: str | None) -> Iterator[CalendarLease]:
    params = {"p_employee_id": employee_id, "p_year": year, "p_month": month, "p_token": str(uuid4())}
    acquired = False
    uncertain = False
    done = Event()
    thread: Thread | None = None
    try:
        try:
            uncertain = True
            result = _rpc("begin_calendar_edit", {
                **params, "p_company_id": company_id,
                "p_expected_revision": expected_revision, "p_seconds": LEASE_SECONDS,
            })
            uncertain = False
        except Exception as exc:
            logger.exception("Réservation du calendrier impossible")
            raise _unavailable() from exc
        if result == "busy" or result == "conflict":
            code = "calendar_busy" if result == "busy" else "calendar_conflict"
            message = (
                "Un enregistrement de ce calendrier est en cours. Vos saisies restent affichées ; réessayez après son achèvement."
                if result == "busy" else
                "Ce calendrier a changé depuis son chargement. Vos saisies restent affichées : conservez-les avant de recharger le calendrier."
            )
            raise ScheduleAppError(code, message, 409, {"code": code, "message": message})
        if result == "not_found":
            raise ScheduleAppError("not_found", "Salarié introuvable dans cette société.", 404)
        if result != "acquired":
            raise _unavailable()
        acquired = True
        lease = CalendarLease(params)
        thread = Thread(target=_renew_while_alive, args=(lease, done), daemon=True)
        thread.start()
        with calendar_write_token(params["p_token"]):
            yield lease
    finally:
        done.set()
        if thread is not None:
            thread.join(timeout=2)
        # Une prise sans réponse peut avoir été enregistrée. Seul ce jeton est
        # rendu : une réservation reprise par une autre requête reste intacte.
        if acquired or uncertain:
            try:
                _rpc("end_calendar_edit", params)
            except Exception:
                logger.warning("Réservation du calendrier non libérée ; expiration automatique", exc_info=True)


def attendre_calendriers_libres(
    employee_id: str,
    mois: set[tuple[int, int]],
    *,
    delai_max: float = 20.0,
    dormir=None,
    maintenant=None,
) -> None:
    """Attend qu'aucun des mois ne soit réservé par un enregistrement en cours.

    Appelé AVANT qu'un auteur extérieur (validation d'absence) écrive son
    statut : sinon la projection pourrait être refusée après coup et laisser
    une absence validée hors du planning. Au-delà du délai : `CalendrierReserve`,
    rien n'est écrit. Si la table de réservation est illisible, on n'attend pas :
    la relance de la projection reste le filet.
    """
    import time
    from datetime import UTC, datetime

    from app.core.calendar_write_context import MESSAGE_CALENDRIER_RESERVE, CalendrierReserve

    if not mois:
        return
    dormir = dormir or time.sleep
    maintenant = maintenant or time.monotonic
    debut = maintenant()
    while True:
        try:
            rows = (
                get_supabase_admin_client().table("calendar_edit_locks")
                .select("year, month")
                .eq("employee_id", str(employee_id))
                .gt("locked_until", datetime.now(UTC).isoformat())
                .execute().data or []
            )
        except Exception:
            logger.warning("Réservations du calendrier illisibles : validation sans attente")
            return
        if not any((int(r["year"]), int(r["month"])) in mois for r in rows):
            return
        if maintenant() - debut >= delai_max:
            raise CalendrierReserve(MESSAGE_CALENDRIER_RESERVE)
        dormir(0.5)
