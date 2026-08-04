"""Règles pures de comptabilisation des pointages."""

from __future__ import annotations

from typing import Iterable, Sequence

from app.modules.schedules.domain.punch_accounting_entities import (
    OvertimeReason,
    PlannedShiftBreak,
    PunchAccountingSettings,
    PunchDayInput,
    PunchDayResult,
    PunchShiftSlot,
)


def time_string_to_minutes(value: str) -> int:
    parts = str(value or "00:00")[:8].split(":")
    h = int(parts[0]) if parts else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    return h * 60 + m


def minutes_to_time_string(minutes: int) -> str:
    minutes = max(0, minutes) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_hhmm_value(raw: object) -> int | None:
    """Parse 800, 1548, '8:00', '15:48' → minutes depuis minuit."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        n = int(raw)
        if n <= 0:
            return None
        if n < 2400:
            h, m = divmod(n, 100)
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h * 60 + m
        return None
    s = str(raw).strip().replace(" ", "")
    if not s or s in ("0", "00", "0000"):
        return None
    if ":" in s or "h" in s.lower():
        s = s.lower().replace("h", ":")
        parts = s.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h * 60 + m
        except ValueError:
            return None
    if s.isdigit() and len(s) <= 4:
        return parse_hhmm_value(int(s))
    return None


def slot_from_row(row: dict) -> PunchShiftSlot:
    entry = row.get("entry_time") or "08:00"
    exit_t = row.get("exit_time") or "17:00"
    if hasattr(entry, "hour"):
        entry_min = entry.hour * 60 + entry.minute
    else:
        entry_min = time_string_to_minutes(str(entry))
    if hasattr(exit_t, "hour"):
        exit_min = exit_t.hour * 60 + exit_t.minute
    else:
        exit_min = time_string_to_minutes(str(exit_t))
    break_m = int(row.get("break_deduct_minutes") or 45)
    paid_lunch = bool(row.get("paid_lunch_break"))
    paid_break = int(row.get("paid_break_minutes") or 0)
    if paid_lunch and break_m > 15:
        break_m = 15
    return PunchShiftSlot(
        id=str(row["id"]) if row.get("id") else None,
        code=(str(row["code"]).strip().upper() if row.get("code") else None),
        label=str(row.get("label") or ""),
        entry_minutes=entry_min,
        exit_minutes=exit_min,
        theoretical_gross_minutes=int(row.get("theoretical_gross_minutes") or 465),
        break_deduct_minutes=break_m,
        paid_break_minutes=paid_break,
        paid_lunch_break=paid_lunch,
        sort_order=int(row.get("sort_order") or 0),
    )


def resolve_break_minutes(
    slot: PunchShiftSlot | None,
    settings: PunchAccountingSettings,
    planned: PlannedShiftBreak | None,
) -> int:
    """Minutes à déduire du brut pointé (pauses non payées uniquement)."""
    if planned and planned.unpaid_break_minutes is not None:
        return max(0, int(planned.unpaid_break_minutes))

    base = settings.default_break_deduct_minutes
    if slot:
        if slot.paid_lunch_break:
            # Legacy équipes : déduction nette après portion payée planifiée.
            base = 15 if slot.break_deduct_minutes > 15 else slot.break_deduct_minutes
            if planned and planned.paid_break_minutes > 0:
                return max(0, base - planned.paid_break_minutes)
            return base
        base = slot.break_deduct_minutes
    if (
        planned
        and planned.paid_break_minutes > 0
        and planned.unpaid_break_minutes is None
        and not (slot and slot.paid_lunch_break)
    ):
        # Legacy calendrier / proposition IA : réduit la déduction globale.
        return max(0, base - planned.paid_break_minutes)
    return base


def apply_break_threshold(
    break_minutes: int,
    entry_minutes: int,
    exit_minutes: int,
    settings: PunchAccountingSettings,
) -> int:
    """Annule la pause sur les journées trop courtes pour la justifier.

    Certaines organisations ne décomptent la pause déjeuner qu'au-delà d'une
    durée de présence : une demi-journée n'en subit aucune. Le seuil est
    comparé au brut pointé, pauses comprises.

    Seuil à 0 : aucune journée n'est exemptée.
    """
    threshold = settings.break_threshold_minutes
    if threshold <= 0 or break_minutes <= 0:
        return break_minutes
    if exit_minutes <= entry_minutes:
        exit_minutes += 24 * 60
    gross = exit_minutes - entry_minutes
    return 0 if gross <= threshold else break_minutes


def _gross_minutes_from_slot(slot: PunchShiftSlot) -> int:
    if slot.theoretical_gross_minutes > 0:
        return slot.theoretical_gross_minutes
    span = slot.exit_minutes - slot.entry_minutes
    return span if span > 0 else 0


def _theoretical_net_hours(slot: PunchShiftSlot, break_minutes: int) -> float:
    gross = _gross_minutes_from_slot(slot)
    return round(max(0, gross - break_minutes) / 60.0, 2)


def _pick_slot(
    *,
    entry_minutes: int,
    shift_code: str | None,
    slots: Sequence[PunchShiftSlot],
    detection: str,
    planned: PlannedShiftBreak | None = None,
) -> PunchShiftSlot | None:
    if not slots:
        return None
    ordered = sorted(slots, key=lambda s: s.sort_order)
    code = (shift_code or "").strip().upper()
    if detection == "planning_first" and not code and planned and planned.slot_code:
        code = planned.slot_code.strip().upper()

    def _match_by_code() -> PunchShiftSlot | None:
        if not code:
            return None
        matches = [s for s in ordered if (s.code or "").upper() == code]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return min(
                matches,
                key=lambda s: abs(s.entry_minutes - entry_minutes),
            )
        return None

    if detection in ("shift_code", "planning_first"):
        by_code = _match_by_code()
        if by_code is not None:
            return by_code

    if detection == "planning_first" and planned and planned.planned_entry_minutes is not None:
        return min(
            ordered,
            key=lambda s: abs(s.entry_minutes - planned.planned_entry_minutes),
        )

    return min(ordered, key=lambda s: abs(s.entry_minutes - entry_minutes))


def _pointed_net_hours(
    entry_minutes: int,
    exit_minutes: int,
    break_minutes: int,
) -> float:
    if exit_minutes <= entry_minutes:
        exit_minutes += 24 * 60
    gross = exit_minutes - entry_minutes
    return round(max(0, gross - break_minutes) / 60.0, 2)


def compute_punch_day(
    day_input: PunchDayInput,
    settings: PunchAccountingSettings,
    slots: Sequence[PunchShiftSlot],
) -> PunchDayResult:
    """Calcule les heures comptabilisées pour une journée."""
    entry = day_input.entry_minutes
    exit_m = day_input.exit_minutes

    if entry is None or exit_m is None or entry <= 0 and exit_m <= 0:
        return PunchDayResult(is_absent=True, accounted_hours=0.0)

    if entry is None or entry <= 0:
        return PunchDayResult(is_absent=True, accounted_hours=0.0)
    if exit_m is None or exit_m <= 0:
        return PunchDayResult(is_absent=True, accounted_hours=0.0)

    slot = _pick_slot(
        entry_minutes=entry,
        shift_code=day_input.shift_code,
        slots=slots,
        detection=settings.slot_detection,
        planned=day_input.planned_shift,
    )
    break_min = resolve_break_minutes(slot, settings, day_input.planned_shift)
    break_min = apply_break_threshold(break_min, entry, exit_m, settings)
    pointed = _pointed_net_hours(entry, exit_m, break_min)
    theoretical = _theoretical_net_hours(slot, break_min) if slot else pointed

    tolerance_hours = settings.tolerance_minutes / 60.0
    alerts: list[str] = []
    overtime = 0.0
    reason: OvertimeReason | None = None

    if slot:
        early_min = slot.entry_minutes - entry
        if early_min > settings.tolerance_minutes:
            ot = round(early_min / 60.0, 2)
            overtime = max(overtime, ot)
            reason = "early_entry"
            alerts.append(
                f"Entrée {minutes_to_time_string(entry)} : "
                f"{early_min} min d'avance (> {settings.tolerance_minutes} min) — HS à valider."
            )

        late_min = exit_m - slot.exit_minutes
        if late_min > settings.tolerance_minutes:
            ot = round(late_min / 60.0, 2)
            if ot >= overtime:
                overtime = ot
                reason = "late_exit"
            alerts.append(
                f"Sortie {minutes_to_time_string(exit_m)} : "
                f"{late_min} min de dépassement (> {settings.tolerance_minutes} min) — HS à valider."
            )

    daily_excess = round(max(0.0, pointed - theoretical - tolerance_hours), 2)
    if daily_excess > overtime:
        overtime = daily_excess
        reason = "daily_excess"
        if daily_excess > 0:
            alerts.append(
                f"Écart journalier {daily_excess:.2f} h au-delà du seuil "
                f"(pointé {pointed:.2f} h vs théorique {theoretical:.2f} h)."
            )

    needs_review = overtime > 0 and settings.require_manager_validation_for_overtime

    if (
        settings.within_tolerance_pay_theoretical
        and abs(pointed - theoretical) <= tolerance_hours
        and overtime <= 0
    ):
        accounted = theoretical
    elif overtime > 0 and not needs_review:
        accounted = round(theoretical + overtime, 2)
    else:
        accounted = pointed

    return PunchDayResult(
        accounted_hours=accounted,
        theoretical_net_hours=theoretical,
        pointed_net_hours=pointed,
        overtime_hours=overtime,
        overtime_reason=reason,
        needs_review=needs_review,
        alerts=tuple(alerts),
        applied_slot_id=slot.id if slot else None,
        is_absent=False,
    )


def compute_from_raw_times(
    *,
    entry_raw: object,
    exit_raw: object,
    shift_code: str | None,
    settings: PunchAccountingSettings,
    slots: Iterable[PunchShiftSlot],
    planned_shift: PlannedShiftBreak | None = None,
) -> PunchDayResult:
    return compute_punch_day(
        PunchDayInput(
            entry_minutes=parse_hhmm_value(entry_raw),
            exit_minutes=parse_hhmm_value(exit_raw),
            shift_code=shift_code,
            planned_shift=planned_shift,
        ),
        settings,
        list(slots),
    )
