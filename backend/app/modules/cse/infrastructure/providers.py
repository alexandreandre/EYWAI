# app/modules/cse/infrastructure/providers.py
"""
Providers CSE — implémentations des interfaces domain (PDF, Excel, IA).
Délégation vers services existants ; comportement strictement identique.
"""

from typing import Any, Dict, List, Optional

from app.modules.cse.domain.interfaces import (
    ICSEExportProvider,
    ICSEPdfProvider,
    ICSERecordingAIProvider,
)


class CSEPdfProvider(ICSEPdfProvider):
    """Délègue à services.cse_pdf_service."""

    def generate_convocation(self, meeting_data: Dict[str, Any]) -> bytes:
        from app.modules.cse.infrastructure.cse_pdf_impl import generate_convocation_pdf

        return generate_convocation_pdf(meeting_data)

    def generate_minutes(
        self,
        meeting_data: Dict[str, Any],
        transcription: Optional[str] = None,
        summary: Optional[Dict] = None,
    ) -> bytes:
        from app.modules.cse.infrastructure.cse_pdf_impl import generate_minutes_pdf

        return generate_minutes_pdf(meeting_data, transcription, summary)

    def generate_election_calendar(
        self, cycle_data: Dict[str, Any], timeline: List[Dict[str, Any]]
    ) -> bytes:
        from app.modules.cse.infrastructure.cse_pdf_impl import (
            generate_election_calendar_pdf,
        )

        return generate_election_calendar_pdf(cycle_data, timeline)


class CSEExportProvider(ICSEExportProvider):
    """Délègue à services.cse_export_service."""

    def export_elected_members(self, members: List[Dict[str, Any]]) -> bytes:
        from app.modules.cse.infrastructure.cse_export_impl import (
            export_elected_members,
        )

        return export_elected_members(members)

    def export_delegation_hours(self, hours: List[Dict], summary: List[Dict]) -> bytes:
        from app.modules.cse.infrastructure.cse_export_impl import (
            export_delegation_hours,
        )

        return export_delegation_hours(hours, summary)

    def export_meetings_history(self, meetings: List[Dict[str, Any]]) -> bytes:
        from app.modules.cse.infrastructure.cse_export_impl import (
            export_meetings_history,
        )

        return export_meetings_history(meetings)


class CSERecordingAIProvider(ICSERecordingAIProvider):
    """Délègue à services.cse_ai_service."""

    def process_recording(self, meeting_id: str) -> Dict[str, Any]:
        from app.modules.cse.infrastructure.cse_ai_impl import process_recording

        return process_recording(meeting_id)


# Instances partagées pour l'application
cse_pdf_provider: ICSEPdfProvider = CSEPdfProvider()
cse_export_provider: ICSEExportProvider = CSEExportProvider()
cse_recording_ai_provider: ICSERecordingAIProvider = CSERecordingAIProvider()
