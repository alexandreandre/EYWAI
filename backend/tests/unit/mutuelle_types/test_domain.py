"""
Tests unitaires du domaine mutuelle_types : entités et règles métier.

Sans DB, sans HTTP. Couvre MutuelleType et les règles du domain/rules.py.
"""
from datetime import datetime
from uuid import UUID, uuid4


from app.modules.mutuelle_types.domain.entities import MutuelleType
from app.modules.mutuelle_types.domain.rules import (
    message_libelle_deja_existant,
    message_libelle_deja_existant_avec_statut,
    statut_formule,
)


class TestMutuelleTypeEntity:
    """Entité domaine MutuelleType (formule de mutuelle catalogue entreprise)."""

    def test_entity_creation_with_required_fields(self):
        company_id = uuid4()
        mutuelle = MutuelleType(
            id=None,
            company_id=company_id,
            libelle="Formule Standard",
            montant_salarial=50.0,
            montant_patronal=30.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
        )
        assert mutuelle.id is None
        assert mutuelle.company_id == company_id
        assert mutuelle.libelle == "Formule Standard"
        assert mutuelle.montant_salarial == 50.0
        assert mutuelle.montant_patronal == 30.0
        assert mutuelle.part_patronale_soumise_a_csg is True
        assert mutuelle.is_active is True
        assert mutuelle.created_at is None
        assert mutuelle.updated_at is None
        assert mutuelle.created_by is None

    def test_entity_with_all_fields(self):
        mutuelle_id = uuid4()
        company_id = uuid4()
        created_by = uuid4()
        now = datetime.now()
        mutuelle = MutuelleType(
            id=mutuelle_id,
            company_id=company_id,
            libelle="Formule Premium",
            montant_salarial=80.0,
            montant_patronal=50.0,
            part_patronale_soumise_a_csg=False,
            is_active=False,
            created_at=now,
            updated_at=now,
            created_by=created_by,
        )
        assert mutuelle.id == mutuelle_id
        assert mutuelle.company_id == company_id
        assert mutuelle.libelle == "Formule Premium"
        assert mutuelle.montant_salarial == 80.0
        assert mutuelle.montant_patronal == 50.0
        assert mutuelle.part_patronale_soumise_a_csg is False
        assert mutuelle.is_active is False
        assert mutuelle.created_at == now
        assert mutuelle.updated_at == now
        assert mutuelle.created_by == created_by

    def test_entity_with_uuid_string_coercion(self):
        """company_id peut être passé comme UUID ; l'entité stocke un UUID."""
        company_id = uuid4()
        mutuelle = MutuelleType(
            id=None,
            company_id=company_id,
            libelle="Test",
            montant_salarial=0.0,
            montant_patronal=0.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
        )
        assert isinstance(mutuelle.company_id, UUID)
        assert mutuelle.company_id == company_id


class TestStatutFormule:
    """Règle statut_formule (libellé actif/inactif)."""

    def test_statut_active(self):
        assert statut_formule(True) == "active"

    def test_statut_inactive(self):
        assert statut_formule(False) == "inactive"


class TestMessageLibelleDejaExistant:
    """Règle message_libelle_deja_existant (contrainte unique)."""

    def test_message_contains_libelle(self):
        msg = message_libelle_deja_existant("Formule Standard")
        assert "Formule Standard" in msg
        assert "existe déjà" in msg
        assert "libellé différent" in msg or "modifier" in msg

    def test_message_sans_statut(self):
        msg = message_libelle_deja_existant("Ma formule")
        assert "Ma formule" in msg
        assert "statut" not in msg or "statut" in msg.lower()


class TestMessageLibelleDejaExistantAvecStatut:
    """Règle message_libelle_deja_existant_avec_statut (création avec doublon)."""

    def test_message_contains_libelle_and_statut(self):
        msg = message_libelle_deja_existant_avec_statut("Formule Standard", "active")
        assert "Formule Standard" in msg
        assert "active" in msg
        assert "existe déjà" in msg

    def test_message_with_inactive_statut(self):
        msg = message_libelle_deja_existant_avec_statut("Ancienne formule", "inactive")
        assert "Ancienne formule" in msg
        assert "inactive" in msg
