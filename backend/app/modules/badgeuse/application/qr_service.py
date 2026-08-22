"""QR, scan et pointage badge."""
from __future__ import annotations

from app.shared.domain.temps_local import aujourd_hui_local, maintenant_utc

from app.modules.badgeuse.application.deps import deps
from app.modules.badgeuse.application._internals import *  # noqa: F403
def get_qr_for_employee(
    *, employee_id: str, company_id: str
) -> Dict[str, Any]:
    row = deps._employee_repository.get_by_id(employee_id, company_id)
    if not row:
        raise ValueError("Employé introuvable")
    if deps._employee_is_forfait_jour(row):
        raise PermissionError("Employé au forfait jours, badgeuse non applicable")
    creds = deps.badge_credentials_repository.ensure_credentials(
        employee_id=employee_id, company_id=company_id
    )
    payload = deps.build_qr_payload(
        company_id=company_id,
        employee_id=employee_id,
        token_version=int(creds["token_version"]),
        secret_salt=str(creds["secret_salt"]),
    )
    return {
        "qr_payload": payload,
        "employee_display_name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
        "badge_username": row.get("username"),
        "token_version": int(creds["token_version"]),
    }


def regenerate_badge_for_employee(
    *, employee_id: str, company_id: str
) -> Dict[str, Any]:
    creds = deps.badge_credentials_repository.regenerate_credentials(
        employee_id=employee_id, company_id=company_id
    )
    row = deps._employee_repository.get_by_id(employee_id, company_id)
    if not row:
        raise ValueError("Employé introuvable")
    payload = deps.build_qr_payload(
        company_id=company_id,
        employee_id=employee_id,
        token_version=int(creds["token_version"]),
        secret_salt=str(creds["secret_salt"]),
    )
    return {
        "qr_payload": payload,
        "token_version": int(creds["token_version"]),
        "employee_display_name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
    }


def _normalize_search_text(value: str) -> str:
    return deps.remove_accents(value or "").lower().strip()


def punch_from_qr(
    *,
    qr_payload: Optional[str],
    employee_id: Optional[str],
    company_id: str,
    actor_user_id: str,
    source: TimeEntrySource = TimeEntrySource.QR_SCAN,
    terminal_device_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not deps.get_badgeuse_settings(company_id).get("scan_mode_enabled", True):
        raise PermissionError("Le mode scan est désactivé pour cette entreprise")

    from app.modules.badgeuse.application.badge_tokens import parse_qr_payload

    resolved_employee_id: Optional[str] = employee_id
    if qr_payload:
        parsed = parse_qr_payload(qr_payload)
        if not parsed:
            raise ValueError("QR code invalide")
        if parsed.company_id != company_id:
            raise ValueError("QR code non valide pour cette entreprise")
        creds = deps.badge_credentials_repository.get_credentials(
            employee_id=parsed.employee_id, company_id=company_id
        )
        if not creds or creds.get("revoked_at"):
            raise ValueError("Badge révoqué ou introuvable")
        verified = deps.verify_qr_payload(
            qr_payload,
            secret_salt=str(creds["secret_salt"]),
            expected_version=int(creds["token_version"]),
        )
        if not verified:
            raise ValueError("QR code invalide ou expiré")
        resolved_employee_id = parsed.employee_id

    if not resolved_employee_id:
        raise ValueError("Employé non identifié")

    row = deps._employee_repository.get_by_id(resolved_employee_id, company_id)
    if not row:
        raise ValueError("Employé introuvable")
    if deps._employee_is_forfait_jour(row):
        raise PermissionError("Employé au forfait jours, badgeuse non applicable")

    today = aujourd_hui_local()
    entries = deps.time_entry_repository.get_entries_for_employee_on_day(
        employee_id=resolved_employee_id,
        company_id=company_id,
        day=today,
    )
    # Instant aware : un naïf soustrait aux timestamps aware de la base
    # levait TypeError au 2e badge du jour (badge-out en 500).
    now = maintenant_utc()
    event_type = deps._insert_toggle_entry(
        employee_id=resolved_employee_id,
        company_id=company_id,
        entries=entries,
        source=source,
        created_by=actor_user_id,
        now=now,
        terminal_device_id=terminal_device_id,
    )

    return deps._build_punch_response(
        employee_id=resolved_employee_id,
        company_id=company_id,
        employee_row=row,
        event_type=event_type,
        punched_at=now,
    )


def punch_by_username(
    *,
    username: str,
    company_id: str,
    actor_user_id: str,
    terminal_device_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fallback scan : identification par nom d'utilisateur (matricule)."""
    from app.core.database import supabase

    result = (
        supabase.table("employees")
        .select("id")
        .eq("company_id", company_id)
        .eq("username", username.strip())
        .eq("employment_status", "actif")
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise ValueError("Aucun employé actif avec cet identifiant")
    return punch_from_qr(
        qr_payload=None,
        employee_id=str(result.data["id"]),
        company_id=company_id,
        actor_user_id=actor_user_id,
        source=TimeEntrySource.RH,
        terminal_device_id=terminal_device_id,
    )


def list_punch_candidates(
    *,
    company_id: str,
    search: Optional[str] = None,
    only_not_badged_today: bool = False,
    limit: int = 24,
) -> List[Dict[str, Any]]:
    """
    Liste les employés éligibles au badgeage (recherche RH sans QR).
    """
    if not deps.get_badgeuse_settings(company_id).get("scan_mode_enabled", True):
        raise PermissionError("Le mode scan est désactivé pour cette entreprise")

    from app.core.database import supabase

    today = aujourd_hui_local()
    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())

    emp_result = (
        supabase.table("employees")
        .select("id, first_name, last_name, username, statut, is_forfait_jour, job_title")
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .order("last_name")
        .execute()
    )
    employees = [
        e for e in (emp_result.data or []) if not deps._employee_is_forfait_jour(e)
    ]

    rows = deps.time_entry_repository.get_entries_for_company_between(
        company_id=company_id,
        start=start_dt,
        end=end_dt,
        employee_ids=[str(e["id"]) for e in employees] if employees else None,
    )
    by_employee: Dict[str, List[TimeEntry]] = {}
    for row in rows:
        entry = deps.time_entry_repository._row_to_entry(row)  # type: ignore[attr-defined]
        by_employee.setdefault(entry.employee_id, []).append(entry)

    query = _normalize_search_text(search) if search else ""

    candidates: List[Dict[str, Any]] = []
    for emp in employees:
        emp_id = str(emp["id"])
        day_entries = by_employee.get(emp_id, [])
        badged_today = bool(day_entries)
        if only_not_badged_today and badged_today:
            continue

        first = str(emp.get("first_name") or "").strip()
        last = str(emp.get("last_name") or "").strip()
        username = str(emp.get("username") or "").strip()
        display_name = f"{first} {last}".strip() or username or emp_id

        if query:
            haystack = _normalize_search_text(
                f"{first} {last} {username} {display_name}"
            )
            if query not in haystack and not any(
                part in haystack for part in query.split() if len(part) >= 2
            ):
                continue

        next_action = (
            deps._resolve_next_event_type(day_entries).value
            if day_entries
            else TimeEntryType.ENTREE.value
        )
        candidates.append(
            {
                "employee_id": emp_id,
                "display_name": display_name,
                "username": username or None,
                "badged_today": badged_today,
                "next_action": next_action,
            }
        )

    candidates.sort(
        key=lambda c: (
            c["badged_today"],
            c["display_name"].lower(),
        )
    )
    return candidates[: max(1, min(limit, 50))]

