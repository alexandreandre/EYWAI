"""
Tests unitaires du domain uploads : entités, value objects et règles.

Sans DB, sans HTTP. Couvre EntityType (enum) et toutes les règles du domain/rules.py.
Les fichiers domain/entities.py et domain/value_objects.py sont des placeholders vides :
aucun test pour entités ou value objects.
"""

from app.modules.uploads.domain.enums import EntityType
from app.modules.uploads.domain.rules import (
    ALLOWED_LOGO_MIMETYPES,
    LOGO_SCALE_MAX,
    LOGO_SCALE_MIN,
    MAX_LOGO_SIZE_BYTES,
    is_allowed_logo_content_type,
    is_logo_scale_valid,
    is_logo_size_valid,
    is_valid_entity_type,
)


class TestEntityType:
    """Enum EntityType (company / group)."""

    def test_company_value(self):
        assert EntityType.COMPANY.value == "company"

    def test_group_value(self):
        assert EntityType.GROUP.value == "group"

    def test_entity_type_members(self):
        assert set(e.value for e in EntityType) == {"company", "group"}


class TestAllowedLogoMimetypes:
    """Constante ALLOWED_LOGO_MIMETYPES."""

    def test_contains_expected_types(self):
        expected = {"image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/webp"}
        assert ALLOWED_LOGO_MIMETYPES == expected

    def test_is_frozenset(self):
        assert isinstance(ALLOWED_LOGO_MIMETYPES, frozenset)


class TestMaxLogoSize:
    """Constante MAX_LOGO_SIZE_BYTES."""

    def test_is_2_mb(self):
        assert MAX_LOGO_SIZE_BYTES == 2 * 1024 * 1024


class TestLogoScaleBounds:
    """Constantes LOGO_SCALE_MIN et LOGO_SCALE_MAX."""

    def test_scale_min(self):
        assert LOGO_SCALE_MIN == 0.5

    def test_scale_max(self):
        assert LOGO_SCALE_MAX == 2.0


class TestIsAllowedLogoContentType:
    """Règle is_allowed_logo_content_type."""

    def test_png_allowed(self):
        assert is_allowed_logo_content_type("image/png") is True

    def test_jpeg_allowed(self):
        assert is_allowed_logo_content_type("image/jpeg") is True

    def test_jpg_allowed(self):
        assert is_allowed_logo_content_type("image/jpg") is True

    def test_svg_allowed(self):
        assert is_allowed_logo_content_type("image/svg+xml") is True

    def test_webp_allowed(self):
        assert is_allowed_logo_content_type("image/webp") is True

    def test_none_returns_false(self):
        assert is_allowed_logo_content_type(None) is False

    def test_empty_string_returns_false(self):
        assert is_allowed_logo_content_type("") is False

    def test_pdf_rejected(self):
        assert is_allowed_logo_content_type("application/pdf") is False

    def test_gif_rejected(self):
        assert is_allowed_logo_content_type("image/gif") is False


class TestIsLogoSizeValid:
    """Règle is_logo_size_valid."""

    def test_zero_valid(self):
        assert is_logo_size_valid(0) is True

    def test_max_valid(self):
        assert is_logo_size_valid(MAX_LOGO_SIZE_BYTES) is True

    def test_under_max_valid(self):
        assert is_logo_size_valid(MAX_LOGO_SIZE_BYTES - 1) is True

    def test_over_max_invalid(self):
        assert is_logo_size_valid(MAX_LOGO_SIZE_BYTES + 1) is False

    def test_negative_invalid(self):
        assert is_logo_size_valid(-1) is False


class TestIsLogoScaleValid:
    """Règle is_logo_scale_valid."""

    def test_min_valid(self):
        assert is_logo_scale_valid(LOGO_SCALE_MIN) is True

    def test_max_valid(self):
        assert is_logo_scale_valid(LOGO_SCALE_MAX) is True

    def test_mid_valid(self):
        assert is_logo_scale_valid(1.0) is True

    def test_below_min_invalid(self):
        assert is_logo_scale_valid(LOGO_SCALE_MIN - 0.1) is False

    def test_above_max_invalid(self):
        assert is_logo_scale_valid(LOGO_SCALE_MAX + 0.1) is False


class TestIsValidEntityType:
    """Règle is_valid_entity_type."""

    def test_company_valid(self):
        assert is_valid_entity_type("company") is True

    def test_group_valid(self):
        assert is_valid_entity_type("group") is True

    def test_other_invalid(self):
        assert is_valid_entity_type("other") is False

    def test_empty_invalid(self):
        assert is_valid_entity_type("") is False

    def test_company_uppercase_invalid(self):
        assert is_valid_entity_type("Company") is False
