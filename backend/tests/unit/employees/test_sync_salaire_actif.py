"""La synchronisation du salaire actif n'écrit que si le montant change.

À chaque génération, elle réécrivait `{"valeur": 2000}` en `{"valeur": 2000.0}` :
l'empreinte posée sur la fiche lue avant cette écriture ne correspondait plus,
et tout bulletin calculé pour la première fois s'affichait « À recalculer »
(recette du 02/10/2026, trois fois sur trois).
"""

from datetime import date
from unittest.mock import patch

from app.modules.employees.infrastructure.repository import EmployeeRepository


def _repo(salaire, historique):
    repo = EmployeeRepository()
    patch.object(repo, "get_by_id", return_value={"id": "e1", "salaire_de_base": salaire}).start()
    patch.object(repo, "get_salary_history", return_value=historique).start()
    return repo


def test_un_salaire_inchange_n_est_pas_reecrit():
    repo = _repo({"valeur": 2000}, [])
    with patch.object(repo, "update") as ecrire:
        fiche = repo.sync_salaire_actif("e1", "co-1", date(2026, 10, 1))
    ecrire.assert_not_called()
    assert fiche["salaire_de_base"] == {"valeur": 2000}
    patch.stopall()


def test_un_salaire_qui_change_est_ecrit():
    repo = _repo({"valeur": 2000}, [{"date_effet": "2026-10-01", "valeur": 2100.0}])
    with patch(
        "app.modules.employees.infrastructure.repository.salaire_actif_a_date", return_value=2100.0
    ), patch.object(repo, "update", return_value={"id": "e1"}) as ecrire:
        repo.sync_salaire_actif("e1", "co-1", date(2026, 10, 1))
    ecrire.assert_called_once_with("e1", {"salaire_de_base": {"valeur": 2100.0}})
    patch.stopall()
