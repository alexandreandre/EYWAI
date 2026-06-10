"""
Scénarios paie bout-en-bout — date d'effet des augmentations.

Timeline salary_history → evolution_salaire_mois → calcul brut (heures).
Reproduit les cas attendus en production sans base de données.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.employees.domain.salary_timeline import construire_evolution_salaire_mois
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _entry(eff: str, ancien: float, nouveau: float) -> dict:
    return {
        "effective_date": eff,
        "ancien_salaire": {"valeur": ancien},
        "nouveau_salaire": {"valeur": nouveau},
    }


def _calendrier_heures(year: int, month: int) -> list:
    import calendar

    last = calendar.monthrange(year, month)[1]
    return [
        {
            "date_complete": date(year, month, d).isoformat(),
            "type": "travail_base",
            "heures": 7.0,
        }
        for d in range(1, last + 1)
        if date(year, month, d).weekday() < 5
    ]


def _calendrier_forfait(year: int, month: int) -> list:
    import calendar

    last = calendar.monthrange(year, month)[1]
    return [
        {"date_complete": date(year, month, d).isoformat(), "type": "travail", "heures": 1.0}
        for d in range(1, last + 1)
        if date(year, month, d).weekday() < 5
    ]


def _inject_evolution(ctx, timeline: list, year: int, month: int, fallback: float):
    evo = construire_evolution_salaire_mois(timeline, year, month, fallback)
    prorata = evo.get("prorata")
    salaire_contrat = (
        float(prorata["montant_mois"])
        if prorata
        else float(evo["salaire_fin_mois"])
    )
    rem = ctx.contrat.setdefault("remuneration", {})
    rem["salaire_de_base"] = {"valeur": salaire_contrat}
    rem["evolution_salaire_mois"] = evo
    return evo, salaire_contrat


def _gain_salaire_base(res: dict) -> float:
    ligne = next(
        (
            l
            for l in res["lignes_composants_brut"]
            if (l.get("libelle") or "").startswith("Salaire de base")
        ),
        None,
    )
    assert ligne is not None
    return float(ligne["gain"])


class TestScenarioProrataMiMois:
    """Augmentation au 09/06 sur bulletin de juin."""

    def test_effet_neuf_juin_prorata_30emes(self):
        timeline = [_entry("2026-06-09", 2600, 2678)]
        ctx = build_test_contexte(salaire_base=2600)
        evo, salaire_contrat = _inject_evolution(ctx, timeline, 2026, 6, 2600)

        attendu = round((2600 * 8 / 30) + (2678 * 22 / 30), 2)
        assert salaire_contrat == pytest.approx(attendu, abs=0.02)
        assert evo["prorata"]["jours_ancien"] == 8
        assert evo["prorata"]["jours_nouveau"] == 22

        res = calculer_salaire_brut(
            ctx, _calendrier_heures(2026, 6), date(2026, 6, 1), date(2026, 6, 30)
        )
        assert _gain_salaire_base(res) == pytest.approx(attendu, abs=0.05)
        assert evo["rappel"]["montant"] == 0.0


class TestScenarioRappelRetroactif:
    """Effet mars, bulletin juin : rappel mars-mai + salaire plein juin."""

    def test_rappel_sur_bulletin_juin(self):
        timeline = [_entry("2026-03-01", 2000, 2200)]
        ctx = build_test_contexte(salaire_base=2200)
        evo, _ = _inject_evolution(ctx, timeline, 2026, 6, 2000)

        assert evo["rappel"]["montant"] == pytest.approx(600.0, abs=0.02)
        assert evo["rappel"]["periode_debut"] == "2026-03-01"
        assert evo["rappel"]["periode_fin"] == "2026-05-31"

        res = calculer_salaire_brut(
            ctx, _calendrier_heures(2026, 6), date(2026, 6, 1), date(2026, 6, 30)
        )
        rappel = [
            l for l in res["lignes_composants_brut"] if "Rappel" in (l.get("libelle") or "")
        ]
        assert len(rappel) == 1
        assert rappel[0]["gain"] == pytest.approx(600.0, abs=0.02)
        assert res["salaire_brut_total"] == pytest.approx(2200.0 + 600.0, abs=0.05)


class TestScenarioEffetPremierDuMois:
    """Effet au 1er du mois : mois entier au nouveau taux, pas de prorata."""

    def test_pas_de_prorata_si_effet_premier_juin(self):
        timeline = [_entry("2026-06-01", 2000, 2500)]
        ctx = build_test_contexte(salaire_base=2500)
        evo, salaire_contrat = _inject_evolution(ctx, timeline, 2026, 6, 2000)

        assert evo["prorata"] is None
        assert salaire_contrat == 2500.0

        res = calculer_salaire_brut(
            ctx, _calendrier_heures(2026, 6), date(2026, 6, 1), date(2026, 6, 30)
        )
        assert _gain_salaire_base(res) == pytest.approx(2500.0, abs=0.05)


class TestScenarioComboEntreeEtAugmentation:
    """Embauche le 15 + augmentation le 20 : prorata salaire puis prorata entrée."""

    def test_entree_quinze_augmentation_vingt(self):
        timeline = [_entry("2026-06-20", 2000, 2200)]
        montant_evolution = round((2000 * 19 / 30) + (2200 * 11 / 30), 2)
        facteur_entree = 16 / 30  # présence du 15 au 30 juin
        attendu = round(montant_evolution * facteur_entree, 2)

        ctx = build_test_contexte(
            salaire_base=montant_evolution,
            date_entree="2026-06-15",
        )
        _inject_evolution(ctx, timeline, 2026, 6, 2000)

        res = calculer_salaire_brut(
            ctx, _calendrier_heures(2026, 6), date(2026, 6, 1), date(2026, 6, 30)
        )
        assert _gain_salaire_base(res) == pytest.approx(attendu, abs=0.05)


class TestScenarioProrataEtRappelCombines:
    """Effet mi-mars + bulletin juin : rappel partiel mars + prorata juin si changement."""

    def test_rappel_mi_mars_et_salaire_plein_juin(self):
        timeline = [_entry("2026-03-10", 2000, 2200)]
        ctx = build_test_contexte(salaire_base=2200)
        evo, _ = _inject_evolution(ctx, timeline, 2026, 6, 2000)

        # Mars : 21/30 × 200 ; avril + mai : 400
        assert evo["rappel"]["montant"] == pytest.approx(200 * 21 / 30 + 400, abs=0.02)
        assert evo["prorata"] is None

        res = calculer_salaire_brut(
            ctx, _calendrier_heures(2026, 6), date(2026, 6, 1), date(2026, 6, 30)
        )
        assert _gain_salaire_base(res) == pytest.approx(2200.0, abs=0.05)
        rappel_gain = sum(
            l["gain"]
            for l in res["lignes_composants_brut"]
            if "Rappel" in (l.get("libelle") or "")
        )
        assert rappel_gain == pytest.approx(evo["rappel"]["montant"], abs=0.05)


class TestScenarioForfaitJour:
    """Cadre forfait : prorata mi-mois et rappel sur le bulletin."""

    def test_forfait_prorata_mi_mois(self):
        timeline = [_entry("2026-06-09", 4000, 4200)]
        attendu = round((4000 * 8 / 30) + (4200 * 22 / 30), 2)
        ctx = build_test_contexte(salaire_base=attendu, statut="Cadre au forfait jour")
        _inject_evolution(ctx, timeline, 2026, 6, 4000)

        res = calculer_salaire_brut_forfait(
            ctx,
            _calendrier_forfait(2026, 6),
            date(2026, 6, 1),
            date(2026, 6, 30),
        )
        ligne_forfait = next(
            l
            for l in res["lignes_composants_brut"]
            if "forfait" in (l.get("libelle") or "").lower()
        )
        assert ligne_forfait["gain"] == pytest.approx(attendu, abs=0.05)

    def test_forfait_avec_rappel(self):
        timeline = [_entry("2026-04-01", 3800, 4000)]
        ctx = build_test_contexte(salaire_base=4000, statut="Cadre au forfait jour")
        evo, _ = _inject_evolution(ctx, timeline, 2026, 6, 3800)

        assert evo["rappel"]["montant"] == pytest.approx(400.0, abs=0.02)  # avril + mai

        res = calculer_salaire_brut_forfait(
            ctx,
            _calendrier_forfait(2026, 6),
            date(2026, 6, 1),
            date(2026, 6, 30),
        )
        rappel = [
            l for l in res["lignes_composants_brut"] if "Rappel" in (l.get("libelle") or "")
        ]
        assert len(rappel) == 1
        assert res["salaire_brut_total"] == pytest.approx(4000.0 + 400.0, abs=0.05)
