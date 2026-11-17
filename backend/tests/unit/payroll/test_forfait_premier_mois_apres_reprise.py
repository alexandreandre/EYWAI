"""Forfait jours, premier mois après une reprise de paie (B1, 17/11).

La période du forfait d'octobre va du 21/09 au 25/10 quand la société décale sa
période ; l'ancien logiciel a payé septembre, absences comprises. Ces absences
ne sont ni retenues, ni maintenues une seconde fois ; le mois ne compte que les
jours d'après la bascule. La période elle-même ne bouge pas.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.payroll.documents.payslip_run_forfait import (
    absences_hors_reprise,
    debut_apres_la_reprise,
)
from app.modules.payroll.documents.payslip_run_heures import _extraire_arret_pour_maintien
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

DEBUT, FIN = date(2026, 9, 21), date(2026, 10, 25)
FIN_REPRISE = date(2026, 9, 30)


def _ouvres(type_jour: str, jusqu_au: date = FIN, **extra) -> list[dict]:
    jours, d = [], DEBUT
    while d <= jusqu_au:
        if d.weekday() < 5:
            jours.append({"date_complete": d.isoformat(), "type": type_jour, "heures": 1.0, **extra})
        d += timedelta(days=1)
    return jours


def _contexte(fin_de_la_reprise=FIN_REPRISE):
    ctx = build_test_contexte(
        statut="Cadre",
        salaire_base=3608.0,
        date_entree="2020-01-01",
        specificites_extra={"is_forfait_jour": True},
    )
    ctx.fin_de_la_reprise = fin_de_la_reprise
    return ctx


def test_les_absences_du_mois_repris_sortent_du_calendrier():
    periode = [
        {"date_complete": "2026-09-28", "type": "conges_payes"},
        {"date_complete": "2026-09-29", "type": "arret_maladie"},
        {"date_complete": "2026-09-30", "type": "travail_base"},
        {"date_complete": "2026-09-30", "type": "absence_non_remuneree", "is_regularisation_anterieure": True},
        {"date_complete": "2026-10-01", "type": "arret_maladie"},
    ]
    gardes = absences_hors_reprise(periode, FIN_REPRISE)
    assert [(j["date_complete"], j["type"]) for j in gardes] == [
        ("2026-09-30", "travail_base"),
        ("2026-09-30", "absence_non_remuneree"),
        ("2026-10-01", "arret_maladie"),
    ]
    assert absences_hors_reprise(periode, None) == periode


def test_le_maintien_commence_apres_la_bascule():
    assert debut_apres_la_reprise(DEBUT, FIN_REPRISE) == date(2026, 10, 1)
    assert debut_apres_la_reprise(DEBUT, None) == DEBUT
    # Bascule avant la période (société au mois civil) : rien ne change.
    assert debut_apres_la_reprise(date(2026, 10, 1), FIN_REPRISE) == date(2026, 10, 1)


def test_un_arret_a_cheval_n_est_maintenu_qu_apres_la_bascule():
    """Arrêt du 15/09 au 09/10 : seuls les jours d'octobre restent au calendrier,
    et la borne passée au maintien est le 01/10 (relecture : 19 jours d'IJSS au
    lieu de 9 sans elle)."""
    calendrier = absences_hors_reprise(
        _ouvres(
            "arret_maladie",
            jusqu_au=date(2026, 10, 9),
            arret_type="maladie",
            date_debut_arret_reel="2026-09-15",
            date_fin_arret_reel="2026-10-09",
        ),
        FIN_REPRISE,
    )
    assert min(j["date_complete"] for j in calendrier) == "2026-10-01"
    debut = debut_apres_la_reprise(DEBUT, FIN_REPRISE)
    arret = _extraire_arret_pour_maintien(calendrier, _contexte(), debut, FIN)
    assert arret is not None


def test_sans_solde_de_toute_la_periode_d_apres_bascule_ne_laisse_pas_de_brut():
    """Sans solde de septembre au 25/10 : octobre (après la bascule) est
    entièrement absent ; le brut de base tombe à 0 (777,50 € restaient)."""
    ctx = _contexte()
    calendrier = absences_hors_reprise(_ouvres("absence_non_remuneree"), FIN_REPRISE)
    resultat = calculer_salaire_brut_forfait(ctx, calendrier, DEBUT, FIN, [])
    assert resultat["salaire_brut_total"] == pytest.approx(0.0, abs=0.01)


def test_hors_premier_mois_rien_ne_change():
    sans = calculer_salaire_brut_forfait(
        _contexte(None), _ouvres("travail_base"), DEBUT, FIN, []
    )
    assert sans["salaire_brut_total"] == pytest.approx(3608.0, abs=0.01)
