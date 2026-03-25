"""
Tests unitaires du domain rib_alerts : entités, value objects, règles, enums, exceptions.

Sans DB, sans HTTP. Couvre toutes les entités, règles et types du domain/.
"""

from datetime import datetime, timezone

import pytest

from app.modules.rib_alerts.domain.entities import RibAlert
from app.modules.rib_alerts.domain.enums import RibAlertSeverity, RibAlertType
from app.modules.rib_alerts.domain.exceptions import (
    MissingCompanyContextError,
    RibAlertDomainError,
    RibAlertNotFoundError,
)
from app.modules.rib_alerts.domain.rules import is_valid_alert_type, require_company_id


# --- Entité RibAlert ---


class TestRibAlertEntity:
    """Entité RibAlert : attributs et instanciation."""

    def test_rib_alert_creation_minimal(self):
        """Création avec champs obligatoires (company_id, alert_type, severity, title, message, details, is_read, is_resolved)."""
        alert = RibAlert(
            id="alert-1",
            company_id="company-1",
            employee_id=None,
            alert_type="rib_modified",
            severity="warning",
            title="IBAN modifié",
            message="L'IBAN a été modifié.",
            details={
                "old_iban_masked": "FR76***1234",
                "new_iban_masked": "FR76***5678",
            },
            is_read=False,
            is_resolved=False,
        )
        assert alert.id == "alert-1"
        assert alert.company_id == "company-1"
        assert alert.employee_id is None
        assert alert.alert_type == "rib_modified"
        assert alert.severity == "warning"
        assert alert.title == "IBAN modifié"
        assert alert.message == "L'IBAN a été modifié."
        assert alert.details == {
            "old_iban_masked": "FR76***1234",
            "new_iban_masked": "FR76***5678",
        }
        assert alert.is_read is False
        assert alert.is_resolved is False
        assert alert.resolved_at is None
        assert alert.resolution_note is None
        assert alert.resolved_by is None
        assert alert.created_at is None

    def test_rib_alert_creation_full(self):
        """Création avec tous les champs optionnels renseignés."""
        now = datetime.now(timezone.utc)
        alert = RibAlert(
            id="alert-2",
            company_id="company-2",
            employee_id="emp-1",
            alert_type="rib_duplicate",
            severity="error",
            title="IBAN en doublon",
            message="Cet IBAN est déjà utilisé.",
            details={
                "iban_masked": "FR76***9999",
                "duplicate_employees": [
                    {"id": "e1", "first_name": "A", "last_name": "B"}
                ],
            },
            is_read=True,
            is_resolved=True,
            resolved_at=now,
            resolution_note="Vérifié manuellement",
            resolved_by="user-1",
            created_at=now,
        )
        assert alert.employee_id == "emp-1"
        assert alert.alert_type == "rib_duplicate"
        assert alert.severity == "error"
        assert alert.is_read is True
        assert alert.is_resolved is True
        assert alert.resolved_at == now
        assert alert.resolution_note == "Vérifié manuellement"
        assert alert.resolved_by == "user-1"
        assert alert.created_at == now

    def test_rib_alert_is_mutable(self):
        """RibAlert est un dataclass non frozen : champs modifiables."""
        alert = RibAlert(
            id="a1",
            company_id="c1",
            employee_id=None,
            alert_type="rib_modified",
            severity="info",
            title="T",
            message="M",
            details={},
            is_read=False,
            is_resolved=False,
        )
        alert.is_read = True
        alert.is_resolved = True
        assert alert.is_read is True
        assert alert.is_resolved is True


# --- Enums ---


class TestRibAlertType:
    """Enum RibAlertType : types d'alerte RIB."""

    def test_rib_modified_value(self):
        assert RibAlertType.RIB_MODIFIED == "rib_modified"

    def test_rib_duplicate_value(self):
        assert RibAlertType.RIB_DUPLICATE == "rib_duplicate"

    def test_rib_alert_type_is_str_enum(self):
        assert str(RibAlertType.RIB_MODIFIED) == "rib_modified"
        assert RibAlertType("rib_duplicate") == RibAlertType.RIB_DUPLICATE

    def test_invalid_alert_type_raises_value_error(self):
        with pytest.raises(ValueError):
            RibAlertType("invalid_type")


class TestRibAlertSeverity:
    """Enum RibAlertSeverity : sévérité des alertes."""

    def test_severity_values(self):
        assert RibAlertSeverity.INFO == "info"
        assert RibAlertSeverity.WARNING == "warning"
        assert RibAlertSeverity.ERROR == "error"

    def test_severity_is_str_enum(self):
        assert RibAlertSeverity("warning") == RibAlertSeverity.WARNING


# --- Exceptions ---


class TestRibAlertDomainError:
    """Exception de base du domaine."""

    def test_inherits_from_exception(self):
        err = RibAlertDomainError("message")
        assert isinstance(err, Exception)
        assert str(err) == "message"


class TestMissingCompanyContextError:
    """Contexte entreprise absent."""

    def test_inherits_from_rib_alert_domain_error(self):
        err = MissingCompanyContextError("Aucune entreprise active.")
        assert isinstance(err, RibAlertDomainError)
        assert "Aucune entreprise active" in str(err)


class TestRibAlertNotFoundError:
    """Alerte introuvable ou hors contexte entreprise."""

    def test_inherits_from_rib_alert_domain_error(self):
        err = RibAlertNotFoundError("Alerte non trouvée")
        assert isinstance(err, RibAlertDomainError)
        assert "Alerte non trouvée" in str(err)


# --- Règles métier ---


class TestRequireCompanyId:
    """Règle require_company_id : exige un company_id non vide."""

    def test_valid_company_id_returns_stripped(self):
        assert require_company_id("company-123") == "company-123"
        assert require_company_id("  company-456  ") == "company-456"

    def test_none_raises_missing_company_context(self):
        with pytest.raises(MissingCompanyContextError) as exc_info:
            require_company_id(None)
        assert (
            "entreprise" in str(exc_info.value).lower()
            or "company" in str(exc_info.value).lower()
        )

    def test_empty_string_raises_missing_company_context(self):
        with pytest.raises(MissingCompanyContextError):
            require_company_id("")

    def test_whitespace_only_raises_missing_company_context(self):
        with pytest.raises(MissingCompanyContextError):
            require_company_id("   ")


class TestIsValidAlertType:
    """Règle is_valid_alert_type : filtre liste (None ou vide = pas de filtre)."""

    def test_none_returns_true(self):
        assert is_valid_alert_type(None) is True

    def test_empty_string_returns_true(self):
        assert is_valid_alert_type("") is True

    def test_rib_modified_returns_true(self):
        assert is_valid_alert_type("rib_modified") is True

    def test_rib_duplicate_returns_true(self):
        assert is_valid_alert_type("rib_duplicate") is True

    def test_invalid_type_returns_false(self):
        assert is_valid_alert_type("invalid") is False
        assert is_valid_alert_type("rib_changed") is False
