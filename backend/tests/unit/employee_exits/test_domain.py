"""
Tests unitaires du domaine employee_exits : entités, value objects, règles.

Aucune DB ni HTTP ; logique pure du domain/.
"""
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.modules.employee_exits.domain.entities import (
    ChecklistItemEntity,
    EmployeeExitEntity,
    ExitDocumentEntity,
)
from app.modules.employee_exits.domain.rules import (
    get_initial_status,
    get_valid_status_transitions,
)


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# EmployeeExitEntity
# ---------------------------------------------------------------------------


class TestEmployeeExitEntity:
    """Entité sortie de salarié."""

    def test_creation_with_required_fields(self):
        """Création avec tous les champs requis ; extra initialisé à {}."""
        eid = uuid4()
        cid = uuid4()
        emp_id = uuid4()
        entity = EmployeeExitEntity(
            id=eid,
            company_id=cid,
            employee_id=emp_id,
            exit_type="demission",
            status="demission_recue",
            exit_request_date=date(2025, 1, 15),
            last_working_day=date(2025, 3, 15),
            notice_period_days=60,
            is_gross_misconduct=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert entity.id == eid
        assert entity.company_id == cid
        assert entity.employee_id == emp_id
        assert entity.exit_type == "demission"
        assert entity.status == "demission_recue"
        assert entity.exit_request_date == date(2025, 1, 15)
        assert entity.last_working_day == date(2025, 3, 15)
        assert entity.notice_period_days == 60
        assert entity.is_gross_misconduct is False
        assert entity.extra == {}

    def test_creation_with_extra_dict(self):
        """extra peut être fourni ; sinon devient {}."""
        entity = EmployeeExitEntity(
            id=uuid4(),
            company_id=uuid4(),
            employee_id=uuid4(),
            exit_type="rupture_conventionnelle",
            status="rupture_en_negociation",
            exit_request_date=date(2025, 2, 1),
            last_working_day=date(2025, 4, 1),
            notice_period_days=0,
            is_gross_misconduct=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            extra={"exit_reason": "Départ à l'amiable"},
        )
        assert entity.extra == {"exit_reason": "Départ à l'amiable"}


# ---------------------------------------------------------------------------
# ExitDocumentEntity
# ---------------------------------------------------------------------------


class TestExitDocumentEntity:
    """Entité document de sortie."""

    def test_creation_uploaded_document(self):
        """Document uploadé : document_category 'uploaded'."""
        doc = ExitDocumentEntity(
            id=uuid4(),
            exit_id=uuid4(),
            company_id=uuid4(),
            document_type="lettre_demission",
            document_category="uploaded",
            storage_path="exits/exit-1/20250115_letter.pdf",
            filename="letter.pdf",
        )
        assert doc.document_category == "uploaded"
        assert doc.extra == {}

    def test_creation_generated_document(self):
        """Document généré : document_category 'generated'."""
        doc = ExitDocumentEntity(
            id=uuid4(),
            exit_id=uuid4(),
            company_id=uuid4(),
            document_type="certificat_travail",
            document_category="generated",
            storage_path="exits/exit-1/certificat_travail_20250115.pdf",
            filename="certificat_travail_20250115.pdf",
        )
        assert doc.document_category == "generated"


# ---------------------------------------------------------------------------
# ChecklistItemEntity
# ---------------------------------------------------------------------------


class TestChecklistItemEntity:
    """Entité item de checklist."""

    def test_creation_required_item(self):
        """Item obligatoire, non complété."""
        item = ChecklistItemEntity(
            id=uuid4(),
            exit_id=uuid4(),
            company_id=uuid4(),
            item_code="badge_return",
            item_label="Restitution du badge",
            item_category="materiel",
            is_completed=False,
            is_required=True,
            display_order=0,
        )
        assert item.is_required is True
        assert item.is_completed is False
        assert item.extra == {}

    def test_creation_completed_optional_item(self):
        """Item optionnel complété."""
        item = ChecklistItemEntity(
            id=uuid4(),
            exit_id=uuid4(),
            company_id=uuid4(),
            item_code="custom_note",
            item_label="Note personnalisée",
            item_category="autre",
            is_completed=True,
            is_required=False,
            display_order=10,
        )
        assert item.is_required is False
        assert item.is_completed is True


# ---------------------------------------------------------------------------
# Règles : get_initial_status
# ---------------------------------------------------------------------------


class TestGetInitialStatus:
    """Statut initial selon le type de sortie."""

    def test_demission(self):
        assert get_initial_status("demission") == "demission_recue"

    def test_rupture_conventionnelle(self):
        assert get_initial_status("rupture_conventionnelle") == "rupture_en_negociation"

    def test_licenciement(self):
        assert get_initial_status("licenciement") == "licenciement_convocation"

    def test_depart_retraite(self):
        assert get_initial_status("depart_retraite") == "demission_effective"

    def test_fin_periode_essai(self):
        assert get_initial_status("fin_periode_essai") == "demission_effective"

    def test_type_inconnu_default(self):
        """Type non mappé → fallback demission_recue."""
        assert get_initial_status("inconnu") == "demission_recue"


# ---------------------------------------------------------------------------
# Règles : get_valid_status_transitions
# ---------------------------------------------------------------------------


class TestGetValidStatusTransitions:
    """Transitions de statut autorisées."""

    def test_demission_recue_to_preavis(self):
        trans = get_valid_status_transitions("demission", "demission_recue")
        assert "demission_preavis_en_cours" in trans
        assert "demission_effective" in trans
        assert "annulee" in trans

    def test_demission_effective_to_archivee(self):
        trans = get_valid_status_transitions("demission", "demission_effective")
        assert trans == ["archivee"]

    def test_rupture_en_negociation_transitions(self):
        trans = get_valid_status_transitions("rupture_conventionnelle", "rupture_en_negociation")
        assert "rupture_validee" in trans
        assert "annulee" in trans

    def test_rupture_validee_to_homologuee(self):
        trans = get_valid_status_transitions("rupture_conventionnelle", "rupture_validee")
        assert "rupture_homologuee" in trans
        assert "annulee" in trans

    def test_rupture_effective_to_archivee(self):
        trans = get_valid_status_transitions("rupture_conventionnelle", "rupture_effective")
        assert trans == ["archivee"]

    def test_licenciement_convocation_to_notifie(self):
        trans = get_valid_status_transitions("licenciement", "licenciement_convocation")
        assert "licenciement_notifie" in trans
        assert "annulee" in trans

    def test_licenciement_effective_to_archivee(self):
        trans = get_valid_status_transitions("licenciement", "licenciement_effective")
        assert trans == ["archivee"]

    def test_depart_retraite_archivee_empty(self):
        trans = get_valid_status_transitions("depart_retraite", "archivee")
        assert trans == []

    def test_statut_inconnu_returns_empty(self):
        trans = get_valid_status_transitions("demission", "statut_inconnu")
        assert trans == []

    def test_type_inconnu_returns_empty(self):
        trans = get_valid_status_transitions("type_inconnu", "demission_recue")
        assert trans == []
