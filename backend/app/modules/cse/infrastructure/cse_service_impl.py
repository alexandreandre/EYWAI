# app/modules/cse/infrastructure/cse_service_impl.py
"""
Implémentation autonome de la logique CSE (ex-services.cse_service).
Utilise app.core.database et app.modules.cse.schemas uniquement.
"""

from datetime import date, datetime, timedelta, time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.database import supabase
from app.modules.cse.schemas import (
    ElectedMemberCreate,
    ElectedMemberUpdate,
    ElectedMemberRead,
    ElectedMemberListItem,
    MeetingCreate,
    MeetingUpdate,
    MeetingRead,
    MeetingListItem,
    MeetingParticipantRead,
    RecordingStatusRead,
    DelegationHourCreate,
    DelegationHourRead,
    DelegationQuotaRead,
    DelegationSummary,
    BDESDocumentCreate,
    BDESDocumentRead,
    ElectionCycleCreate,
    ElectionCycleRead,
    ElectionTimelineStepRead,
    ElectionAlert,
    MandateAlert,
    MeetingStatus,
)


# ============================================================================
# Fonctions utilitaires
# ============================================================================


def _check_module_active(company_id: str) -> None:
    """Toutes les entreprises ont accès à tous les modules. Aucune vérification."""
    return


def _is_elected_member(company_id: str, employee_id: str) -> bool:
    """Vérifie si un employé est élu actif."""
    response = (
        supabase.table("cse_elected_members")
        .select("id")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("is_active", True)
        .gte("end_date", date.today())
        .execute()
    )

    return len(response.data or []) > 0


def _parse_time(value: Any) -> Optional[time]:
    """Parse une valeur heure (string 'HH:MM:SS' ou 'HH:MM', ou time/datetime)."""
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, str):
        # PostgreSQL TIME renvoie "14:00:00" ; datetime.fromisoformat exige un datetime complet
        if "T" in value or len(value) > 10:
            return datetime.fromisoformat(value).time()
        return time.fromisoformat(value)
    return None


# ============================================================================
# Gestion des élus CSE
# ============================================================================


def get_elected_members(
    company_id: str, active_only: bool = True
) -> List[ElectedMemberListItem]:
    """Récupère la liste des élus CSE."""
    _check_module_active(company_id)

    query = (
        supabase.table("cse_elected_members")
        .select(
            """
        id,
        employee_id,
        role,
        college,
        start_date,
        end_date,
        is_active,
        employees!inner(
            id,
            first_name,
            last_name,
            job_title
        )
        """
        )
        .eq("company_id", company_id)
    )

    if active_only:
        query = query.eq("is_active", True).gte("end_date", date.today())

    query = query.order("start_date", desc=True)

    response = query.execute()
    members = response.data or []

    result = []
    for member in members:
        employee = member.get("employees", {})
        end_date = (
            datetime.fromisoformat(member["end_date"]).date()
            if isinstance(member["end_date"], str)
            else member["end_date"]
        )
        days_remaining = (
            (end_date - date.today()).days if end_date >= date.today() else None
        )

        result.append(
            ElectedMemberListItem(
                id=member["id"],
                employee_id=member["employee_id"],
                first_name=employee.get("first_name", ""),
                last_name=employee.get("last_name", ""),
                job_title=employee.get("job_title"),
                role=member["role"],
                college=member.get("college"),
                start_date=datetime.fromisoformat(member["start_date"]).date()
                if isinstance(member["start_date"], str)
                else member["start_date"],
                end_date=end_date,
                is_active=member["is_active"],
                days_remaining=days_remaining,
            )
        )

    return result


def create_elected_member(
    company_id: str, data: ElectedMemberCreate, created_by: Optional[str] = None
) -> ElectedMemberRead:
    """Crée un nouvel élu CSE."""
    _check_module_active(company_id)

    # Vérifier que l'employé existe
    employee_response = (
        supabase.table("employees")
        .select("id")
        .eq("id", data.employee_id)
        .eq("company_id", company_id)
        .execute()
    )

    if not employee_response.data:
        raise HTTPException(status_code=404, detail="Employé non trouvé")

    # Créer le mandat
    insert_data = {
        "company_id": company_id,
        "employee_id": data.employee_id,
        "role": data.role,
        "college": data.college,
        "start_date": data.start_date.isoformat(),
        "end_date": data.end_date.isoformat(),
        "is_active": True,
        "notes": data.notes,
    }

    response = supabase.table("cse_elected_members").insert(insert_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=500, detail="Erreur lors de la création du mandat"
        )

    member_data = response.data[0]
    return get_elected_member_by_id(member_data["id"])


def update_elected_member(
    member_id: str, data: ElectedMemberUpdate, company_id: str
) -> ElectedMemberRead:
    """Met à jour un élu CSE."""
    _check_module_active(company_id)

    # Vérifier que le mandat existe et appartient à l'entreprise
    existing = (
        supabase.table("cse_elected_members")
        .select("id, company_id")
        .eq("id", member_id)
        .eq("company_id", company_id)
        .execute()
    )

    if not existing.data:
        raise HTTPException(status_code=404, detail="Mandat non trouvé")

    # Préparer les données de mise à jour
    update_data = {}
    if data.role is not None:
        update_data["role"] = data.role
    if data.college is not None:
        update_data["college"] = data.college
    if data.start_date is not None:
        update_data["start_date"] = data.start_date.isoformat()
    if data.end_date is not None:
        update_data["end_date"] = data.end_date.isoformat()
    if data.is_active is not None:
        update_data["is_active"] = data.is_active
    if data.notes is not None:
        update_data["notes"] = data.notes

    if not update_data:
        return get_elected_member_by_id(member_id)

    response = (
        supabase.table("cse_elected_members")
        .update(update_data)
        .eq("id", member_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour")

    return get_elected_member_by_id(member_id)


def get_elected_member_by_id(member_id: str) -> ElectedMemberRead:
    """Récupère un élu CSE par son ID."""
    response = (
        supabase.table("cse_elected_members")
        .select(
            """
        *,
        employees!inner(
            id,
            first_name,
            last_name,
            job_title
        )
        """
        )
        .eq("id", member_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Mandat non trouvé")

    member = response.data[0]
    employee = member.get("employees", {})

    return ElectedMemberRead(
        id=member["id"],
        company_id=member["company_id"],
        employee_id=member["employee_id"],
        role=member["role"],
        college=member.get("college"),
        start_date=datetime.fromisoformat(member["start_date"]).date()
        if isinstance(member["start_date"], str)
        else member["start_date"],
        end_date=datetime.fromisoformat(member["end_date"]).date()
        if isinstance(member["end_date"], str)
        else member["end_date"],
        is_active=member["is_active"],
        notes=member.get("notes"),
        created_at=datetime.fromisoformat(member["created_at"])
        if isinstance(member["created_at"], str)
        else member["created_at"],
        updated_at=datetime.fromisoformat(member["updated_at"])
        if isinstance(member["updated_at"], str)
        else member["updated_at"],
        first_name=employee.get("first_name"),
        last_name=employee.get("last_name"),
        job_title=employee.get("job_title"),
    )


def get_elected_member_by_employee(
    company_id: str, employee_id: str
) -> Optional[ElectedMemberRead]:
    """Récupère le mandat actif d'un employé."""
    _check_module_active(company_id)

    response = (
        supabase.table("cse_elected_members")
        .select(
            """
        *,
        employees!inner(
            id,
            first_name,
            last_name,
            job_title
        )
        """
        )
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("is_active", True)
        .gte("end_date", date.today().isoformat())
        .order("start_date", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    member = response.data[0]
    employee = member.get("employees", {})

    return ElectedMemberRead(
        id=member["id"],
        company_id=member["company_id"],
        employee_id=member["employee_id"],
        role=member["role"],
        college=member.get("college"),
        start_date=datetime.fromisoformat(member["start_date"]).date()
        if isinstance(member["start_date"], str)
        else member["start_date"],
        end_date=datetime.fromisoformat(member["end_date"]).date()
        if isinstance(member["end_date"], str)
        else member["end_date"],
        is_active=member["is_active"],
        notes=member.get("notes"),
        created_at=datetime.fromisoformat(member["created_at"])
        if isinstance(member["created_at"], str)
        else member["created_at"],
        updated_at=datetime.fromisoformat(member["updated_at"])
        if isinstance(member["updated_at"], str)
        else member["updated_at"],
        first_name=employee.get("first_name"),
        last_name=employee.get("last_name"),
        job_title=employee.get("job_title"),
    )


def get_mandate_alerts(company_id: str, months_before: int = 3) -> List[MandateAlert]:
    """Récupère les alertes de fin de mandat."""
    _check_module_active(company_id)

    alert_date = date.today() + timedelta(days=months_before * 30)

    response = (
        supabase.table("cse_elected_members")
        .select(
            """
        id,
        employee_id,
        role,
        end_date,
        employees!inner(
            id,
            first_name,
            last_name
        )
        """
        )
        .eq("company_id", company_id)
        .eq("is_active", True)
        .lte("end_date", alert_date.isoformat())
        .gte("end_date", date.today().isoformat())
        .execute()
    )

    alerts = []
    for member in response.data or []:
        employee = member.get("employees", {})
        end_date = (
            datetime.fromisoformat(member["end_date"]).date()
            if isinstance(member["end_date"], str)
            else member["end_date"]
        )
        days_remaining = (end_date - date.today()).days
        months_remaining = days_remaining / 30.0

        alerts.append(
            MandateAlert(
                elected_member_id=member["id"],
                employee_id=member["employee_id"],
                first_name=employee.get("first_name", ""),
                last_name=employee.get("last_name", ""),
                role=member["role"],
                end_date=end_date,
                days_remaining=days_remaining,
                months_remaining=months_remaining,
            )
        )

    return alerts


# ============================================================================
# Gestion des réunions CSE
# ============================================================================


def get_meetings(
    company_id: str,
    status: Optional[MeetingStatus] = None,
    meeting_type: Optional[str] = None,
    participant_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[MeetingListItem]:
    """Récupère la liste des réunions CSE."""
    _check_module_active(company_id)

    if participant_id:
        # Si participant_id est fourni, récupérer uniquement les réunions où cet employé participe
        query = (
            supabase.table("cse_meeting_participants")
            .select(
                """
            meeting_id,
            cse_meetings!inner(
                id,
                title,
                meeting_date,
                meeting_time,
                meeting_type,
                status,
                created_at
            )
            """
            )
            .eq("employee_id", participant_id)
        )

        response = query.execute()
        meetings = []
        for participant in response.data or []:
            meeting = participant.get("cse_meetings", {})
            if meeting and meeting.get("company_id") == company_id:
                meetings.append(meeting)
    else:
        # Sinon, récupérer toutes les réunions de l'entreprise
        query = (
            supabase.table("cse_meetings")
            .select(
                """
            id,
            title,
            meeting_date,
            meeting_time,
            meeting_type,
            status,
            created_at,
            cse_meeting_participants(count)
            """
            )
            .eq("company_id", company_id)
        )

        if status:
            query = query.eq("status", status)
        if meeting_type:
            query = query.eq("meeting_type", meeting_type)

        query = query.order("meeting_date", desc=True)

        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        response = query.execute()
        meetings = response.data or []

    result = []
    for meeting in meetings:
        # Compter les participants
        participant_count = 0
        if "cse_meeting_participants" in meeting:
            participants_data = meeting["cse_meeting_participants"]
            if isinstance(participants_data, list):
                participant_count = len(participants_data)
            elif isinstance(participants_data, dict) and "count" in participants_data:
                participant_count = participants_data["count"]

        result.append(
            MeetingListItem(
                id=meeting["id"],
                title=meeting["title"],
                meeting_date=datetime.fromisoformat(meeting["meeting_date"]).date()
                if isinstance(meeting["meeting_date"], str)
                else meeting["meeting_date"],
                meeting_time=_parse_time(meeting.get("meeting_time")),
                meeting_type=meeting["meeting_type"],
                status=meeting["status"],
                participant_count=participant_count,
                created_at=datetime.fromisoformat(meeting["created_at"])
                if isinstance(meeting["created_at"], str)
                else meeting["created_at"],
            )
        )

    return result


def create_meeting(
    company_id: str, data: MeetingCreate, created_by: str
) -> MeetingRead:
    """Crée une nouvelle réunion CSE."""
    _check_module_active(company_id)

    # Créer la réunion
    meeting_data = {
        "company_id": company_id,
        "title": data.title,
        "meeting_date": data.meeting_date.isoformat(),
        "meeting_time": data.meeting_time.isoformat() if data.meeting_time else None,
        "location": data.location,
        "meeting_type": data.meeting_type,
        "status": "a_venir",
        "agenda": data.agenda,
        "notes": data.notes,
        "created_by": created_by,
    }

    response = supabase.table("cse_meetings").insert(meeting_data).execute()

    if not response.data:
        raise HTTPException(
            status_code=500, detail="Erreur lors de la création de la réunion"
        )

    meeting_id = response.data[0]["id"]

    # Ajouter les participants
    if data.participant_ids:
        add_participants(meeting_id, data.participant_ids)

    return get_meeting_by_id(meeting_id, company_id)


def get_meeting_by_id(meeting_id: str, company_id: str) -> MeetingRead:
    """Récupère une réunion par son ID."""
    _check_module_active(company_id)

    response = (
        supabase.table("cse_meetings")
        .select(
            """
        *,
        cse_meeting_participants(
            *,
            employees!inner(
                id,
                first_name,
                last_name,
                job_title
            )
        ),
        cse_meeting_recordings(
            status
        )
        """
        )
        .eq("id", meeting_id)
        .eq("company_id", company_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")

    meeting = response.data[0]

    # Transformer les participants
    participants = []
    for participant in meeting.get("cse_meeting_participants", []):
        employee = participant.get("employees", {})
        participants.append(
            MeetingParticipantRead(
                meeting_id=participant["meeting_id"],
                employee_id=participant["employee_id"],
                role=participant["role"],
                invited_at=datetime.fromisoformat(participant["invited_at"])
                if participant.get("invited_at")
                and isinstance(participant["invited_at"], str)
                else participant.get("invited_at"),
                confirmed_at=datetime.fromisoformat(participant["confirmed_at"])
                if participant.get("confirmed_at")
                and isinstance(participant["confirmed_at"], str)
                else participant.get("confirmed_at"),
                attended=participant.get("attended", False),
                first_name=employee.get("first_name"),
                last_name=employee.get("last_name"),
                job_title=employee.get("job_title"),
            )
        )

    # Statut d'enregistrement
    recording_status = None
    if meeting.get("cse_meeting_recordings"):
        recordings = meeting["cse_meeting_recordings"]
        if isinstance(recordings, list) and len(recordings) > 0:
            recording_status = recordings[0].get("status")
        elif isinstance(recordings, dict):
            recording_status = recordings.get("status")

    return MeetingRead(
        id=meeting["id"],
        company_id=meeting["company_id"],
        title=meeting["title"],
        meeting_date=datetime.fromisoformat(meeting["meeting_date"]).date()
        if isinstance(meeting["meeting_date"], str)
        else meeting["meeting_date"],
        meeting_time=_parse_time(meeting.get("meeting_time")),
        location=meeting.get("location"),
        meeting_type=meeting["meeting_type"],
        status=meeting["status"],
        agenda=meeting.get("agenda"),
        notes=meeting.get("notes"),
        convocations_pdf_path=meeting.get("convocations_pdf_path"),
        created_by=meeting.get("created_by"),
        created_at=datetime.fromisoformat(meeting["created_at"])
        if isinstance(meeting["created_at"], str)
        else meeting["created_at"],
        updated_at=datetime.fromisoformat(meeting["updated_at"])
        if isinstance(meeting["updated_at"], str)
        else meeting["updated_at"],
        participants=participants,
        participant_count=len(participants),
        recording_status=recording_status,
    )


def update_meeting(
    meeting_id: str, company_id: str, data: MeetingUpdate
) -> MeetingRead:
    """Met à jour une réunion CSE."""
    _check_module_active(company_id)

    # Vérifier que la réunion existe
    existing = (
        supabase.table("cse_meetings")
        .select("id")
        .eq("id", meeting_id)
        .eq("company_id", company_id)
        .execute()
    )

    if not existing.data:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")

    # Préparer les données de mise à jour
    update_data = {}
    if data.title is not None:
        update_data["title"] = data.title
    if data.meeting_date is not None:
        update_data["meeting_date"] = data.meeting_date.isoformat()
    if data.meeting_time is not None:
        update_data["meeting_time"] = data.meeting_time.isoformat()
    if data.location is not None:
        update_data["location"] = data.location
    if data.meeting_type is not None:
        update_data["meeting_type"] = data.meeting_type
    if data.status is not None:
        update_data["status"] = data.status
    if data.agenda is not None:
        update_data["agenda"] = data.agenda
    if data.notes is not None:
        update_data["notes"] = data.notes

    if not update_data:
        return get_meeting_by_id(meeting_id, company_id)

    response = (
        supabase.table("cse_meetings")
        .update(update_data)
        .eq("id", meeting_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour")

    return get_meeting_by_id(meeting_id, company_id)


def add_participants(
    meeting_id: str, employee_ids: List[str]
) -> List[MeetingParticipantRead]:
    """Ajoute des participants à une réunion."""
    # Vérifier que la réunion existe
    meeting_response = (
        supabase.table("cse_meetings")
        .select("id, company_id")
        .eq("id", meeting_id)
        .execute()
    )
    if not meeting_response.data:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")

    company_id = meeting_response.data[0]["company_id"]
    _check_module_active(company_id)

    # Ajouter les participants
    participants_data = []
    for employee_id in employee_ids:
        participants_data.append(
            {
                "meeting_id": meeting_id,
                "employee_id": employee_id,
                "role": "participant",
            }
        )

    response = (
        supabase.table("cse_meeting_participants").insert(participants_data).execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=500, detail="Erreur lors de l'ajout des participants"
        )

    # Récupérer les participants avec leurs informations
    return get_meeting_participants(meeting_id)


def remove_participant(meeting_id: str, employee_id: str) -> None:
    """Retire un participant d'une réunion."""
    # Vérifier que la réunion existe
    meeting_response = (
        supabase.table("cse_meetings")
        .select("id, company_id")
        .eq("id", meeting_id)
        .execute()
    )
    if not meeting_response.data:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")

    company_id = meeting_response.data[0]["company_id"]
    _check_module_active(company_id)

    # Supprimer le participant
    supabase.table("cse_meeting_participants").delete().eq("meeting_id", meeting_id).eq(
        "employee_id", employee_id
    ).execute()

    # Pas d'erreur si rien à supprimer (idempotent)


def get_meeting_participants(meeting_id: str) -> List[MeetingParticipantRead]:
    """Récupère la liste des participants d'une réunion."""
    response = (
        supabase.table("cse_meeting_participants")
        .select(
            """
        *,
        employees!inner(
            id,
            first_name,
            last_name,
            job_title
        )
        """
        )
        .eq("meeting_id", meeting_id)
        .execute()
    )

    participants = []
    for participant in response.data or []:
        employee = participant.get("employees", {})
        participants.append(
            MeetingParticipantRead(
                meeting_id=participant["meeting_id"],
                employee_id=participant["employee_id"],
                role=participant["role"],
                invited_at=datetime.fromisoformat(participant["invited_at"])
                if participant.get("invited_at")
                and isinstance(participant["invited_at"], str)
                else participant.get("invited_at"),
                confirmed_at=datetime.fromisoformat(participant["confirmed_at"])
                if participant.get("confirmed_at")
                and isinstance(participant["confirmed_at"], str)
                else participant.get("confirmed_at"),
                attended=participant.get("attended", False),
                first_name=employee.get("first_name"),
                last_name=employee.get("last_name"),
                job_title=employee.get("job_title"),
            )
        )

    return participants


# ============================================================================
# Gestion des enregistrements et synthèse IA
# ============================================================================


def start_recording(
    meeting_id: str, company_id: str, consents: List[Dict[str, Any]]
) -> RecordingStatusRead:
    """Démarre l'enregistrement d'une réunion avec consentements RGPD."""
    _check_module_active(company_id)

    # Vérifier que la réunion existe
    meeting = get_meeting_by_id(meeting_id, company_id)

    # Vérifier que tous les participants ont donné leur consentement
    participant_ids = {p.employee_id for p in meeting.participants or []}
    consent_ids = {c["employee_id"] for c in consents if c.get("consent_given")}

    if participant_ids != consent_ids:
        raise HTTPException(
            status_code=400,
            detail="Tous les participants doivent donner leur consentement",
        )

    # Créer ou mettre à jour l'enregistrement
    consent_data = [
        {"employee_id": c["employee_id"], "timestamp": datetime.now().isoformat()}
        for c in consents
        if c.get("consent_given")
    ]

    # Vérifier si un enregistrement existe déjà
    existing_response = (
        supabase.table("cse_meeting_recordings")
        .select("id")
        .eq("meeting_id", meeting_id)
        .execute()
    )

    if existing_response.data:
        # Mettre à jour
        update_data = {
            "status": "in_progress",
            "consent_given_by": consent_data,
            "recording_started_at": datetime.now().isoformat(),
        }
        response = (
            supabase.table("cse_meeting_recordings")
            .update(update_data)
            .eq("meeting_id", meeting_id)
            .execute()
        )
    else:
        # Créer
        insert_data = {
            "meeting_id": meeting_id,
            "status": "in_progress",
            "consent_given_by": consent_data,
            "recording_started_at": datetime.now().isoformat(),
        }
        response = (
            supabase.table("cse_meeting_recordings").insert(insert_data).execute()
        )

    if not response.data:
        raise HTTPException(
            status_code=500, detail="Erreur lors du démarrage de l'enregistrement"
        )

    return get_recording_status(meeting_id)


def stop_recording(meeting_id: str, company_id: str) -> RecordingStatusRead:
    """Arrête l'enregistrement d'une réunion."""
    _check_module_active(company_id)

    # Vérifier que la réunion existe
    meeting_response = (
        supabase.table("cse_meetings")
        .select("id")
        .eq("id", meeting_id)
        .eq("company_id", company_id)
        .execute()
    )
    if not meeting_response.data:
        raise HTTPException(status_code=404, detail="Réunion non trouvée")

    # Mettre à jour le statut
    update_data = {
        "status": "completed",
        "recording_ended_at": datetime.now().isoformat(),
    }

    response = (
        supabase.table("cse_meeting_recordings")
        .update(update_data)
        .eq("meeting_id", meeting_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")

    return get_recording_status(meeting_id)


def get_recording_status(meeting_id: str) -> RecordingStatusRead:
    """Récupère le statut d'un enregistrement."""
    response = (
        supabase.table("cse_meeting_recordings")
        .select("*")
        .eq("meeting_id", meeting_id)
        .execute()
    )

    if not response.data:
        return RecordingStatusRead(
            meeting_id=meeting_id,
            status="not_started",
            recording_started_at=None,
            recording_ended_at=None,
            consent_given_by=[],
            error_message=None,
            has_transcription=False,
            has_summary=False,
            has_minutes=False,
        )

    recording = response.data[0]

    return RecordingStatusRead(
        meeting_id=meeting_id,
        status=recording.get("status", "not_started"),
        recording_started_at=datetime.fromisoformat(recording["recording_started_at"])
        if recording.get("recording_started_at")
        and isinstance(recording["recording_started_at"], str)
        else recording.get("recording_started_at"),
        recording_ended_at=datetime.fromisoformat(recording["recording_ended_at"])
        if recording.get("recording_ended_at")
        and isinstance(recording["recording_ended_at"], str)
        else recording.get("recording_ended_at"),
        consent_given_by=recording.get("consent_given_by", []),
        error_message=recording.get("error_message"),
        has_transcription=bool(recording.get("transcription_text")),
        has_summary=bool(recording.get("ai_summary")),
        has_minutes=bool(recording.get("minutes_pdf_path")),
    )


# ============================================================================
# Gestion des heures de délégation
# ============================================================================


def get_delegation_quota(
    company_id: str, employee_id: str
) -> Optional[DelegationQuotaRead]:
    """Récupère le quota mensuel d'heures de délégation pour un employé."""
    _check_module_active(company_id)

    # Récupérer la convention collective de l'employé
    employee_response = (
        supabase.table("employees")
        .select("collective_agreement_id")
        .eq("id", employee_id)
        .execute()
    )
    if not employee_response.data:
        return None

    collective_agreement_id = employee_response.data[0].get("collective_agreement_id")

    if not collective_agreement_id:
        # Si pas de CC sur l'employé, prendre la première convention assignée à l'entreprise
        company_response = (
            supabase.table("company_collective_agreements")
            .select("collective_agreement_id")
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        if company_response.data:
            collective_agreement_id = company_response.data[0].get(
                "collective_agreement_id"
            )

    if not collective_agreement_id:
        return None

    # Récupérer le quota
    response = (
        supabase.table("cse_delegation_quotas")
        .select(
            """
        *,
        collective_agreements_catalog!inner(
            id,
            name
        )
        """
        )
        .eq("company_id", company_id)
        .eq("collective_agreement_id", collective_agreement_id)
        .execute()
    )

    if not response.data:
        return None

    quota = response.data[0]
    cc = quota.get("collective_agreements_catalog", {})

    return DelegationQuotaRead(
        id=quota["id"],
        company_id=quota["company_id"],
        collective_agreement_id=quota.get("collective_agreement_id"),
        quota_hours_per_month=float(quota["quota_hours_per_month"]),
        notes=quota.get("notes"),
        collective_agreement_name=cc.get("name"),
    )


def get_delegation_hours(
    company_id: str,
    employee_id: str,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> List[DelegationHourRead]:
    """Récupère les heures de délégation consommées."""
    _check_module_active(company_id)

    query = (
        supabase.table("cse_delegation_hours")
        .select(
            """
        *,
        employees!inner(
            id,
            first_name,
            last_name
        )
        """
        )
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
    )

    if period_start:
        query = query.gte("date", period_start.isoformat())
    if period_end:
        query = query.lte("date", period_end.isoformat())

    query = query.order("date", desc=True)

    response = query.execute()

    hours = []
    for hour in response.data or []:
        employee = hour.get("employees", {})
        hours.append(
            DelegationHourRead(
                id=hour["id"],
                company_id=hour["company_id"],
                employee_id=hour["employee_id"],
                date=datetime.fromisoformat(hour["date"]).date()
                if isinstance(hour["date"], str)
                else hour["date"],
                duration_hours=float(hour["duration_hours"]),
                reason=hour["reason"],
                meeting_id=hour.get("meeting_id"),
                created_by=hour.get("created_by"),
                created_at=datetime.fromisoformat(hour["created_at"])
                if isinstance(hour["created_at"], str)
                else hour["created_at"],
                first_name=employee.get("first_name"),
                last_name=employee.get("last_name"),
            )
        )

    return hours


def create_delegation_hour(
    company_id: str, employee_id: str, data: DelegationHourCreate, created_by: str
) -> DelegationHourRead:
    """Crée une heure de délégation."""
    _check_module_active(company_id)

    # Vérifier que l'employé existe
    employee_response = (
        supabase.table("employees")
        .select("id")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .execute()
    )
    if not employee_response.data:
        raise HTTPException(status_code=404, detail="Employé non trouvé")

    # Créer l'heure de délégation
    insert_data = {
        "company_id": company_id,
        "employee_id": employee_id,
        "date": data.date.isoformat(),
        "duration_hours": str(data.duration_hours),
        "reason": data.reason,
        "meeting_id": data.meeting_id,
        "created_by": created_by,
    }

    response = supabase.table("cse_delegation_hours").insert(insert_data).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création")

    hour = response.data[0]
    employee = employee_response.data[0]

    return DelegationHourRead(
        id=hour["id"],
        company_id=hour["company_id"],
        employee_id=hour["employee_id"],
        date=datetime.fromisoformat(hour["date"]).date()
        if isinstance(hour["date"], str)
        else hour["date"],
        duration_hours=float(hour["duration_hours"]),
        reason=hour["reason"],
        meeting_id=hour.get("meeting_id"),
        created_by=hour.get("created_by"),
        created_at=datetime.fromisoformat(hour["created_at"])
        if isinstance(hour["created_at"], str)
        else hour["created_at"],
        first_name=employee.get("first_name"),
        last_name=employee.get("last_name"),
    )


def get_delegation_summary(
    company_id: str, period_start: date, period_end: date
) -> List[DelegationSummary]:
    """Récupère le récapitulatif des heures de délégation pour tous les élus."""
    _check_module_active(company_id)

    # Récupérer tous les élus actifs
    elected_members = get_elected_members(company_id, active_only=True)

    summaries = []
    for member in elected_members:
        # Récupérer le quota
        quota = get_delegation_quota(company_id, member.employee_id)
        quota_hours = quota.quota_hours_per_month if quota else 0.0

        # Récupérer les heures consommées
        hours = get_delegation_hours(
            company_id, member.employee_id, period_start, period_end
        )
        consumed_hours = sum(h.duration_hours for h in hours)

        summaries.append(
            DelegationSummary(
                employee_id=member.employee_id,
                first_name=member.first_name,
                last_name=member.last_name,
                quota_hours_per_month=quota_hours,
                consumed_hours=consumed_hours,
                remaining_hours=max(0, quota_hours - consumed_hours),
                period_start=period_start,
                period_end=period_end,
            )
        )

    return summaries


# ============================================================================
# Gestion des documents BDES
# ============================================================================


def upload_bdes_document(
    company_id: str, data: BDESDocumentCreate, published_by: str
) -> BDESDocumentRead:
    """Upload un document BDES."""
    _check_module_active(company_id)

    insert_data = {
        "company_id": company_id,
        "title": data.title,
        "document_type": data.document_type,
        "file_path": data.file_path,
        "year": data.year,
        "is_visible_to_elected": data.is_visible_to_elected,
        "description": data.description,
        "published_by": published_by,
        "published_at": datetime.now().isoformat(),
    }

    response = supabase.table("cse_bdes_documents").insert(insert_data).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Erreur lors de l'upload")

    return get_bdes_document_by_id(response.data[0]["id"], company_id)


def get_bdes_documents(
    company_id: str,
    year: Optional[int] = None,
    document_type: Optional[str] = None,
    visible_to_elected_only: bool = False,
) -> List[BDESDocumentRead]:
    """Récupère la liste des documents BDES."""
    _check_module_active(company_id)

    query = (
        supabase.table("cse_bdes_documents")
        .select(
            """
        *,
        published_by_profile:profiles!cse_bdes_documents_published_by_fkey(
            id,
            first_name,
            last_name
        )
        """
        )
        .eq("company_id", company_id)
    )

    if year:
        query = query.eq("year", year)
    if document_type:
        query = query.eq("document_type", document_type)
    if visible_to_elected_only:
        query = query.eq("is_visible_to_elected", True)

    query = query.order("published_at", desc=True)

    response = query.execute()

    documents = []
    for doc in response.data or []:
        published_by_profile = doc.get("published_by_profile", {})
        published_by_name = None
        if published_by_profile:
            first = published_by_profile.get("first_name", "")
            last = published_by_profile.get("last_name", "")
            published_by_name = f"{first} {last}".strip() if first or last else None

        documents.append(
            BDESDocumentRead(
                id=doc["id"],
                company_id=doc["company_id"],
                title=doc["title"],
                document_type=doc["document_type"],
                file_path=doc["file_path"],
                year=doc.get("year"),
                published_at=datetime.fromisoformat(doc["published_at"])
                if doc.get("published_at") and isinstance(doc["published_at"], str)
                else doc.get("published_at"),
                published_by=doc.get("published_by"),
                is_visible_to_elected=doc["is_visible_to_elected"],
                description=doc.get("description"),
                created_at=datetime.fromisoformat(doc["created_at"])
                if isinstance(doc["created_at"], str)
                else doc["created_at"],
                updated_at=datetime.fromisoformat(doc["updated_at"])
                if isinstance(doc["updated_at"], str)
                else doc["updated_at"],
                published_by_name=published_by_name,
                download_url=None,  # Sera généré dans le router avec URL signée
            )
        )

    return documents


def get_bdes_document_by_id(document_id: str, company_id: str) -> BDESDocumentRead:
    """Récupère un document BDES par son ID."""
    _check_module_active(company_id)

    response = (
        supabase.table("cse_bdes_documents")
        .select(
            """
        *,
        published_by_profile:profiles!cse_bdes_documents_published_by_fkey(
            id,
            first_name,
            last_name
        )
        """
        )
        .eq("id", document_id)
        .eq("company_id", company_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    doc = response.data[0]
    published_by_profile = doc.get("published_by_profile", {})
    published_by_name = None
    if published_by_profile:
        first = published_by_profile.get("first_name", "")
        last = published_by_profile.get("last_name", "")
        published_by_name = f"{first} {last}".strip() if first or last else None

    return BDESDocumentRead(
        id=doc["id"],
        company_id=doc["company_id"],
        title=doc["title"],
        document_type=doc["document_type"],
        file_path=doc["file_path"],
        year=doc.get("year"),
        published_at=datetime.fromisoformat(doc["published_at"])
        if doc.get("published_at") and isinstance(doc["published_at"], str)
        else doc.get("published_at"),
        published_by=doc.get("published_by"),
        is_visible_to_elected=doc["is_visible_to_elected"],
        description=doc.get("description"),
        created_at=datetime.fromisoformat(doc["created_at"])
        if isinstance(doc["created_at"], str)
        else doc["created_at"],
        updated_at=datetime.fromisoformat(doc["updated_at"])
        if isinstance(doc["updated_at"], str)
        else doc["updated_at"],
        published_by_name=published_by_name,
        download_url=None,
    )


# ============================================================================
# Gestion du calendrier électoral
# ============================================================================


def create_election_cycle(
    company_id: str, data: ElectionCycleCreate
) -> ElectionCycleRead:
    """Crée un cycle électoral."""
    _check_module_active(company_id)

    insert_data = {
        "company_id": company_id,
        "cycle_name": data.cycle_name,
        "mandate_end_date": data.mandate_end_date.isoformat(),
        "election_date": data.election_date.isoformat() if data.election_date else None,
        "status": "in_progress",
        "notes": data.notes,
    }

    response = supabase.table("cse_election_cycles").insert(insert_data).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création")

    cycle_id = response.data[0]["id"]

    # Créer la timeline par défaut
    _create_default_timeline(cycle_id, data.mandate_end_date)

    return get_election_cycle_by_id(cycle_id, company_id)


def _create_default_timeline(cycle_id: str, mandate_end_date: date) -> None:
    """Crée une timeline électorale par défaut."""
    # Étapes standard J-180 à proclamation
    steps = [
        {
            "name": "Déclenchement des élections",
            "order": 1,
            "due_date": mandate_end_date - timedelta(days=180),
        },
        {
            "name": "Dépôt des listes",
            "order": 2,
            "due_date": mandate_end_date - timedelta(days=90),
        },
        {
            "name": "Campagne électorale",
            "order": 3,
            "due_date": mandate_end_date - timedelta(days=30),
        },
        {"name": "Élections", "order": 4, "due_date": mandate_end_date},
        {
            "name": "Proclamation des résultats",
            "order": 5,
            "due_date": mandate_end_date + timedelta(days=7),
        },
    ]

    timeline_data = [
        {
            "election_cycle_id": cycle_id,
            "step_name": step["name"],
            "step_order": step["order"],
            "due_date": step["due_date"].isoformat(),
            "status": "pending",
        }
        for step in steps
    ]

    supabase.table("cse_election_timeline").insert(timeline_data).execute()


def get_election_cycle_by_id(cycle_id: str, company_id: str) -> ElectionCycleRead:
    """Récupère un cycle électoral par son ID."""
    _check_module_active(company_id)

    response = (
        supabase.table("cse_election_cycles")
        .select(
            """
        *,
        cse_election_timeline(
            *
        )
        """
        )
        .eq("id", cycle_id)
        .eq("company_id", company_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Cycle électoral non trouvé")

    cycle = response.data[0]

    # Transformer la timeline
    timeline = []
    for step in cycle.get("cse_election_timeline", []):
        timeline.append(
            ElectionTimelineStepRead(
                id=step["id"],
                election_cycle_id=step["election_cycle_id"],
                step_name=step["step_name"],
                step_order=step["step_order"],
                due_date=datetime.fromisoformat(step["due_date"]).date()
                if isinstance(step["due_date"], str)
                else step["due_date"],
                completed_at=datetime.fromisoformat(step["completed_at"])
                if step.get("completed_at") and isinstance(step["completed_at"], str)
                else step.get("completed_at"),
                status=step["status"],
                notes=step.get("notes"),
                created_at=datetime.fromisoformat(step["created_at"])
                if isinstance(step["created_at"], str)
                else step["created_at"],
                updated_at=datetime.fromisoformat(step["updated_at"])
                if isinstance(step["updated_at"], str)
                else step["updated_at"],
            )
        )

    mandate_end = (
        datetime.fromisoformat(cycle["mandate_end_date"]).date()
        if isinstance(cycle["mandate_end_date"], str)
        else cycle["mandate_end_date"]
    )
    days_until = (mandate_end - date.today()).days

    return ElectionCycleRead(
        id=cycle["id"],
        company_id=cycle["company_id"],
        cycle_name=cycle["cycle_name"],
        mandate_end_date=mandate_end,
        election_date=datetime.fromisoformat(cycle["election_date"]).date()
        if cycle.get("election_date") and isinstance(cycle["election_date"], str)
        else cycle.get("election_date"),
        status=cycle["status"],
        results_pdf_path=cycle.get("results_pdf_path"),
        minutes_pdf_path=cycle.get("minutes_pdf_path"),
        notes=cycle.get("notes"),
        created_at=datetime.fromisoformat(cycle["created_at"])
        if isinstance(cycle["created_at"], str)
        else cycle["created_at"],
        updated_at=datetime.fromisoformat(cycle["updated_at"])
        if isinstance(cycle["updated_at"], str)
        else cycle["updated_at"],
        timeline=timeline,
        days_until_mandate_end=days_until,
    )


def get_election_cycles(company_id: str) -> List[ElectionCycleRead]:
    """Récupère tous les cycles électoraux."""
    _check_module_active(company_id)

    response = (
        supabase.table("cse_election_cycles")
        .select("id")
        .eq("company_id", company_id)
        .order("mandate_end_date", desc=True)
        .execute()
    )

    cycles = []
    for cycle in response.data or []:
        cycles.append(get_election_cycle_by_id(cycle["id"], company_id))

    return cycles


def get_election_alerts(company_id: str) -> List[ElectionAlert]:
    """Récupère les alertes électorales (J-180, J-90, J-30)."""
    _check_module_active(company_id)

    cycles = get_election_cycles(company_id)
    alerts = []

    for cycle in cycles:
        days_remaining = cycle.days_until_mandate_end or 0

        if days_remaining <= 0:
            alert_level = "critical"
            message = "Le mandat se termine aujourd'hui ou est déjà terminé"
        elif days_remaining <= 30:
            alert_level = "critical"
            message = f"Le mandat se termine dans {days_remaining} jours"
        elif days_remaining <= 90:
            alert_level = "warning"
            message = f"Le mandat se termine dans {days_remaining} jours"
        elif days_remaining <= 180:
            alert_level = "info"
            message = f"Le mandat se termine dans {days_remaining} jours"
        else:
            continue  # Pas d'alerte si > 180 jours

        alerts.append(
            ElectionAlert(
                cycle_id=cycle.id,
                cycle_name=cycle.cycle_name,
                mandate_end_date=cycle.mandate_end_date,
                days_remaining=days_remaining,
                alert_level=alert_level,
                message=message,
            )
        )

    return alerts
