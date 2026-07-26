"""L'import DSN ne fabrique plus d'adresse e-mail.

La DSN ne transporte aucune adresse. Le champ doit rester vide plutôt que de porter une
adresse inventée : une fausse adresse passe le test `if email:` des notifications et fait
croire qu'un salarié a été prévenu alors que l'envoi part dans le vide.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_import.application.mapping import map_employee_payload
from app.modules.dsn_import.domain.model import (
    ContratBlock,
    EtablissementBlock,
    IndividuBlock,
)
from app.modules.employees.domain.rules import is_dsn_import_placeholder_email

pytestmark = pytest.mark.unit

SIRET = "53438649500053"


def _individu() -> IndividuBlock:
    return IndividuBlock(
        nom="AMATE",
        prenom="Vanessa",
        nir="283127512345678",
        date_naissance="01011983",
        contrats=[ContratBlock(date_debut="01012024", nature="01")],
    )


def test_payload_ne_porte_aucune_adresse_fabriquee() -> None:
    payload = map_employee_payload(_individu(), EtablissementBlock(siret=SIRET), SIRET)

    assert "email" not in payload, (
        "La DSN ne fournit pas d'adresse : la clé doit être absente du payload, "
        f"or elle vaut {payload.get('email')!r}"
    )


def test_aucun_suffixe_technique_dans_le_payload() -> None:
    payload = map_employee_payload(_individu(), EtablissementBlock(siret=SIRET), SIRET)

    valeurs = " ".join(str(v) for v in payload.values())
    assert "dsn-import.local" not in valeurs
    assert "dsn-import.eywai.fr" not in valeurs


def test_le_reste_du_payload_est_intact() -> None:
    """Retirer l'adresse ne doit rien casser d'autre dans la fiche importée."""
    payload = map_employee_payload(_individu(), EtablissementBlock(siret=SIRET), SIRET)

    assert payload["first_name"] == "Vanessa"
    assert payload["last_name"] == "AMATE"
    assert payload["nir"] == "283127512345678"
    assert payload["hire_date"] == "2024-01-01"


def test_les_anciennes_adresses_restent_reconnues() -> None:
    """Les 183 fiches déjà en base gardent leur adresse : la détection doit survivre."""
    assert is_dsn_import_placeholder_email(
        "import.vanessa.amate.383122@534386495.dsn-import.local"
    )
    assert is_dsn_import_placeholder_email("import.abc123@dsn-import.eywai.fr")
    assert is_dsn_import_placeholder_email("gaelle.bouali@eywai.access.local")
    assert is_dsn_import_placeholder_email("vanessa.amate@users.eywai")
    assert not is_dsn_import_placeholder_email("amatevanessa@yahoo.fr")
    assert not is_dsn_import_placeholder_email(None)
