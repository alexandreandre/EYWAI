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
    brut_break = row.get("break_deduct_minutes")
    break_m = 45 if brut_break is None else int(brut_break)  # 0 est légal
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
        theoretical_gross_minutes=(
            465
            if row.get("theoretical_gross_minutes") is None
            else int(row.get("theoretical_gross_minutes"))
        ),
        break_deduct_minutes=break_m,
        paid_break_minutes=paid_break,
        paid_lunch_break=paid_lunch,
        sort_order=int(row.get("sort_order") or 0),
    )


def resolve_break_minutes(
    slot: PunchShiftSlot | None,
    settings: PunchAccountingSettings,
    planned: PlannedShiftBreak | None,
    *,
    measured_break_minutes: int | None = None,
) -> int:
    """Minutes à déduire du brut pointé (pauses non payées uniquement).

    Priorité : pause MESURÉE (badgée) > pause planifiée > créneau > forfait
    société. Réintégrer une pause badgée puis déduire un forfait fabriquait
    des HS fantômes (2 h de pause réelle ≈ 2 h de fausses HS).
    """
    if measured_break_minutes is not None and measured_break_minutes > 0:
        # La part PAYÉE de la pause (MBC : 2×10 min comprises dans les
        # 7 h 30) reste acquise : on ne déduit que l'excédent badgé. Elle
        # vit dans le planning du jour OU, à défaut, sur le créneau.
        part_payee = int(planned.paid_break_minutes) if planned else 0
        if part_payee <= 0 and slot is not None:
            part_payee = int(slot.paid_break_minutes or 0)
        return max(0, int(measured_break_minutes) - max(0, part_payee))
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


def _distance_au_creneau(
    slot: PunchShiftSlot, entry_minutes: int, exit_minutes: int | None
) -> int:
    """Écart entre la journée pointée et le créneau, entrée ET sortie.

    L'entrée seule trompe : un salarié de journée qui badge à 5 h 29 est plus
    près de l'équipe de 4 h que de la journée de 8 h, et sa sortie à 16 h 30
    devenait 4 h 30 « en plus ». Les postes qui passent minuit sont comptés
    sur 24 h + la sortie.
    """
    ecart = abs(slot.entry_minutes - entry_minutes)
    if exit_minutes is None:
        return ecart
    sortie_creneau = slot.exit_minutes
    if sortie_creneau <= slot.entry_minutes:
        sortie_creneau += 24 * 60
    sortie = exit_minutes
    if sortie <= entry_minutes:
        sortie += 24 * 60
    return ecart + abs(sortie_creneau - sortie)


def _pick_slot(
    *,
    entry_minutes: int,
    shift_code: str | None,
    slots: Sequence[PunchShiftSlot],
    detection: str,
    planned: PlannedShiftBreak | None = None,
    exit_minutes: int | None = None,
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

    if detection == "nearest_entry":
        # « Horaire le plus proche » : entrée et sortie ensemble.
        return min(
            ordered,
            key=lambda s: _distance_au_creneau(s, entry_minutes, exit_minutes),
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
    a_une_entree = entry is not None and entry > 0
    a_une_sortie = exit_m is not None and exit_m > 0

    if not a_une_entree and not a_une_sortie:
        return PunchDayResult(is_absent=True, accounted_hours=0.0)

    if not a_une_entree or not a_une_sortie or entry == exit_m:
        # Un seul badge (ou entrée = sortie) : ni travaillée ni absente.
        # Compter 24 h − pause, ou une absence à 0 h, serait un état faux.
        if not a_une_sortie:
            detail = f"entrée {minutes_to_time_string(entry)} sans sortie"
        elif not a_une_entree:
            detail = f"sortie {minutes_to_time_string(exit_m)} sans entrée"
        else:
            detail = f"un seul badge à {minutes_to_time_string(entry)}"
        return PunchDayResult(
            is_incomplete=True,
            accounted_hours=0.0,
            alerts=(f"Pointage incomplet : {detail}. Journée à compléter.",),
        )

    slot = _pick_slot(
        entry_minutes=entry,
        shift_code=day_input.shift_code,
        slots=slots,
        detection=settings.slot_detection,
        planned=day_input.planned_shift,
        exit_minutes=exit_m,
    )
    # Deux pauses distinctes : celle du PLANNING pour le théorique (le
    # contrat de la journée), celle CONSTATÉE (badgée si mesurée, sinon la
    # même estimation) pour le pointé. Mélanger les deux faisait fuir la
    # pause badgée dans le théorique.
    schedule_break = resolve_break_minutes(slot, settings, day_input.planned_shift)
    schedule_break = apply_break_threshold(schedule_break, entry, exit_m, settings)
    mesure = day_input.measured_break_minutes
    # La pause CONSTATÉE passe par resolve_break_minutes : c'est là que la
    # part payée est soustraite — la recalculer à la main ici court-circuitait
    # le contrat (faux vert n°5 : le fix C5 n'était jamais appelé en prod).
    actual_break = (
        resolve_break_minutes(
            slot,
            settings,
            day_input.planned_shift,
            measured_break_minutes=mesure,
        )
        if mesure is not None and mesure > 0
        else schedule_break
    )
    pointed = _pointed_net_hours(entry, exit_m, actual_break)
    theoretical = _theoretical_net_hours(slot, schedule_break) if slot else pointed

    tolerance_hours = settings.tolerance_minutes / 60.0

    pause_pointee = day_input.punched_break_minutes
    if (mesure is None or mesure <= 0) and pause_pointee is not None:
        # Pause vue entre les paires de badges, hors part payée du créneau
        # (déjeuner payé des équipes). Elle remplace la pause du créneau
        # quand elle est plus longue (temps non travaillé : pas d'heures en
        # plus fictives), ou sur une journée courte (demi-journée sans
        # déjeuner : on ne déduit pas une pause non prise). Une journée
        # complète où la pause du matin n'est pas badgée garde la règle.
        part_payee = int(slot.paid_break_minutes or 0) if slot else 0
        pause_non_payee = max(0, int(pause_pointee) - part_payee)
        if pause_non_payee > actual_break or pointed < theoretical - tolerance_hours:
            pointed = _pointed_net_hours(entry, exit_m, pause_non_payee)
    alerts: list[str] = []
    overtime = 0.0
    reason: OvertimeReason | None = None

    # Une pause badgée rompt l'hypothèse de présence continue : l'avance
    # d'entrée ou le retard de sortie ne mesurent plus du travail — seul
    # l'excédent journalier (travaillé − théorique) fait foi.
    pause_mesuree = mesure is not None and mesure > 0
    if slot and not pause_mesuree:
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

    if overtime > 0:
        # Jamais plus d'heures en plus que le temps réellement fait au-delà du
        # théorique : un retard le matin compense une sortie tardive. Sous la
        # tolérance une fois compensé, ce n'est plus qu'un arrondi.
        fait_en_plus = round(max(0.0, pointed - theoretical), 2)
        if fait_en_plus < overtime:
            overtime = fait_en_plus
            if overtime <= tolerance_hours:
                overtime = 0.0
                reason = None
                alerts = []

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
    elif overtime > 0:
        # HS en attente de validation : NON payées (théorique retenu).
        # L'ancienne branche retenait le pointé complet — exiger la
        # validation payait PLUS que ne pas l'exiger, et l'approbation
        # n'avait aucun effet. L'approbation écrit désormais les heures
        # dans le calendrier réel (punch_accounting_commands).
        # En attente de validation : le théorique est retenu, mais JAMAIS
        # plus que le pointé — un badge de 15 min avec revue early_entry ne
        # crédite pas la journée théorique complète.
        accounted = (
            min(theoretical, pointed)
            if needs_review
            else round(theoretical + overtime, 2)
        )
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
    punched_break_minutes: int | None = None,
) -> PunchDayResult:
    return compute_punch_day(
        PunchDayInput(
            entry_minutes=parse_hhmm_value(entry_raw),
            exit_minutes=parse_hhmm_value(exit_raw),
            shift_code=shift_code,
            planned_shift=planned_shift,
            punched_break_minutes=punched_break_minutes,
        ),
        settings,
        list(slots),
    )
