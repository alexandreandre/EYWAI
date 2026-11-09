"""R-194 : un arrêt au tournant du mois qui n'est pas resaisi : le mois partirait plein."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.schedules.domain.arret_a_confirmer import (
    fin_d_arret_a_confirmer,
    message_arret_a_confirmer,
)

pytestmark = pytest.mark.unit


def _septembre_en_arret_jusqu_au(jour_fin: int, *, fin_reelle: str | None = None) -> list[dict]:
    jours = []
    for jour in range(1, 31):
        if jour <= jour_fin:
            jours.append(
                {
                    "jour": jour,
                    "type": "arret_maladie",
                    "date_debut_arret_reel": "2026-09-01",
                    "date_fin_arret_reel": fin_reelle or f"2026-09-{jour_fin:02d}",
                }
            )
        else:
            jours.append({"jour": jour, "type": "travail", "heures_prevues": 7})
    return jours


def _octobre_plein() -> list[dict]:
    jours = []
    for jour in range(1, 32):
        if date(2026, 10, jour).weekday() >= 5:
            jours.append({"jour": jour, "type": "weekend", "heures_prevues": 0})
        else:
            jours.append({"jour": jour, "type": "travail", "heures_prevues": 7})
    return jours


def _a_confirmer(precedent, prevus=None, reels=(), absences=()):
    return fin_d_arret_a_confirmer(precedent, prevus or _octobre_plein(), reels, absences, 2026, 10)


def test_arret_repris_qui_finit_au_dernier_jour_est_a_confirmer():
    """Erreur injectée : l'arrêt finit le 30/09, rien en octobre, le mois partirait plein."""
    assert _a_confirmer(_septembre_en_arret_jusqu_au(30)) == date(2026, 9, 30)


def test_arret_qui_court_en_octobre_sans_saisie():
    fin = _a_confirmer(_septembre_en_arret_jusqu_au(30, fin_reelle="2026-10-15"))
    assert fin == date(2026, 10, 15)
    assert "jusqu'au 15/10" in message_arret_a_confirmer(fin, 2026, 10)
    assert "payé plein" in message_arret_a_confirmer(fin, 2026, 10)


def test_arret_fini_avant_le_tournant_ne_se_signale_pas():
    assert _a_confirmer(_septembre_en_arret_jusqu_au(20)) is None


def test_arret_saisi_en_octobre_ne_se_signale_pas():
    octobre = _octobre_plein()
    octobre[0] = {"jour": 1, "type": "arret_maladie", "date_debut_arret_reel": "2026-09-01"}
    assert _a_confirmer(_septembre_en_arret_jusqu_au(30), prevus=octobre) is None


def test_prolongation_posee_par_une_demande_validee():
    absences = [{"type": "arret_maladie", "selected_days": ["2026-10-01", "2026-10-02"]}]
    assert _a_confirmer(_septembre_en_arret_jusqu_au(30), absences=absences) is None


def test_des_heures_faites_le_premier_jour_prouvent_la_reprise():
    reels = [{"jour": 1, "type": "travail", "heures_faites": 7}]
    assert _a_confirmer(_septembre_en_arret_jusqu_au(30), reels=reels) is None


def test_des_heures_ne_rassurent_pas_si_l_arret_court_encore():
    reels = [{"jour": 1, "type": "travail", "heures_faites": 7}]
    assert _a_confirmer(_septembre_en_arret_jusqu_au(30, fin_reelle="2026-10-15"), reels=reels) == date(2026, 10, 15)


def test_janvier_regarde_decembre():
    decembre = [{"jour": 31, "type": "arret_maladie", "date_fin_arret_reel": "2026-12-31"}]
    assert fin_d_arret_a_confirmer(decembre, _octobre_plein(), (), (), 2027, 1) == date(2026, 12, 31)
