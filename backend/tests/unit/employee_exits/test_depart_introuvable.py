"""Un départ disparu (supprimé avec son salarié) se lit comme introuvable : 404, jamais 500.

Avec maybe_single(), postgrest renvoie None (et non une réponse vide) quand aucune
ligne ne correspond ; le dépôt le lisait comme une réponse.
"""

from unittest.mock import MagicMock

import pytest

from app.modules.employee_exits.application import commands, queries
from app.modules.employee_exits.application.dto import EmployeeExitApplicationError
from app.modules.employee_exits.infrastructure.repository import (
    EmployeeExitRepository,
    ExitChecklistRepository,
    ExitDocumentRepository,
)

pytestmark = pytest.mark.unit


def _client_sans_ligne():
    sb = MagicMock()
    chaine = sb.table.return_value
    for methode in ("select", "eq"):
        getattr(chaine, methode).return_value = chaine
    chaine.maybe_single.return_value = chaine
    chaine.execute.return_value = None
    return sb


def test_depot_renvoie_none_quand_le_depart_n_existe_plus():
    repo = EmployeeExitRepository(_client_sans_ligne())
    assert repo.get_by_id("x", "c") is None
    assert repo.get_with_employee("x", "c", "id") is None


def test_lecture_d_un_depart_disparu_donne_404():
    with pytest.raises(EmployeeExitApplicationError) as e:
        queries.get_employee_exit("x", "c", _client_sans_ligne())
    assert e.value.status_code == 404
    assert e.value.detail == "Départ non trouvé"


def test_suppression_d_un_depart_disparu_donne_404():
    with pytest.raises(EmployeeExitApplicationError) as e:
        commands.delete_employee_exit("x", "c", _client_sans_ligne())
    assert e.value.status_code == 404
