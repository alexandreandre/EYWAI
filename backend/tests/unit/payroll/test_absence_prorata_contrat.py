"""Absence non rémunérée d'un contrat > 35 h : retenue au prorata du contrat.

Le cabinet (Quadra) retire chaque heure d'absence 35/39 au taux de base et
4/39 sur les heures sup structurelles mensualisées, sur les heures
planifiées du jour : Marion Gautheron (Colorplast, juillet 2026), journées
de 8,5 h et 7,5 h → 7,63 + 0,87 et 6,73 + 0,77 ; MBC, journées de 7,8 h →
7,00 + 0,80. La position de l'absence dans la semaine n'entre pas en jeu.
EYWAI retenait 7 h + 0,8 h par jour quelle que soit la journée.
"""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JUILLET = (date(2026, 7, 1), date(2026, 7, 31))


def _calendrier_juillet(absences: dict[str, float], heures_jour: float = 8.5) -> list[dict]:
    cal = []
    jour = date(2026, 7, 1)
    while jour.month == 7:
        if jour.weekday() < 5:
            iso = jour.isoformat()
            abs_h = absences.get(iso, 0.0)
            planifie = 7.5 if iso == "2026-07-09" else heures_jour
            if abs_h < planifie:
                cal.append({"date_complete": iso, "type": "travail_base", "heures": planifie - abs_h})
            if abs_h > 0:
                cal.append({"date_complete": iso, "type": "absence_injustifiee_base", "heures": abs_h})
        jour = date.fromordinal(jour.toordinal() + 1)
    return cal


def _lignes(res, motif: str):
    return [l for l in res["lignes_composants_brut"] if motif in str(l.get("libelle"))]


def test_journees_de_8h30_retenues_au_prorata_35_39():
    ctx = build_test_contexte(salaire_base=2278.11, duree_hebdo=39.0)
    cal = _calendrier_juillet(
        {"2026-07-07": 8.5, "2026-07-08": 8.5, "2026-07-09": 7.5, "2026-07-20": 0.25, "2026-07-23": 0.75}
    )
    res = calculer_salaire_brut(ctx, cal, *JUILLET, [])

    absences = _lignes(res, "Absence injustifiée")
    assert [l["quantite"] for l in absences] == [7.63, 7.63, 6.73, 0.22, 0.67]
    assert absences[0]["taux"] == pytest.approx(13.143, abs=0.001)
    assert absences[0]["perte"] == pytest.approx(100.28, abs=0.01)
    assert absences[2]["perte"] == pytest.approx(88.45, abs=0.01)

    reduction = _lignes(res, "Réduction HS structurelles")
    assert len(reduction) == 1
    # 0,87 + 0,87 + 0,77 + 0,03 + 0,08 : ce que le taux de base ne retient pas.
    assert reduction[0]["quantite"] == pytest.approx(2.62, abs=0.005)
    assert reduction[0]["taux"] == pytest.approx(16.4287, abs=0.001)


def test_journee_de_7h48_donne_7h_plus_0h80_comme_avant():
    # MBC : journées de 7,8 h (39 h sur 5 jours) → 7,00 en base et 0,80 en HS.
    ctx = build_test_contexte(salaire_base=2278.11, duree_hebdo=39.0)
    cal = _calendrier_juillet({"2026-07-07": 7.8}, heures_jour=7.8)
    res = calculer_salaire_brut(ctx, cal, *JUILLET, [])
    absences = _lignes(res, "Absence injustifiée")
    assert [l["quantite"] for l in absences] == [7.0]
    reduction = _lignes(res, "Réduction HS structurelles")
    assert reduction[0]["quantite"] == pytest.approx(0.8, abs=0.005)


def test_contrat_35h_inchange():
    ctx = build_test_contexte(salaire_base=2000.0, duree_hebdo=35.0)
    cal = _calendrier_juillet({"2026-07-07": 7.0}, heures_jour=7.0)
    res = calculer_salaire_brut(ctx, cal, *JUILLET, [])
    absences = _lignes(res, "Absence injustifiée")
    assert [l["quantite"] for l in absences] == [7.0]
    assert _lignes(res, "Réduction HS structurelles") == []


def test_absence_non_remuneree_meme_prorata():
    # Demory, juin 2026 : 8,5 h → 7,63 + 0,87, identique à Quadra.
    ctx = build_test_contexte(salaire_base=2278.11, duree_hebdo=39.0)
    cal = [
        {"date_complete": "2026-07-07", "type": "absence_non_remuneree", "heures": 8.5},
        *[e for e in _calendrier_juillet({"2026-07-07": 8.5}) if e["type"] == "travail_base"],
    ]
    res = calculer_salaire_brut(ctx, cal, *JUILLET, [])
    absences = _lignes(res, "Absence non rémunérée")
    assert [l["quantite"] for l in absences] == [7.63]
    assert _lignes(res, "Réduction HS structurelles")[0]["quantite"] == pytest.approx(0.87, abs=0.005)
