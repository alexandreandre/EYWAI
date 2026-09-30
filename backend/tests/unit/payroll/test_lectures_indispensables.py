"""Une lecture indispensable au bulletin est relue, puis arrête le calcul — jamais un bulletin amputé.

Revue du 29/09/2026 : une coupure réseau d'une minute a fait perdre sa prime
d'ancienneté à un salarié (règles de convention non lues), avec un simple
avertissement orange.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.modules.payroll.engine import lectures
from app.modules.payroll.engine.lectures import LectureIndispensable, lire_ou_arreter

pytestmark = pytest.mark.unit

PAYROLL = Path(__file__).resolve().parents[3] / "app" / "modules" / "payroll"


@pytest.fixture(autouse=True)
def _sans_pause(monkeypatch):
    monkeypatch.setattr(lectures.time, "sleep", lambda _s: None)


def _coupure() -> Exception:
    return httpx.ConnectError("connexion interrompue")


def test_une_lecture_reussie_passe_telle_quelle():
    assert lire_ou_arreter(lambda: [1, 2], "X n'a pas pu être lu") == [1, 2]


def test_une_coupure_passagere_est_relue():
    essais = iter([_coupure(), "règles"])

    def lire():
        r = next(essais)
        if isinstance(r, Exception):
            raise r
        return r

    assert lire_ou_arreter(lire, "X n'a pas pu être lu") == "règles"


def test_trois_coupures_arretent_le_calcul_avec_une_phrase_claire():
    appels = []

    def lire():
        appels.append(1)
        raise _coupure()

    with pytest.raises(LectureIndispensable, match="réessayez dans un instant") as err:
        lire_ou_arreter(lire, "Les règles de la convention collective n'ont pas pu être lues")
    assert len(appels) == 3
    assert str(err.value).startswith("Les règles de la convention collective n'ont pas pu être lues")


def test_une_erreur_qui_n_est_pas_reseau_arrete_sans_relire():
    appels = []

    def lire():
        appels.append(1)
        raise RuntimeError("requête refusée")

    with pytest.raises(LectureIndispensable):
        lire_ou_arreter(lire, "X n'a pas pu être lu")
    assert len(appels) == 1


def test_une_convention_sans_regle_n_est_pas_un_echec():
    """Une réponse vide se calcule normalement : seul l'échec de lecture arrête."""
    from app.modules.payroll.engine.baremes_loader import (
        charger_conventions_collectives,
    )

    base = MagicMock()
    base.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
    assert charger_conventions_collectives(base) == {}


def test_une_coupure_passagere_sur_la_convention_garde_ses_regles():
    from app.modules.payroll.engine.baremes_loader import (
        charger_conventions_collectives,
    )

    execute = MagicMock(side_effect=[_coupure(), MagicMock(data=[{"idcc": "9999", "rules": {"x": 1}}])])
    base = MagicMock()
    base.table.return_value.select.return_value.execute = execute
    assert charger_conventions_collectives(base)["idcc_9999"]["x"] == 1


@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs", return_value=[])
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_un_historique_de_salaire_illisible_arrete_le_calcul(mock_repo_cls, _sync, _lire):
    from app.modules.payroll.application.salary_evolution_payroll import (
        prepare_salary_evolution_for_payslip,
    )

    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.get_by_id.return_value = {"id": "e", "salaire_de_base": {"valeur": 2000}}
    repo.get_salary_history.side_effect = _coupure()
    with pytest.raises(LectureIndispensable, match="salaire du salarié"):
        prepare_salary_evolution_for_payslip("e", "c", 2026, 9)
    assert repo.get_salary_history.call_count == 3


def test_la_mutuelle_illisible_est_une_lecture_indispensable():
    from app.modules.payroll.engine.mutuelles import MutuelleIllisible

    assert issubclass(MutuelleIllisible, LectureIndispensable)


@pytest.mark.parametrize(
    "fichier", ["documents/payslip_generator.py", "documents/payslip_generator_forfait.py"]
)
def test_les_generateurs_laissent_passer_la_lecture_ratee_et_repondent_503(fichier):
    """L'évolution de salaire garde son repli pour une erreur de calcul, pas pour une
    lecture ratée ; et la génération répond 503 avec la phrase, pas une erreur 500."""
    source = (PAYROLL / fichier).read_text(encoding="utf-8")
    evo = source.index("salary_evo = prepare_salary_evolution_for_payslip(")
    assert source.index("except LectureIndispensable:", evo) < source.index("except Exception as evo_err", evo)
    fin = source.rindex("    except HTTPException:\n        raise\n")
    assert source.index("except LectureIndispensable as e:", fin) < source.index("except Exception as e:", fin)
    assert "status_code=503" in source[fin:source.index("except Exception as e:", fin)]
