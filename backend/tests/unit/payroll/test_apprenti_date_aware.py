"""Régime apprenti piloté par la date de début d'exécution du contrat.

Un salarié embauché d'abord en droit commun puis passé en apprentissage ne doit
bénéficier du régime apprenti (exonérations, CSG apprenti) qu'à partir de la date
de début d'exécution du contrat d'apprentissage. Avant cette date : cotisations
pleines. La bascule est pilotée par `date_debut_execution` comparée à la période
de paie (`contexte.date_fin_periode`). Sans date renseignée : comportement
historique (statique) inchangé — aucune régression pour les apprentis existants.
"""

from __future__ import annotations

from datetime import date

from tests.unit.payroll.helpers import build_test_contexte


def test_apprenti_avant_date_effet_est_non_apprenti():
    ctx = build_test_contexte(
        type_contrat="Apprentissage",
        specificites_extra={"apprenti_date_effet": "2026-06-01"},
    )
    ctx.date_fin_periode = date(2026, 5, 31)  # bulletin de mai
    assert ctx.is_apprenti is False
    assert ctx.is_alternant is False


def test_apprenti_a_partir_de_la_date_effet():
    ctx = build_test_contexte(
        type_contrat="Apprentissage",
        specificites_extra={"apprenti_date_effet": "2026-06-01"},
    )
    ctx.date_fin_periode = date(2026, 6, 30)  # bulletin de juin
    assert ctx.is_apprenti is True
    assert ctx.is_alternant is True


def test_apprenti_sans_date_effet_reste_apprenti():
    # Comportement historique : pas de date d'effet -> statique (toujours apprenti).
    ctx = build_test_contexte(type_contrat="Apprentissage")
    ctx.date_fin_periode = date(2026, 5, 31)
    assert ctx.is_apprenti is True


def test_apprenti_sans_periode_reste_apprenti():
    # date_fin_periode non renseignée (chemins sans période) -> statique.
    ctx = build_test_contexte(
        type_contrat="Apprentissage",
        specificites_extra={"apprenti_date_effet": "2026-06-01"},
    )
    assert ctx.is_apprenti is True
