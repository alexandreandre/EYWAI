"""Ligne absente : maybe_single().execute() rend None (postgrest 2.31), la lecture le dit sans planter.

Même piège que la publication des documents de départ (tournage H.4 du 20/10/2026) :
`.data` était lu sur None. Quand la ligne existe, rien ne change.
"""

from __future__ import annotations

import logging

import pytest

from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit


def test_l_impact_d_une_suppression_d_un_salarie_disparu_est_vide(sans_ligne):
    from app.modules.employees.application import deletion_cleanup

    sans_ligne(deletion_cleanup)
    impact = deletion_cleanup.get_deletion_impact("x", "c")
    assert impact.employee_name == ""


def test_supprimer_les_salaries_d_une_societe_disparue_le_dit(sans_ligne):
    from app.modules.employees.application import commands

    sans_ligne(commands)
    with pytest.raises(LookupError, match="Entreprise non trouvée"):
        next(commands.iter_delete_all_company_employees("x"))


def test_le_resume_d_un_depart_disparu_est_absent_sans_erreur_journalisee(sans_ligne, caplog):
    from app.modules.employees.infrastructure import queries

    sans_ligne(queries)
    with caplog.at_level(logging.ERROR):
        assert queries.fetch_exit_summary_for_employee("x", "c") is None
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
