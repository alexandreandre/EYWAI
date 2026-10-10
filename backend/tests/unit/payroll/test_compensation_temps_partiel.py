"""L'option « compensation des heures entre semaines » ne s'applique pas à un temps partiel.

Enquête du 10/10/2026 : pour un contrat de 14 h, l'analyse produit déjà des
heures complémentaires (10 % puis 25 %) au-delà du contrat ; la compensation ne
remplaçait que les heures supplémentaires et y ajoutait l'écart de la semaine
en heures sup à 25 % (jusqu'à 43 h moins la durée). Les mêmes heures étaient
payées deux fois : +109,47 € de brut au bac à sable sur un cas réel.

Un salarié à temps partiel (durée inférieure à la durée légale, C. trav.
art. L3123-1) garde le décompte normal ; un temps plein avec l'option garde la
compensation telle qu'elle est.

Le générateur tourne pour de vrai sur un calendrier synthétique ; seules ses
lectures en base et le calcul du bulletin sont doublés (harnais du filet
« heures sur arrêt »). On compare ce que le générateur remet au calcul du
bulletin : événements de paie du mois et du mois d'avant, saisies du mois.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader

from .test_filet_heures_sur_arret import EMP, SOCIETE, _Base, moteur  # noqa: F401 — fixture

pytestmark = pytest.mark.unit

#: Heures ajoutées au pointage de septembre : +2 h les 8, 9 et 10, +1 h le 16.
DEPASSEMENTS = {8: 2.0, 9: 2.0, 10: 2.0, 16: 1.0}


def _jours(annee: int, mois: int):
    d = date(annee, mois, 1)
    while d.month == mois:
        yield d
        d += timedelta(days=1)


def _heures_du_jour(d: date, duree: float) -> float:
    if duree >= 39:
        return 8.0 if d.weekday() < 4 else 7.0
    return round(duree / 5, 2)


def _prevu(annee: int, mois: int, duree: float) -> list[dict]:
    return [
        {"jour": d.day, "type": "travail", "heures_prevues": _heures_du_jour(d, duree)}
        if d.weekday() < 5
        else {"jour": d.day, "type": "weekend", "heures_prevues": 0.0}
        for d in _jours(annee, mois)
    ]


def _reel(annee: int, mois: int, duree: float, extra: dict[int, float]) -> list[dict]:
    return [
        {"jour": d.day, "type": "travail", "heures_faites": round(_heures_du_jour(d, duree) + extra.get(d.day, 0.0), 2)}
        for d in _jours(annee, mois)
        if d.weekday() < 5
    ]


class _BaseContrat(_Base):
    def __init__(self, duree: float, *, compensation: bool):
        super().__init__([], compensation=compensation)
        self.duree = duree
        self.lignes = [
            {
                "year": 2026, "month": m, "payroll_events": None,
                "planned_calendar": {"calendrier_prevu": _prevu(2026, m, duree)},
                "actual_hours": {"calendrier_reel": reel},
            }
            for m, reel in (
                (8, _reel(2026, 8, duree, {})),
                (9, _reel(2026, 9, duree, DEPASSEMENTS)),
                (10, []),
            )
        ]

    def lire(self, table: str, colonnes: str):
        if table == "employees":
            fiche = super().lire(table, colonnes)
            return {**fiche, "duree_hebdomadaire": self.duree, "is_temps_partiel": self.duree < 35}
        return super().lire(table, colonnes)


def _entrees_du_bulletin(monkeypatch, duree: float, *, compensation: bool) -> dict:
    """Ce que le générateur remet au calcul du bulletin."""
    from app.modules.payroll.documents import payslip_run_heures

    remis: dict = {}

    def calcul_espion(dossier, annee, mois, *_a, **_k):
        for nom, chemin in (
            ("evenements", dossier / "evenements_paie" / f"{mois:02d}.json"),
            ("evenements_mois_d_avant", dossier / "evenements_paie" / f"{mois - 1:02d}.json"),
            ("saisies", dossier / "saisies" / f"{mois:02d}.json"),
        ):
            remis[nom] = json.loads(chemin.read_text(encoding="utf-8"))
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", calcul_espion)
    monkeypatch.setattr(pg, "supabase", _BaseContrat(duree, compensation=compensation))
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {})
    pg.process_payslip_generation(EMP, 2026, 9, bac_a_sable=BacASable())
    return remis


def _heures(evenements: dict, prefixe: str) -> float:
    return round(
        sum(float(e.get("heures") or 0) for e in evenements["calendrier_analyse"] if str(e.get("type", "")).startswith(prefixe)),
        2,
    )


class TestTempsPartiel:
    def test_avec_l_option_le_bulletin_est_celui_sans_l_option(self, monkeypatch, moteur):  # noqa: F811
        sans = _entrees_du_bulletin(monkeypatch, 14.0, compensation=False)
        avec = _entrees_du_bulletin(monkeypatch, 14.0, compensation=True)

        assert avec == sans
        assert "compensation_semaines" not in avec["saisies"]

    def test_les_heures_au_dela_du_contrat_restent_des_heures_complementaires(self, monkeypatch, moteur):  # noqa: F811
        avec = _entrees_du_bulletin(monkeypatch, 14.0, compensation=True)

        # Semaine du 7/09 : +6 h = 1,4 h à 10 % (1/10 de 14 h) et 4,6 h à 25 % ;
        # semaine du 14/09 : +1 h à 10 %. Aucune heure supplémentaire.
        assert _heures(avec["evenements"], "travail_hc10") == 2.4
        assert _heures(avec["evenements"], "travail_hc25") == 4.6
        assert _heures(avec["evenements"], "travail_hs") == 0.0


class TestTempsPlein:
    def test_l_option_compense_toujours_les_semaines(self, monkeypatch, moteur):  # noqa: F811
        avec = _entrees_du_bulletin(monkeypatch, 39.0, compensation=True)

        resume = avec["saisies"]["compensation_semaines"]
        # Semaine du 7/09 : +6 h = 4 h à 25 % (39 h → 43 h) et 2 h à 50 % ; semaine du 14/09 : +1 h.
        assert (resume["net25"], resume["net50"]) == (5.0, 2.0)
        assert _heures(avec["evenements"], "travail_hs25") == 5.0
        assert _heures(avec["evenements"], "travail_hs50") == 2.0
        assert all(
            e.get("compensation_semaines")
            for e in avec["evenements"]["calendrier_analyse"]
            if str(e.get("type", "")).startswith("travail_hs")
        )


@pytest.mark.parametrize(
    ("duree", "attendu"),
    [(14.0, False), (34.99, False), (35.0, True), (39.0, True), ("39", True), (None, True)],
)
def test_l_option_vaut_pour_un_contrat_a_la_duree_legale_ou_plus(duree, attendu):
    from app.modules.payroll.application.compensation_semaines import s_applique_au_contrat

    assert s_applique_au_contrat(duree) is attendu
