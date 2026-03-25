"""
Tests unitaires du domaine residence_permits : enums et règles métier.

Aucune dépendance DB ni HTTP. Couvre :
- ResidencePermitStatus (domain/enums.py)
- calculate_residence_permit_status, ANTICIPATION_THRESHOLD_DAYS (domain/rules.py)

Le module n'a pas d'entités ni de value objects persistés (fichiers réservés).
"""

from datetime import date, timedelta


from app.modules.residence_permits.domain.enums import ResidencePermitStatus
from app.modules.residence_permits.domain.rules import (
    ANTICIPATION_THRESHOLD_DAYS,
    calculate_residence_permit_status,
)


# --- Enums ---


class TestResidencePermitStatus:
    """Tests de l'enum ResidencePermitStatus."""

    def test_valid_value(self):
        assert ResidencePermitStatus.VALID.value == "valid"

    def test_to_renew_value(self):
        assert ResidencePermitStatus.TO_RENEW.value == "to_renew"

    def test_expired_value(self):
        assert ResidencePermitStatus.EXPIRED.value == "expired"

    def test_to_complete_value(self):
        assert ResidencePermitStatus.TO_COMPLETE.value == "to_complete"

    def test_all_members(self):
        """Tous les statuts attendus sont présents."""
        names = {s.name for s in ResidencePermitStatus}
        assert names == {"VALID", "TO_RENEW", "EXPIRED", "TO_COMPLETE"}


# --- Règles métier : calculate_residence_permit_status ---


class TestCalculateResidencePermitStatusNotSubject:
    """CAS 1 : Employé non soumis au titre de séjour."""

    def test_not_subject_returns_none_status_and_no_date(self):
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=False,
            residence_permit_expiry_date=date(2026, 12, 31),
            employment_status="actif",
        )
        assert result["is_subject_to_residence_permit"] is False
        assert result["residence_permit_status"] is None
        assert result["residence_permit_expiry_date"] is None
        assert result["residence_permit_days_remaining"] is None
        assert result["residence_permit_data_complete"] is None


class TestCalculateResidencePermitStatusExcludedEmployment:
    """CAS 2 : Employé soumis mais statut d'emploi exclu du suivi (hors actif/en_sortie)."""

    def test_employment_status_suspendu_returns_none_status(self):
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=date(2026, 6, 15),
            employment_status="suspendu",
        )
        assert result["is_subject_to_residence_permit"] is True
        assert result["residence_permit_status"] is None
        assert result["residence_permit_expiry_date"] == date(2026, 6, 15)
        assert result["residence_permit_days_remaining"] is None
        assert result["residence_permit_data_complete"] is False

    def test_employment_status_demissionnaire_returns_none_status(self):
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=date(2026, 6, 15),
            employment_status="demissionnaire",
        )
        assert result["is_subject_to_residence_permit"] is True
        assert result["residence_permit_status"] is None
        assert result["residence_permit_data_complete"] is False


class TestCalculateResidencePermitStatusNoExpiryDate:
    """CAS 3 : Employé soumis, actif/en_sortie, mais date d'expiration non renseignée."""

    def test_expiry_none_returns_to_complete(self):
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=None,
            employment_status="actif",
        )
        assert result["is_subject_to_residence_permit"] is True
        assert (
            result["residence_permit_status"] == ResidencePermitStatus.TO_COMPLETE.value
        )
        assert result["residence_permit_expiry_date"] is None
        assert result["residence_permit_days_remaining"] is None
        assert result["residence_permit_data_complete"] is False

    def test_expiry_none_en_sortie(self):
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=None,
            employment_status="en_sortie",
        )
        assert (
            result["residence_permit_status"] == ResidencePermitStatus.TO_COMPLETE.value
        )


class TestCalculateResidencePermitStatusWithExpiryDate:
    """CAS 4 : Calcul du statut selon la date d'expiration (actif ou en_sortie)."""

    def test_valid_far_future(self):
        """Date d'expiration au-delà du seuil d'anticipation → valid."""
        ref = date(2025, 3, 17)
        expiry = ref + timedelta(days=ANTICIPATION_THRESHOLD_DAYS + 10)
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=expiry,
            employment_status="actif",
            reference_date=ref,
        )
        assert result["residence_permit_status"] == ResidencePermitStatus.VALID.value
        assert result["residence_permit_data_complete"] is True
        assert (
            result["residence_permit_days_remaining"]
            == ANTICIPATION_THRESHOLD_DAYS + 10
        )
        assert result["residence_permit_expiry_date"] == expiry.isoformat()

    def test_to_renew_expiry_equals_reference(self):
        """Date d'expiration = date de référence → to_renew."""
        ref = date(2025, 3, 17)
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=ref,
            employment_status="actif",
            reference_date=ref,
        )
        assert result["residence_permit_status"] == ResidencePermitStatus.TO_RENEW.value
        assert result["residence_permit_days_remaining"] == 0

    def test_to_renew_within_anticipation_threshold(self):
        """Date d'expiration dans la fenêtre d'anticipation → to_renew."""
        ref = date(2025, 3, 17)
        expiry = ref + timedelta(days=30)  # < 45 jours
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=expiry,
            employment_status="actif",
            reference_date=ref,
        )
        assert result["residence_permit_status"] == ResidencePermitStatus.TO_RENEW.value
        assert result["residence_permit_days_remaining"] == 30

    def test_to_renew_exactly_at_threshold(self):
        """Date d'expiration exactement au seuil (ref + 45 jours) → to_renew (<= threshold)."""
        ref = date(2025, 3, 17)
        expiry = ref + timedelta(days=ANTICIPATION_THRESHOLD_DAYS)
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=expiry,
            employment_status="actif",
            reference_date=ref,
        )
        assert result["residence_permit_status"] == ResidencePermitStatus.TO_RENEW.value
        assert result["residence_permit_days_remaining"] == ANTICIPATION_THRESHOLD_DAYS

    def test_expired_past_date(self):
        """Date d'expiration dans le passé → expired."""
        ref = date(2025, 3, 17)
        expiry = ref - timedelta(days=10)
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=expiry,
            employment_status="actif",
            reference_date=ref,
        )
        assert result["residence_permit_status"] == ResidencePermitStatus.EXPIRED.value
        assert result["residence_permit_days_remaining"] == -10

    def test_reference_date_defaults_to_today(self):
        """Sans reference_date, utilise date.today() pour le calcul."""
        # On ne peut pas prédire le résultat sans fixer today ; on vérifie au moins la structure.
        result = calculate_residence_permit_status(
            is_subject_to_residence_permit=True,
            residence_permit_expiry_date=date(2030, 1, 1),
            employment_status="actif",
            reference_date=None,
        )
        assert "residence_permit_status" in result
        assert result["residence_permit_status"] in (
            ResidencePermitStatus.VALID.value,
            ResidencePermitStatus.TO_RENEW.value,
            ResidencePermitStatus.EXPIRED.value,
            ResidencePermitStatus.TO_COMPLETE.value,
        )
        assert result["residence_permit_data_complete"] is True


class TestAnticipationThreshold:
    """Constante métier ANTICIPATION_THRESHOLD_DAYS."""

    def test_threshold_value(self):
        """Seuil d'anticipation à 45 jours (aligné legacy)."""
        assert ANTICIPATION_THRESHOLD_DAYS == 45
