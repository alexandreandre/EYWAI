"""Filet du moteur : une heure saisie un jour d'arrêt ne crée ni heure travaillée ni heure sup.

Constat du 30/09/2026 : une salariée en arrêt tout septembre gardait des heures
pointées sur ses jours d'arrêt ; le moteur en faisait des heures sup (70,75 h à
50 %) et ne retenait l'arrêt que sur les jours sans heures. Deux chemins les
produisent : l'analyse des horaires (`analyser_horaires_du_mois`) et l'option
société `compensation_semaines`. Neutraliser un seul ne suffit pas.

La garde de génération refuse déjà ce cas ; le filet couvre ce qui ne passe pas
par elle (bac à sable, suivi IJSS, jours hors de la période à saisir). Les heures
des jours en conflit sont écartées une fois, à la source commune des deux
chemins, et une alerte le dit sur le bulletin.

Le générateur tourne ici pour de vrai, jusqu'au bout du bac à sable, sur un
calendrier synthétique ; seules ses lectures en base et le calcul du bulletin
(`run_payslip_generation_heures`) sont doublés.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import httpx
import pytest

from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader

pytestmark = pytest.mark.unit

EMP = "emp-arret"
SOCIETE = "soc-1"
ANNEE, MOIS = 2026, 9
#: Jours ouvrés de l'arrêt pointés à 7 h, et un samedi (prévu « weekend ») de l'arrêt.
JOURS_POINTES = [7, 8, 9, 10, 11, 14, 15, 16, 17]
SAMEDI_D_ARRET = 12
ARRET_VALIDE = {
    "employee_id": EMP,
    "type": "arret_maladie",
    "status": "validated",
    "selected_days": [f"2026-09-{j:02d}" for j in range(1, 31)],
}
#: Le repli noté quand les arrêts n'ont pas pu être lus (`engine/replis.py`).
CODE_REPLI_ARRETS_ILLISIBLES = "repli_arrets_illisibles"
MESSAGE_ATTENDU = (
    "Heures saisies pendant l'arrêt, écartées du calcul : les 7, 8, 9, 10, 11, 12, "
    "14, 15, 16 et 17 septembre (70 h). Effacez-les du calendrier, ou corrigez "
    "l'arrêt si elles ont été travaillées."
)


def _jours(annee: int, mois: int):
    d = date(annee, mois, 1)
    while d.month == mois:
        yield d
        d += timedelta(days=1)


def _prevu(annee: int, mois: int, *, en_arret: bool) -> list[dict]:
    """Planning 39 h (8 h du lundi au jeudi, 7 h le vendredi). En arrêt, les jours
    ouvrés sont retypés `arret_maladie` à 0 h et les week-ends restent `weekend`,
    comme le fait la validation d'un arrêt."""
    prevu = []
    for d in _jours(annee, mois):
        if d.weekday() >= 5:
            prevu.append({"jour": d.day, "type": "weekend", "heures_prevues": 0.0})
        elif en_arret:
            prevu.append(
                {"jour": d.day, "type": "arret_maladie", "heures_prevues": 0.0, "arret_type": "arret_maladie"}
            )
        else:
            prevu.append(
                {"jour": d.day, "type": "travail", "heures_prevues": 8.0 if d.weekday() < 4 else 7.0}
            )
    return prevu


def _reel_d_aout() -> list[dict]:
    return [
        {"jour": e["jour"], "type": "travail", "heures_faites": e["heures_prevues"]}
        for e in _prevu(2026, 8, en_arret=False)
        if e["type"] == "travail"
    ]


def _reel_de_septembre(*, samedi: bool = True) -> list[dict]:
    jours = JOURS_POINTES + ([SAMEDI_D_ARRET] if samedi else [])
    return [{"jour": j, "type": "travail", "heures_faites": 7.0} for j in sorted(jours)]


def _lignes_de_calendrier(reel_septembre: list[dict]) -> list[dict]:
    return [
        {
            "year": 2026, "month": 8, "payroll_events": None,
            "planned_calendar": {"calendrier_prevu": _prevu(2026, 8, en_arret=False)},
            "actual_hours": {"calendrier_reel": _reel_d_aout()},
        },
        {
            "year": 2026, "month": 9, "payroll_events": None,
            "planned_calendar": {"calendrier_prevu": _prevu(2026, 9, en_arret=True)},
            "actual_hours": {"calendrier_reel": reel_septembre},
        },
        {
            "year": 2026, "month": 10, "payroll_events": None,
            "planned_calendar": {"calendrier_prevu": _prevu(2026, 10, en_arret=False)},
            "actual_hours": {"calendrier_reel": []},
        },
    ]


class _Requete:
    def __init__(self, base: _Base, table: str):
        self.base, self.table, self.colonnes = base, table, "*"

    def select(self, colonnes: str = "*", *_a, **_k):
        self.colonnes = colonnes
        return self

    def eq(self, *_a):
        return self

    in_ = gte = lte = limit = order = eq

    def match(self, *_a):
        return self

    def single(self):
        return self

    maybe_single = single

    def execute(self):
        return SimpleNamespace(data=self.base.lire(self.table, self.colonnes))


class _Base:
    """Les lectures du générateur, en mémoire."""

    def __init__(self, reel_septembre: list[dict], *, compensation: bool):
        self.lignes = _lignes_de_calendrier(reel_septembre)
        self.compensation = compensation

    def table(self, nom: str) -> _Requete:
        return _Requete(self, nom)

    def lire(self, table: str, colonnes: str):
        if table == "employees":
            return {
                "id": EMP, "company_id": SOCIETE, "employee_folder_name": "Salarie_Filet",
                "duree_hebdomadaire": 39, "hire_date": "2020-01-06", "statut": "Non-Cadre",
                "first_name": "Octavie", "last_name": "Filet", "contract_type": "CDI",
            }
        if table == "companies":
            return {
                "id": SOCIETE, "siren": "000000000",
                "settings": {"compensation_heures_entre_semaines": self.compensation},
            }
        if table == "employee_schedules":
            return None if colonnes == "cumuls" else self.lignes
        if table in ("monthly_inputs", "expense_reports", "absence_requests"):
            return []
        raise AssertionError(f"lecture inattendue : {table}")


class _Moteur:
    """Ce que les deux chemins ont produit pour septembre."""

    def __init__(self):
        self.analyse: list[dict] = []
        self.compensation = None
        self.apres_compensation: list[dict] | None = None
        self.bulletin: dict = {}


@pytest.fixture
def moteur(monkeypatch) -> _Moteur:
    from app.modules.employee_loans.application import payroll_integration
    from app.modules.modulation.application import reference_resolution
    from app.modules.payroll.application import periode_variables_service
    from app.modules.payroll.documents import payslip_run_heures
    from app.modules.planning.application import shift_payroll_aggregation
    from app.modules.planning.infrastructure.repository import planning_repository
    from app.modules.prime_anciennete_settings.application import (
        queries as prime_queries,
    )
    from app.modules.saisies_avances.infrastructure import queries as avances

    def reseau_interdit(*_a, **_k):
        raise AssertionError("appel réseau pendant un test unitaire")

    monkeypatch.setattr(httpx.Client, "send", reseau_interdit)
    monkeypatch.setattr(planning_repository, "get_company_planning_settings", lambda *_a: {})
    monkeypatch.setattr(reference_resolution, "resolve_effective_weekly_hours_map", lambda *_a, **_k: None)
    monkeypatch.setattr(
        periode_variables_service,
        "resoudre_fenetre_variables",
        lambda *_a, **_k: SimpleNamespace(debut=date(2026, 9, 1), fin=date(2026, 9, 30), origine="test"),
    )
    monkeypatch.setattr(shift_payroll_aggregation, "aggregate_shift_payroll_metrics", lambda *_a, **_k: None)
    monkeypatch.setattr(avances, "get_advances_to_repay", lambda *_a, **_k: [])
    monkeypatch.setattr(payroll_integration, "inject_loan_benefit_in_kind", lambda contrat, *_a: contrat)
    monkeypatch.setattr(prime_queries, "get_prime_anciennete_overrides_for_payslip", lambda *_a: {})
    monkeypatch.setattr(pg, "build_convention_collective_payload", lambda *_a, **_k: {})
    monkeypatch.setattr(pg, "prepare_salary_evolution_for_payslip", lambda *_a, **_k: None)
    monkeypatch.setattr(
        pg,
        "get_jei_settings_raw",
        lambda *_a: SimpleNamespace(jei_enabled=False, date_creation_etablissement=None, taux_exoneration=None),
    )

    etat = _Moteur()
    analyser, compenser = pg.payroll_analyzer_analyser, pg.appliquer_aux_mois

    def analyser_espion(prevu, reel, duree, annee, mois, *a, **k):
        evenements = analyser(prevu, reel, duree, annee, mois, *a, **k)
        if (annee, mois) == (ANNEE, MOIS):
            etat.analyse = [dict(e) for e in evenements]
        return evenements

    def compenser_espion(*a, **k):
        evenements, compensation = compenser(*a, **k)
        etat.compensation = compensation
        etat.apres_compensation = [dict(e) for e in evenements[(ANNEE, MOIS)]]
        return evenements, compensation

    def run_factice(*_a, **_k):
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    monkeypatch.setattr(pg, "payroll_analyzer_analyser", analyser_espion)
    monkeypatch.setattr(pg, "appliquer_aux_mois", compenser_espion)
    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run_factice)
    return etat


def _generer(monkeypatch, *, compensation: bool, reel_septembre=None, arrets=None) -> dict:
    base = _Base(
        _reel_de_septembre() if reel_septembre is None else reel_septembre,
        compensation=compensation,
    )
    monkeypatch.setattr(pg, "supabase", base)
    lecteur = arrets if callable(arrets) else (lambda *_a, **_k: {EMP: [ARRET_VALIDE]})
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lecteur)
    return pg.process_payslip_generation(EMP, ANNEE, MOIS, bac_a_sable=BacASable())


def _heures_sup(evenements: list[dict]) -> float:
    return sum(
        float(e.get("heures") or 0)
        for e in evenements
        if str(e.get("type", "")).startswith(("travail_hs", "travail_hc"))
    )


def _jours_d_arret(evenements: list[dict]) -> list[int]:
    return sorted({int(e["jour"]) for e in evenements if e.get("type") == "arret_maladie"})


JOURS_OUVRES_DE_SEPTEMBRE = [d.day for d in _jours(2026, 9) if d.weekday() < 5]


class TestCheminAnalyseDesHoraires:
    """Sans l'option société : `analyser_horaires_du_mois`."""

    def test_aucune_heure_sup(self, monkeypatch, moteur):
        _generer(monkeypatch, compensation=False)

        assert _heures_sup(moteur.analyse) == 0
        assert moteur.compensation is None

    def test_l_arret_est_retenu_sur_tout_le_mois(self, monkeypatch, moteur):
        _generer(monkeypatch, compensation=False)

        assert _jours_d_arret(moteur.analyse) == JOURS_OUVRES_DE_SEPTEMBRE


class TestCheminCompensationSemaines:
    """Avec l'option société : `compensation_semaines.appliquer_aux_mois`."""

    def test_aucune_heure_sup(self, monkeypatch, moteur):
        _generer(monkeypatch, compensation=True)

        # La semaine du 31 août reste, à écart nul : le 31 est un jour travaillé.
        assert [s.total for s in moteur.compensation.semaines] == [0.0]
        assert (moteur.compensation.net25, moteur.compensation.net50) == (0.0, 0.0)
        assert _heures_sup(moteur.apres_compensation) == 0

    def test_l_arret_est_retenu_sur_tout_le_mois(self, monkeypatch, moteur):
        _generer(monkeypatch, compensation=True)

        assert _jours_d_arret(moteur.apres_compensation) == JOURS_OUVRES_DE_SEPTEMBRE


class TestAlerteSurLeBulletin:
    @pytest.mark.parametrize("compensation", [False, True])
    def test_les_jours_et_les_heures_ecartes_sont_dits(self, monkeypatch, moteur, compensation):
        resultat = _generer(monkeypatch, compensation=compensation)

        alertes = [
            a for a in resultat["payslip_data"]["alertes_baremes"]
            if a.get("code") == "heures_sur_arret_ecartees"
        ]
        assert len(alertes) == 1
        assert alertes[0]["message"] == MESSAGE_ATTENDU
        assert alertes[0]["jours"][0] == {"annee": 2026, "mois": 9, "jour": 7, "heures": 7.0}
        assert MESSAGE_ATTENDU in resultat["warnings"]

    def test_sans_heures_sur_l_arret_ni_alerte_ni_lecture_des_arrets(self, monkeypatch, moteur):
        lectures = []

        def lecteur(*a, **_k):
            lectures.append(a)
            return {EMP: [ARRET_VALIDE]}

        resultat = _generer(monkeypatch, compensation=True, reel_septembre=[], arrets=lecteur)

        assert resultat["payslip_data"]["alertes_baremes"] == []
        assert lectures == []


class TestArretsIllisibles:
    """La lecture des arrêts échoue : le moteur n'invente rien. La règle du type
    prévu s'applique (les jours d'arrêt du planning), le samedi de l'arrêt garde
    ses heures, et le bulletin le dit."""

    def _generer_sans_arrets(self, monkeypatch, compensation: bool) -> dict:
        def en_panne(*_a, **_k):
            raise ConnectionError("base injoignable")

        return _generer(monkeypatch, compensation=compensation, arrets=en_panne)

    @pytest.mark.parametrize("compensation", [False, True])
    def test_les_jours_d_arret_du_planning_sont_ecartes_quand_meme(self, monkeypatch, moteur, compensation):
        self._generer_sans_arrets(monkeypatch, compensation)

        evenements = moteur.apres_compensation if compensation else moteur.analyse
        assert _jours_d_arret(evenements) == JOURS_OUVRES_DE_SEPTEMBRE

    def test_le_bulletin_dit_que_les_arrets_n_ont_pas_ete_lus(self, monkeypatch, moteur):
        resultat = self._generer_sans_arrets(monkeypatch, compensation=True)

        alertes = resultat["payslip_data"]["alertes_baremes"]
        codes = [a.get("code") for a in alertes]
        assert CODE_REPLI_ARRETS_ILLISIBLES in codes
        ecartees = next(a for a in alertes if a.get("code") == "heures_sur_arret_ecartees")
        assert ecartees["message"].startswith(
            "Heures saisies pendant l'arrêt, écartées du calcul : les 7, 8, 9, 10, 11, "
            "14, 15, 16 et 17 septembre (63 h)."
        )
