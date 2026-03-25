"""
Tests unitaires du domaine contract_parser : value objects, règles, enums.

Sans DB, sans HTTP. Couvre toutes les entités, value objects et règles présents
dans app/modules/contract_parser/domain/.
"""

import pytest

from app.modules.contract_parser.domain.value_objects import ExtractionResult
from app.modules.contract_parser.domain.rules import is_scanned_pdf
from app.modules.contract_parser.domain.enums import ExtractionType


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Value objects : ExtractionResult
# ---------------------------------------------------------------------------


class TestExtractionResult:
    """Value object ExtractionResult (résultat d'extraction contrat/RIB/questionnaire)."""

    def test_creation_with_all_fields(self):
        """Création avec extracted_data, confidence, warnings."""
        data = {"first_name": "Jean", "last_name": "Dupont", "hire_date": "2024-01-15"}
        result = ExtractionResult(
            extracted_data=data,
            confidence="high",
            warnings=["Vérifier le NIR"],
        )
        assert result.extracted_data == data
        assert result.confidence == "high"
        assert result.warnings == ["Vérifier le NIR"]

    def test_creation_empty_data_and_warnings(self):
        """Création avec données vides et liste d'avertissements vide."""
        result = ExtractionResult(
            extracted_data={},
            confidence="low",
            warnings=[],
        )
        assert result.extracted_data == {}
        assert result.confidence == "low"
        assert result.warnings == []

    def test_is_frozen(self):
        """ExtractionResult est immutable (frozen dataclass) : réassignation interdite."""
        result = ExtractionResult(
            extracted_data={"iban": "FR7612345678901234567890123"},
            confidence="medium",
            warnings=[],
        )
        with pytest.raises(AttributeError):
            result.confidence = "high"
        with pytest.raises(AttributeError):
            result.warnings = ["nouveau"]


# ---------------------------------------------------------------------------
# Règles métier : is_scanned_pdf
# ---------------------------------------------------------------------------


class TestIsScannedPdf:
    """Règle is_scanned_pdf : détection PDF scanné vs texte extractible."""

    def test_empty_text_is_scanned(self):
        """Texte vide → considéré comme scanné (peu de texte)."""
        assert is_scanned_pdf("") is True

    def test_very_short_text_is_scanned(self):
        """Moins de 50 caractères alphanumériques → scanné."""
        assert is_scanned_pdf("abc") is True
        assert is_scanned_pdf("1234567890" * 4) is True  # 40 alphanum

    def test_long_text_high_ratio_not_scanned(self):
        """Texte long avec ratio alphanumérique élevé → pas scanné."""
        text = "Contrat de travail CDI entre la société X et M. Dupont. " * 20
        assert len(text) > 50
        alphanum = sum(c.isalnum() for c in text)
        assert (alphanum / len(text)) >= 0.3
        assert is_scanned_pdf(text) is False

    def test_long_text_low_ratio_is_scanned(self):
        """Texte long mais ratio alphanumérique < 0.3 → scanné (ex. OCR bruité)."""
        # Beaucoup d'espaces / caractères spéciaux
        text = "a" * 30 + " " * 100 + "." * 100
        alphanum = 30
        assert alphanum < 50  # donc < 50 alphanum → True
        assert is_scanned_pdf(text) is True

    def test_around_50_alphanumeric(self):
        """Exactement 50 caractères alphanumériques dans un texte plus long."""
        base = "a" * 50 + " " * 200
        # ratio = 50/250 = 0.2 < 0.3 → scanné
        assert is_scanned_pdf(base) is True

    def test_rich_text_not_scanned(self):
        """Texte riche type contrat extrait correctement → pas scanné."""
        text = (
            "CONTRAT DE TRAVAIL A DUREE INDETERMINEE\n"
            "Entre la société Example SARL et M. Jean Dupont.\n"
            "Date d'embauche : 01/03/2024. Salaire brut : 2500 euros."
        ) * 5
        assert is_scanned_pdf(text) is False


# ---------------------------------------------------------------------------
# Enums : ExtractionType
# ---------------------------------------------------------------------------


class TestExtractionType:
    """Énumération des types de document à extraire."""

    def test_values(self):
        """Valeurs attendues contract, rib, questionnaire."""
        assert ExtractionType.CONTRACT.value == "contract"
        assert ExtractionType.RIB.value == "rib"
        assert ExtractionType.QUESTIONNAIRE.value == "questionnaire"

    def test_enum_members(self):
        """Tous les membres sont présents."""
        assert len(ExtractionType) == 3
        names = {e.name for e in ExtractionType}
        assert names == {"CONTRACT", "RIB", "QUESTIONNAIRE"}

    def test_string_enum_comparison(self):
        """Comparaison avec string (StrEnum)."""
        assert ExtractionType.CONTRACT == "contract"
        assert ExtractionType.RIB == "rib"
