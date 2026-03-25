"""
Tests unitaires du domaine promotions : entités, value objects, règles, enums.

Aucune dépendance DB ni HTTP. Logique pure du domain/.
"""
from datetime import date, datetime


from app.modules.promotions.domain.entities import Promotion
from app.modules.promotions.domain import rules as domain_rules


# --- Entité Promotion ---


class TestPromotionEntity:
    """Entité Promotion (dataclass)."""

    def test_creation_with_required_fields(self):
        """Création avec champs requis uniquement."""
        p = Promotion(
            id="promo-1",
            company_id="co-1",
            employee_id="emp-1",
            promotion_type="salaire",
            status="draft",
            effective_date=date(2025, 6, 1),
            request_date=date(2025, 3, 1),
        )
        assert p.id == "promo-1"
        assert p.company_id == "co-1"
        assert p.employee_id == "emp-1"
        assert p.promotion_type == "salaire"
        assert p.status == "draft"
        assert p.effective_date == date(2025, 6, 1)
        assert p.request_date == date(2025, 3, 1)
        assert p.previous_job_title is None
        assert p.new_job_title is None
        assert p.grant_rh_access is False
        assert p.reason is None
        assert p.created_at is None

    def test_creation_with_optional_snapshots(self):
        """Création avec snapshot avant/après et accès RH."""
        p = Promotion(
            id="promo-2",
            company_id="co-1",
            employee_id="emp-2",
            promotion_type="poste",
            status="approved",
            effective_date=date(2025, 4, 1),
            request_date=date(2025, 2, 15),
            previous_job_title="Développeur",
            new_job_title="Lead Dev",
            previous_salary={"valeur": 3500, "devise": "EUR"},
            new_salary={"valeur": 4200, "devise": "EUR"},
            previous_rh_access="collaborateur_rh",
            new_rh_access="rh",
            grant_rh_access=True,
            reason="Evolution interne",
            approved_by="user-admin",
            approved_at=datetime(2025, 3, 10, 14, 0),
        )
        assert p.previous_job_title == "Développeur"
        assert p.new_job_title == "Lead Dev"
        assert p.previous_salary == {"valeur": 3500, "devise": "EUR"}
        assert p.new_salary == {"valeur": 4200, "devise": "EUR"}
        assert p.previous_rh_access == "collaborateur_rh"
        assert p.new_rh_access == "rh"
        assert p.grant_rh_access is True
        assert p.reason == "Evolution interne"
        assert p.approved_by == "user-admin"
        assert p.approved_at == datetime(2025, 3, 10, 14, 0)


# --- Enums / Literals ---


class TestPromotionEnums:
    """Types littéraux PromotionStatus, PromotionType, RhAccessRole."""

    def test_promotion_status_values_used_in_entity(self):
        """Statuts du workflow de promotion utilisables dans l'entité."""
        valid_statuses = [
            "draft",
            "pending_approval",
            "approved",
            "rejected",
            "effective",
            "cancelled",
        ]
        for s in valid_statuses:
            p = Promotion(
                id="p",
                company_id="c",
                employee_id="e",
                promotion_type="salaire",
                status=s,
                effective_date=date(2025, 1, 1),
                request_date=date(2025, 1, 1),
            )
            assert p.status == s

    def test_promotion_type_values_used_in_entity(self):
        """Types de promotion utilisables dans l'entité."""
        for t in ("poste", "salaire", "statut", "classification", "mixte"):
            p = Promotion(
                id="p",
                company_id="c",
                employee_id="e",
                promotion_type=t,
                status="draft",
                effective_date=date(2025, 1, 1),
                request_date=date(2025, 1, 1),
            )
            assert p.promotion_type == t

    def test_rh_access_role_values(self):
        """Rôles d'accès RH (utilisés dans les règles)."""
        assert domain_rules.get_available_rh_roles(None) == ["collaborateur_rh", "rh"]
        assert "admin" in domain_rules.get_available_rh_roles("collaborateur_rh")


# --- Règles : validate_rh_access_transition ---


class TestValidateRhAccessTransition:
    """Transition de rôle RH autorisée ou non."""

    def test_null_to_collaborateur_rh_allowed(self):
        """Aucun accès → collaborateur_rh autorisé."""
        assert domain_rules.validate_rh_access_transition(None, "collaborateur_rh") is True

    def test_null_to_rh_allowed(self):
        """Aucun accès → rh autorisé."""
        assert domain_rules.validate_rh_access_transition(None, "rh") is True

    def test_null_to_admin_not_allowed(self):
        """Aucun accès → admin non autorisé (doit passer par collaborateur_rh ou rh)."""
        assert domain_rules.validate_rh_access_transition(None, "admin") is False

    def test_collaborateur_rh_to_rh_allowed(self):
        """collaborateur_rh → rh autorisé."""
        assert domain_rules.validate_rh_access_transition("collaborateur_rh", "rh") is True

    def test_collaborateur_rh_to_admin_allowed(self):
        """collaborateur_rh → admin autorisé."""
        assert domain_rules.validate_rh_access_transition("collaborateur_rh", "admin") is True

    def test_collaborateur_rh_to_collaborateur_rh_not_allowed(self):
        """collaborateur_rh → collaborateur_rh (même rôle) non autorisé."""
        assert domain_rules.validate_rh_access_transition("collaborateur_rh", "collaborateur_rh") is False

    def test_rh_to_admin_allowed(self):
        """rh → admin autorisé."""
        assert domain_rules.validate_rh_access_transition("rh", "admin") is True

    def test_rh_to_collaborateur_rh_not_allowed(self):
        """rh → collaborateur_rh (rétrogradation) non autorisé."""
        assert domain_rules.validate_rh_access_transition("rh", "collaborateur_rh") is False

    def test_admin_no_transition(self):
        """admin → aucun autre rôle (déjà au maximum)."""
        assert domain_rules.validate_rh_access_transition("admin", "admin") is False
        assert domain_rules.validate_rh_access_transition("admin", "rh") is False
        assert domain_rules.validate_rh_access_transition("admin", "collaborateur_rh") is False

    def test_unknown_current_role_treated_like_null(self):
        """Rôle actuel inconnu → traité comme aucun accès (collaborateur_rh, rh autorisés)."""
        assert domain_rules.validate_rh_access_transition("unknown", "collaborateur_rh") is True
        assert domain_rules.validate_rh_access_transition("unknown", "rh") is True
        assert domain_rules.validate_rh_access_transition("unknown", "admin") is False


# --- Règles : get_available_rh_roles ---


class TestGetAvailableRhRoles:
    """Rôles RH disponibles selon le rôle actuel."""

    def test_no_current_role_returns_collaborateur_rh_and_rh(self):
        """Sans rôle actuel : collaborateur_rh et rh disponibles."""
        roles = domain_rules.get_available_rh_roles(None)
        assert "collaborateur_rh" in roles
        assert "rh" in roles
        assert "admin" not in roles

    def test_unknown_role_treated_like_no_access(self):
        """Rôle inconnu : traité comme aucun accès (collaborateur_rh et rh proposés)."""
        roles = domain_rules.get_available_rh_roles("unknown")
        assert roles == ["collaborateur_rh", "rh"]

    def test_collaborateur_rh_returns_rh_and_admin(self):
        """collaborateur_rh : rh et admin disponibles."""
        roles = domain_rules.get_available_rh_roles("collaborateur_rh")
        assert "rh" in roles
        assert "admin" in roles
        assert "collaborateur_rh" not in roles

    def test_rh_returns_admin_only(self):
        """rh : seul admin disponible."""
        roles = domain_rules.get_available_rh_roles("rh")
        assert roles == ["admin"]

    def test_admin_returns_empty(self):
        """admin : aucun rôle supérieur."""
        roles = domain_rules.get_available_rh_roles("admin")
        assert roles == []
