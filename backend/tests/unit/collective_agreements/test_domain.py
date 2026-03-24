"""
Tests du domain collective_agreements : entités, value objects, règles, exceptions.

Sans DB, sans HTTP. Comportement pur du domaine.
"""
from datetime import date, datetime
from unittest.mock import patch

import pytest

from app.modules.collective_agreements.domain.entities import (
    CollectiveAgreementCatalogEntity,
    CompanyAssignmentEntity,
    CachedAgreementTextEntity,
)
from app.modules.collective_agreements.domain.exceptions import (
    CollectiveAgreementError,
    NotFoundError,
    ForbiddenError,
    ValidationError,
)
from app.modules.collective_agreements.domain.rules import (
    idcc_variants,
    build_catalog_update_dict,
    generate_upload_path,
)


# --- Entités ---


class TestCollectiveAgreementCatalogEntity:
    """Entité catalogue (convention du catalogue)."""

    def test_instanciation_with_required_fields(self):
        now = datetime.now()
        e = CollectiveAgreementCatalogEntity(
            id="agr-1",
            name="Convention Syntec",
            idcc="1486",
            description="Convention informatique",
            sector="Informatique",
            effective_date=date(2020, 1, 1),
            is_active=True,
            rules_pdf_path="/catalog/doc.pdf",
            rules_pdf_filename="doc.pdf",
            created_at=now,
            updated_at=now,
        )
        assert e.id == "agr-1"
        assert e.name == "Convention Syntec"
        assert e.idcc == "1486"
        assert e.description == "Convention informatique"
        assert e.sector == "Informatique"
        assert e.effective_date == date(2020, 1, 1)
        assert e.is_active is True
        assert e.rules_pdf_path == "/catalog/doc.pdf"
        assert e.rules_pdf_filename == "doc.pdf"
        assert e.rules_pdf_url is None

    def test_rules_pdf_url_optional_default_none(self):
        now = datetime.now()
        e = CollectiveAgreementCatalogEntity(
            id="a",
            name="CC",
            idcc="1234",
            description=None,
            sector=None,
            effective_date=None,
            is_active=True,
            rules_pdf_path=None,
            rules_pdf_filename=None,
            created_at=now,
            updated_at=now,
            rules_pdf_url="https://signed.url/pdf",
        )
        assert e.rules_pdf_url == "https://signed.url/pdf"


class TestCompanyAssignmentEntity:
    """Entité assignation entreprise <-> convention."""

    def test_instanciation(self):
        now = datetime.now()
        e = CompanyAssignmentEntity(
            id="assign-1",
            company_id="company-uuid",
            collective_agreement_id="agr-uuid",
            assigned_at=now,
            assigned_by="user-123",
        )
        assert e.id == "assign-1"
        assert e.company_id == "company-uuid"
        assert e.collective_agreement_id == "agr-uuid"
        assert e.assigned_at == now
        assert e.assigned_by == "user-123"
        assert e.agreement_details is None

    def test_agreement_details_optional(self):
        now = datetime.now()
        details = CollectiveAgreementCatalogEntity(
            id="agr-uuid",
            name="CC",
            idcc="1486",
            description=None,
            sector=None,
            effective_date=None,
            is_active=True,
            rules_pdf_path=None,
            rules_pdf_filename=None,
            created_at=now,
            updated_at=now,
        )
        e = CompanyAssignmentEntity(
            id="a",
            company_id="c",
            collective_agreement_id="agr-uuid",
            assigned_at=now,
            assigned_by=None,
            agreement_details=details,
        )
        assert e.agreement_details is not None
        assert e.agreement_details.name == "CC"


class TestCachedAgreementTextEntity:
    """Entité cache texte PDF (pour le chat)."""

    def test_instanciation(self):
        e = CachedAgreementTextEntity(
            agreement_id="agr-1",
            full_text="Contenu extrait du PDF...",
            character_count=15000,
        )
        assert e.agreement_id == "agr-1"
        assert e.full_text == "Contenu extrait du PDF..."
        assert e.character_count == 15000
        assert e.pdf_hash is None

    def test_pdf_hash_optional(self):
        e = CachedAgreementTextEntity(
            agreement_id="agr-1",
            full_text="...",
            character_count=3,
            pdf_hash="abc123",
        )
        assert e.pdf_hash == "abc123"


# --- Règles (domain/rules.py) ---


class TestIdccVariants:
    """Règle idcc_variants : variantes pour recherche convention_classifications."""

    def test_idcc_brut_sans_zeros(self):
        assert idcc_variants("1486") == ["1486", "1486", "1486"]

    def test_idcc_avec_zeros_en_tete(self):
        assert idcc_variants("0123") == ["0123", "123", "0123"]

    def test_idcc_court_zfill_4(self):
        assert idcc_variants("12") == ["12", "12", "0012"]

    def test_idcc_vide_ou_none(self):
        assert idcc_variants("") == ["", "", "0000"]
        assert idcc_variants("   ") == ["", "", "0000"]
        assert idcc_variants(None) == ["", "", "0000"]

    def test_idcc_strip(self):
        assert idcc_variants("  1486  ") == ["1486", "1486", "1486"]

    def test_idcc_uniquement_zeros(self):
        assert idcc_variants("0000") == ["0000", "0", "0000"]


class TestBuildCatalogUpdateDict:
    """Règle build_catalog_update_dict : filtre None sauf champs PDF."""

    def test_garde_toutes_les_valeurs_non_none(self):
        raw = {"name": "Nouveau nom", "idcc": "1486", "description": "Desc"}
        out = build_catalog_update_dict(raw)
        assert out == {"name": "Nouveau nom", "idcc": "1486", "description": "Desc"}

    def test_ignore_none_sauf_rules_pdf(self):
        raw = {
            "name": "Nom",
            "description": None,
            "rules_pdf_path": None,
            "rules_pdf_filename": "fichier.pdf",
        }
        out = build_catalog_update_dict(raw)
        assert out["name"] == "Nom"
        assert "description" not in out
        assert out["rules_pdf_path"] is None
        assert out["rules_pdf_filename"] == "fichier.pdf"

    def test_vide_si_tout_none_sauf_pdf(self):
        raw = {"rules_pdf_path": None, "rules_pdf_filename": None}
        out = build_catalog_update_dict(raw)
        assert out == {"rules_pdf_path": None, "rules_pdf_filename": None}

    def test_dict_vide_entree_vide(self):
        assert build_catalog_update_dict({}) == {}


class TestGenerateUploadPath:
    """Règle generate_upload_path : chemin unique catalog/{iso}-{uuid}{ext}."""

    def test_contient_prefix_catalog_et_extension(self):
        path = generate_upload_path("document.pdf")
        assert path.startswith("catalog/")
        assert path.endswith(".pdf")
        parts = path.replace("catalog/", "").replace(".pdf", "").split("-")
        assert len(parts) >= 2  # iso + uuid hex

    def test_conserve_extension(self):
        path = generate_upload_path("regles.PDF")
        assert path.lower().endswith(".pdf")

    def test_sans_extension(self):
        path = generate_upload_path("sans_ext")
        assert path.startswith("catalog/")
        assert "sans_ext" not in path  # remplacé par iso-uuid


# --- Exceptions ---


class TestCollectiveAgreementError:
    """Exception de base du module."""

    def test_message_et_code(self):
        e = CollectiveAgreementError("Message custom", code="custom_code")
        assert str(e) == "Message custom"
        assert e.message == "Message custom"
        assert e.code == "custom_code"

    def test_code_default_error(self):
        e = CollectiveAgreementError("Erreur")
        assert e.code == "error"


class TestNotFoundError:
    """Ressource non trouvée."""

    def test_herite_base(self):
        e = NotFoundError("Convention non trouvée")
        assert isinstance(e, CollectiveAgreementError)
        assert e.message == "Convention non trouvée"
        assert e.code == "not_found"

    def test_message_par_defaut(self):
        e = NotFoundError()
        assert "Ressource" in e.message


class TestForbiddenError:
    """Accès refusé."""

    def test_code_forbidden(self):
        e = ForbiddenError("Accès non autorisé")
        assert e.code == "forbidden"
        assert e.message == "Accès non autorisé"


class TestValidationError:
    """Données invalides."""

    def test_code_validation_error(self):
        e = ValidationError("Aucune donnée à mettre à jour")
        assert e.code == "validation_error"
        assert isinstance(e, CollectiveAgreementError)
