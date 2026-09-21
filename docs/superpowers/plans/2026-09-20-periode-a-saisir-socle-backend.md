# Période à saisir pour la paie — pas 1, socle backend : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un seul juge de « ce qui manque pour la paie de M » — l'union du mois civil et de la fenêtre des variables du moteur — consommé par le garde-fou de génération, la revue pré-paie et le tableau de bord, avec les dates manquantes nommées.

**Architecture:** Une fonction pure `periode_a_saisir` (domaine schedules) reçoit la fenêtre déjà résolue, les calendriers des mois couverts et les bornes du contrat, et rend la liste des jours manquants, bloquants (dans la fenêtre) ou informatifs (mois civil hors fenêtre). Un service de chargement (`periode_a_saisir_service`) résout la fenêtre via `resoudre_fenetre_variables`, lit les lignes `employee_schedules` des mois couverts et le contrat. Les trois consommateurs remplacent leur décision `a_saisir` par celle du service ; `compute_row_status` garde les écarts d'heures et accepte la décision en paramètre.

**Tech Stack:** Python 3.12, FastAPI, Supabase (moqué en tests), pytest, ruff. Interpréteur : `backend/.venv/bin/python`.

Spec : `docs/superpowers/specs/2026-09-20-periode-a-saisir-pour-la-paie-design.md`.

## Global Constraints

- Le moteur de bulletin ne change pas.
- La règle « jour prêt » (`is_day_ready_for_payroll`) est réutilisée, jamais réécrite.
- Le 422 garde `{"code": "calendrier_incomplet", "message"}` ; les nouveaux champs (`fenetre`, `jours_manquants`, `jours_informatifs`) sont additifs.
- Aucun commit sans demande explicite d'Alexandre (règle du dépôt) : les tâches n'ont pas d'étape commit ; on lui présente l'ensemble à la fin.
- Deux tests unitaires sont rouges par l'environnement local, pas par le code : `test_app_env_defaut_est_prod`, `test_api_failure_manual_fallback`.
- Tous les tests : `cd backend && .venv/bin/python -m pytest tests/unit -q -p no:warnings`.

---

### Task 1: Le domaine pur `periode_a_saisir`

**Files:**
- Create: `backend/app/modules/schedules/domain/periode_a_saisir.py`
- Test: `backend/tests/unit/schedules/test_periode_a_saisir.py`

**Interfaces:**
- Consumes: `ecart_rules.is_day_ready_for_payroll(planned, actual, *, forfait)`.
- Produces: `JourASaisir(jour, bloquant, motif)`, `PeriodeASaisir(debut, fin, fenetre, mois_civil, manquants)` avec `.bloquants`, `.informatifs`, `.statut`, la fonction `periode_a_saisir(*, annee, mois, fenetre, calendriers, date_entree=None, date_sortie=None, forfait=False)`, et `plages(jours)`, `libelle_plages(jours)`.

- [ ] **Step 1: Écrire les tests (rouges)**

```python
"""La période à saisir pour la paie d'un mois : l'union du mois civil et de la
fenêtre des variables, jugée jour par jour, dans les bornes du contrat."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.schedules.domain.periode_a_saisir import (
    libelle_plages,
    periode_a_saisir,
    plages,
)

pytestmark = pytest.mark.unit

FENETRE_JUILLET = (date(2026, 6, 22), date(2026, 7, 26))  # Colorplast : S26–S30


def _mois(annee: int, mois: int, *, reel_jusqu_au: int | None, heures: float = 8.0):
    """Prévu complet (travail en semaine, repos le week-end) ; réel jusqu'au jour donné."""
    import calendar

    prevu, reel = [], []
    for jour in range(1, calendar.monthrange(annee, mois)[1] + 1):
        d = date(annee, mois, jour)
        if d.weekday() >= 5:
            prevu.append({"jour": jour, "type": "repos", "heures_prevues": 0.0})
            continue
        prevu.append({"jour": jour, "type": "travail", "heures_prevues": heures})
        if reel_jusqu_au is not None and jour <= reel_jusqu_au:
            reel.append({"jour": jour, "type": "travail", "heures_faites": heures})
    return prevu, reel


def test_michel_juillet_2026_bloque_sur_juin_et_informe_sur_la_fin_de_juillet():
    """État du test au 20/09 : juin sans réel, juillet saisi du 1er au 24."""
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={(2026, 6): _mois(2026, 6, reel_jusqu_au=None), (2026, 7): _mois(2026, 7, reel_jusqu_au=24)},
        date_entree=date(2020, 1, 15),
    )

    assert (periode.debut, periode.fin) == (date(2026, 6, 22), date(2026, 7, 31))
    assert periode.statut == "a_saisir"
    assert [j.jour.isoformat() for j in periode.bloquants] == [
        "2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25", "2026-06-26",
        "2026-06-29", "2026-06-30",
    ]
    assert [j.jour.day for j in periode.informatifs] == [27, 28, 29, 30, 31]
    assert {j.motif for j in periode.manquants} == {"prevu_sans_reel"}


def test_une_fois_juin_saisi_juillet_est_saisi_avec_cinq_informatifs():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={(2026, 6): _mois(2026, 6, reel_jusqu_au=30), (2026, 7): _mois(2026, 7, reel_jusqu_au=24)},
    )

    assert periode.statut == "saisi"
    assert len(periode.informatifs) == 5


def test_rien_a_saisir_avant_l_embauche_ni_apres_la_sortie():
    calendriers = {(2026, 6): _mois(2026, 6, reel_jusqu_au=None), (2026, 7): _mois(2026, 7, reel_jusqu_au=None)}

    entrant = periode_a_saisir(annee=2026, mois=7, fenetre=FENETRE_JUILLET, calendriers=calendriers, date_entree=date(2026, 7, 6))
    sortant = periode_a_saisir(annee=2026, mois=7, fenetre=FENETRE_JUILLET, calendriers=calendriers, date_sortie=date(2026, 7, 15))

    assert min(j.jour for j in entrant.manquants) == date(2026, 7, 6)
    assert max(j.jour for j in sortant.manquants) == date(2026, 7, 15)


def test_un_mois_sans_planning_attend_ses_jours_ouvres_pas_le_week_end():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={(2026, 7): _mois(2026, 7, reel_jusqu_au=31)},  # pas de ligne pour juin
    )

    juin = [j for j in periode.manquants if j.jour.month == 6]
    assert [j.jour.day for j in juin] == [22, 23, 24, 25, 26, 29, 30]
    assert {j.motif for j in juin} == {"planning_absent"}
    assert all(j.bloquant for j in juin)


def test_un_forfait_jour_est_juge_sur_le_mois_civil_seul():
    prevu = [{"jour": j, "type": "travail", "heures_prevues": 1} for j in range(1, 32)]
    reel = [{"jour": j, "heures_faites": 1} for j in range(1, 32)]

    periode = periode_a_saisir(
        annee=2026, mois=7, fenetre=FENETRE_JUILLET, calendriers={(2026, 7): (prevu, reel)}, forfait=True
    )

    assert periode.fenetre == (date(2026, 7, 1), date(2026, 7, 31))
    assert periode.statut == "saisi" and not periode.manquants


def test_en_mode_mois_calendaire_il_n_y_a_pas_d_informatif():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=(date(2026, 7, 1), date(2026, 7, 31)),
        calendriers={(2026, 7): _mois(2026, 7, reel_jusqu_au=24)},
    )

    assert not periode.informatifs
    assert [j.jour.day for j in periode.bloquants] == [27, 28, 29, 30, 31]


def test_une_fin_avancee_rend_la_derniere_semaine_informative():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=(date(2026, 6, 22), date(2026, 7, 19)),
        calendriers={(2026, 6): _mois(2026, 6, reel_jusqu_au=30), (2026, 7): _mois(2026, 7, reel_jusqu_au=17)},
    )

    assert periode.statut == "saisi"
    assert [j.jour.day for j in periode.informatifs] == [20, 21, 22, 23, 24, 27, 28, 29, 30, 31]


def test_les_motifs_distinguent_prevu_sans_heures_et_reel_a_zero():
    prevu = [
        {"jour": 1, "type": "travail", "heures_prevues": None},
        {"jour": 2, "type": "travail", "heures_prevues": 8.0},
    ]
    reel = [{"jour": 2, "type": "travail", "heures_faites": 0.0}]

    periode = periode_a_saisir(
        annee=2026, mois=7, fenetre=(date(2026, 7, 1), date(2026, 7, 2)),
        calendriers={(2026, 7): (prevu, reel)}, date_sortie=date(2026, 7, 2),
    )

    assert [(j.jour.day, j.motif) for j in periode.manquants] == [(1, "prevu_sans_heures"), (2, "reel_a_zero")]


def test_les_plages_regroupent_les_jours_consecutifs():
    jours = [date(2026, 6, 22), date(2026, 6, 23), date(2026, 6, 24), date(2026, 6, 26), date(2026, 7, 1)]

    assert plages(jours) == [
        (date(2026, 6, 22), date(2026, 6, 24)),
        (date(2026, 6, 26), date(2026, 6, 26)),
        (date(2026, 7, 1), date(2026, 7, 1)),
    ]
    assert libelle_plages(jours) == "22/06–24/06, 26/06, 01/07"
```

- [ ] **Step 2: Vérifier le rouge**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/schedules/test_periode_a_saisir.py -q -p no:warnings`
Expected: `ModuleNotFoundError: app.modules.schedules.domain.periode_a_saisir`.

- [ ] **Step 3: Écrire le module**

```python
"""La période à saisir pour la paie d'un mois — règles pures.

Le bulletin porte le mois civil ; les heures (heures sup, paniers) suivent la
fenêtre des variables (`shared.domain.periode_variables`). Le moteur lit
l'union des deux (`payslip_run_heures.creer_calendrier_etendu`). Le contrôle
amont doit juger la même union : sinon il bloque des jours que le moteur ne
lit pas (27–31/07 chez Colorplast, juillet 2026) et se tait sur ceux qu'il lit
(22–30/06). Constat du 20/09/2026, dossier Michel BUGNY.

Module pur : l'appelant fournit la fenêtre, les calendriers et le contrat.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable, Literal, Mapping

from app.modules.schedules.domain.ecart_rules import is_day_ready_for_payroll

Motif = Literal["planning_absent", "prevu_sans_reel", "prevu_sans_heures", "reel_a_zero"]
#: (année, mois) → (calendrier prévu, calendrier réel) tels que stockés.
Calendriers = Mapping[tuple[int, int], tuple[list[dict[str, Any]], list[dict[str, Any]]]]


@dataclass(frozen=True)
class JourASaisir:
    jour: date
    #: Dans la fenêtre des variables : le moteur lira ce jour pour les heures.
    bloquant: bool
    motif: Motif


@dataclass(frozen=True)
class PeriodeASaisir:
    debut: date
    fin: date
    fenetre: tuple[date, date]
    mois_civil: tuple[date, date]
    manquants: tuple[JourASaisir, ...]
    #: D'où vient la fenêtre : « regle » (société) ou « manuel » (surcharge du mois).
    origine: str = "regle"

    @property
    def bloquants(self) -> tuple[JourASaisir, ...]:
        return tuple(j for j in self.manquants if j.bloquant)

    @property
    def informatifs(self) -> tuple[JourASaisir, ...]:
        return tuple(j for j in self.manquants if not j.bloquant)

    @property
    def statut(self) -> str:
        """`a_saisir` dès qu'un jour de la fenêtre manque, `saisi` sinon."""
        return "a_saisir" if self.bloquants else "saisi"


def _motif(planned: dict[str, Any] | None, actual: dict[str, Any] | None) -> Motif:
    """Pourquoi un jour n'est pas prêt — la décision, elle, reste à `is_day_ready_for_payroll`."""
    if not planned:
        return "planning_absent"
    if planned.get("heures_prevues") is None:
        return "prevu_sans_heures"
    if not actual or actual.get("heures_faites") is None:
        return "prevu_sans_reel"
    return "reel_a_zero"


def _par_jour(entrees: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for entree in entrees:
        try:
            out[int(entree["jour"])] = entree
        except (KeyError, TypeError, ValueError):
            continue
    return out


def periode_a_saisir(
    *,
    annee: int,
    mois: int,
    fenetre: tuple[date, date],
    calendriers: Calendriers,
    date_entree: date | None = None,
    date_sortie: date | None = None,
    forfait: bool = False,
    origine: str = "regle",
) -> PeriodeASaisir:
    """Les jours manquants sur l'union du mois civil et de la fenêtre des variables.

    - Un forfait jour est jugé sur le mois civil seul : présence en jours, pas
      d'heures, la fenêtre des variables ne le concerne pas.
    - Rien n'est attendu avant l'entrée ni après la sortie, comme le moteur qui
      écarte tout événement hors contrat.
    - Un mois sans ligne de planning attend ses jours ouvrés (lundi à vendredi),
      pas le week-end.
    """
    mois_civil = (date(annee, mois, 1), date(annee, mois, calendar.monthrange(annee, mois)[1]))
    if forfait:
        fenetre = mois_civil
    debut, fin = min(mois_civil[0], fenetre[0]), max(mois_civil[1], fenetre[1])
    par_mois = {cle: (_par_jour(prevu), _par_jour(reel)) for cle, (prevu, reel) in calendriers.items()}

    manquants: list[JourASaisir] = []
    jour = debut
    while jour <= fin:
        hors_contrat = (date_entree is not None and jour < date_entree) or (
            date_sortie is not None and jour > date_sortie
        )
        if not hors_contrat:
            dans_fenetre = fenetre[0] <= jour <= fenetre[1]
            planning = par_mois.get((jour.year, jour.month))
            if planning is None:
                if jour.weekday() < 5:
                    manquants.append(JourASaisir(jour, dans_fenetre, "planning_absent"))
            else:
                planned, actual = planning[0].get(jour.day), planning[1].get(jour.day)
                if not is_day_ready_for_payroll(planned, actual, forfait=forfait):
                    manquants.append(JourASaisir(jour, dans_fenetre, _motif(planned, actual)))
        jour += timedelta(days=1)
    return PeriodeASaisir(debut, fin, fenetre, mois_civil, tuple(manquants), origine)


def plages(jours: Iterable[date]) -> list[tuple[date, date]]:
    """Regroupe des dates triées en plages de jours consécutifs."""
    groupes: list[tuple[date, date]] = []
    for jour in sorted(jours):
        if groupes and jour == groupes[-1][1] + timedelta(days=1):
            groupes[-1] = (groupes[-1][0], jour)
        else:
            groupes.append((jour, jour))
    return groupes


def libelle_plages(jours: Iterable[date]) -> str:
    """« 22/06–26/06, 29/06–30/06 » — pour un message qui nomme ce qui manque."""
    return ", ".join(
        f"{a:%d/%m}" if a == b else f"{a:%d/%m}–{b:%d/%m}" for a, b in plages(jours)
    )


__all__ = ["JourASaisir", "PeriodeASaisir", "libelle_plages", "periode_a_saisir", "plages"]
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/schedules/test_periode_a_saisir.py -q -p no:warnings && .venv/bin/ruff check app/modules/schedules/domain/periode_a_saisir.py tests/unit/schedules/test_periode_a_saisir.py`
Expected: `9 passed`, `All checks passed!`.

---

### Task 2: `compute_row_status` accepte la décision `a_saisir`

**Files:**
- Modify: `backend/app/modules/schedules/domain/ecart_rules.py:106-130`
- Test: `backend/tests/unit/schedules/test_ecart_rules.py`

**Interfaces:**
- Produces: `compute_row_status(planned_days, actual_days, year, month, forfait, *, a_saisir: bool | None = None)` — `a_saisir` fourni ⇒ il remplace `compute_month_completion` ; absent ⇒ comportement inchangé (autres appelants, tests existants).

- [ ] **Step 1: Test rouge** (à ajouter en fin de `test_ecart_rules.py`)

```python
def test_compute_row_status_prend_la_decision_a_saisir_quand_on_la_lui_donne():
    """La complétude vient désormais de la période à saisir (mois civil ∪ fenêtre) ;
    la fonction garde les écarts d'heures."""
    from app.modules.schedules.domain.ecart_rules import compute_row_status

    planned = [{"jour": 1, "type": "travail", "heures_prevues": 7.0}]
    actual = [{"jour": 1, "type": "travail", "heures_faites": 7.0}]

    # Mois civil incomplet (30 autres jours sans planning) mais décision fournie : saisi.
    assert compute_row_status(planned, actual, 2026, 7, False, a_saisir=False) == "saisi"
    # Décision fournie : à saisir, même si le mois civil est plein.
    assert compute_row_status(planned, actual, 2026, 7, False, a_saisir=True) == "a_saisir"
    # Sans décision : règle historique sur le mois civil.
    assert compute_row_status(planned, actual, 2026, 7, False) == "a_saisir"
```

- [ ] **Step 2: Vérifier le rouge**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/schedules/test_ecart_rules.py -q -p no:warnings -k a_saisir_quand`
Expected: `TypeError: compute_row_status() got an unexpected keyword argument 'a_saisir'`.

- [ ] **Step 3: Implémenter**

Remplacer la signature et le début de `compute_row_status` :

```python
def compute_row_status(
    planned_days: List[Dict[str, Any]],
    actual_days: List[Dict[str, Any]],
    year: int,
    month: int,
    forfait: bool,
    *,
    a_saisir: bool | None = None,
) -> EmployeeRowStatus:
    """Statut d'une ligne : `a_saisir` | `saisi` | `saisi_avec_ecart`.

    `a_saisir` fourni : la décision de complétude vient de la période à saisir
    (`domain.periode_a_saisir`, mois civil ∪ fenêtre des variables). Absent :
    règle historique sur le mois civil seul.
    """
    if a_saisir is None:
        a_saisir = (
            compute_month_completion(planned_days, actual_days, year, month, forfait=forfait)
            == "a_saisir"
        )
    if a_saisir:
        return "a_saisir"
```

Le reste de la fonction (écarts) est inchangé.

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/schedules/test_ecart_rules.py -q -p no:warnings`
Expected: tous verts.

---

### Task 3: Le service de chargement `periode_a_saisir_service`

**Files:**
- Create: `backend/app/modules/schedules/application/periode_a_saisir_service.py`
- Test: `backend/tests/unit/schedules/test_periode_a_saisir_service.py`

**Interfaces:**
- Consumes: `periode_variables_service.resoudre_fenetre_variables(company_id, annee, mois)` → `FenetreVariables(debut, fin, origine)` ; `schedule_repository.list_schedules_for_employees(ids, year, month)` → `{employee_id: row}` ; `ecart_rules.parse_iso_date` ; `employment_rules.is_forfait_jour(statut, explicit)`.
- Produces: `charger_periodes_a_saisir(company_id, employees, annee, mois) -> dict[str, PeriodeASaisir]`, `charger_periode_a_saisir(company_id, employee, annee, mois) -> PeriodeASaisir`, `resume_api(periode) -> dict` (`fenetre`, `jours_manquants`, `jours_informatifs`).

- [ ] **Step 1: Tests rouges**

```python
"""Le service charge la fenêtre du moteur, les plannings des mois couverts et le
contrat, puis délègue au domaine. Supabase est moqué : on vérifie ce qu'il lit."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.shared.domain.periode_variables import FenetreVariables

pytestmark = pytest.mark.unit

SERVICE = "app.modules.schedules.application.periode_a_saisir_service"
FENETRE_JUILLET = FenetreVariables(debut=date(2026, 6, 22), fin=date(2026, 7, 26), origine="regle")


def _ligne(prevu, reel):
    return {"planned_calendar": {"calendrier_prevu": prevu}, "actual_hours": {"calendrier_reel": reel}}


def _juillet_saisi_jusqu_au_24():
    prevu = [{"jour": j, "type": "travail" if date(2026, 7, j).weekday() < 5 else "repos", "heures_prevues": 8.0 if date(2026, 7, j).weekday() < 5 else 0.0} for j in range(1, 32)]
    reel = [{"jour": j, "heures_faites": 8.0} for j in range(1, 25) if date(2026, 7, j).weekday() < 5]
    return _ligne(prevu, reel)


@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.resoudre_fenetre_variables", return_value=FENETRE_JUILLET)
def test_lit_les_deux_mois_couverts_par_l_union(mock_fenetre, mock_repo):
    from app.modules.schedules.application.periode_a_saisir_service import charger_periodes_a_saisir

    mock_repo.list_schedules_for_employees.side_effect = lambda ids, y, m: (
        {"e1": _juillet_saisi_jusqu_au_24()} if (y, m) == (2026, 7) else {}
    )
    employes = [{"id": "e1", "statut": "Non-Cadre", "is_forfait_jour": False, "hire_date": "2020-01-15"}]

    periodes = charger_periodes_a_saisir("c1", employes, 2026, 7)

    mois_lus = sorted((c.args[1], c.args[2]) for c in mock_repo.list_schedules_for_employees.call_args_list)
    assert mois_lus == [(2026, 6), (2026, 7)]
    mock_fenetre.assert_called_once_with("c1", 2026, 7)
    periode = periodes["e1"]
    assert periode.statut == "a_saisir"
    assert [j.jour.isoformat() for j in periode.bloquants][:2] == ["2026-06-22", "2026-06-23"]
    assert [j.jour.day for j in periode.informatifs] == [27, 28, 29, 30, 31]


@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.resoudre_fenetre_variables", return_value=FENETRE_JUILLET)
def test_les_bornes_du_contrat_viennent_de_la_fiche(mock_fenetre, mock_repo):
    from app.modules.schedules.application.periode_a_saisir_service import charger_periode_a_saisir

    mock_repo.list_schedules_for_employees.return_value = {}
    employe = {"id": "e1", "statut": "Non-Cadre", "hire_date": "2026-07-06", "exit_last_working_day": "2026-07-15"}

    periode = charger_periode_a_saisir("c1", employe, 2026, 7)

    jours = [j.jour for j in periode.manquants]
    assert min(jours) == date(2026, 7, 6) and max(jours) == date(2026, 7, 15)


@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.resoudre_fenetre_variables", return_value=FENETRE_JUILLET)
def test_resume_api_expose_fenetre_et_dates(mock_fenetre, mock_repo):
    from app.modules.schedules.application.periode_a_saisir_service import (
        charger_periode_a_saisir,
        resume_api,
    )

    mock_repo.list_schedules_for_employees.side_effect = lambda ids, y, m: (
        {"e1": _juillet_saisi_jusqu_au_24()} if (y, m) == (2026, 7) else {}
    )

    resume = resume_api(charger_periode_a_saisir("c1", {"id": "e1", "statut": "Non-Cadre"}, 2026, 7))

    assert resume["fenetre"] == {"debut": "2026-06-22", "fin": "2026-07-26", "semaines": [26, 27, 28, 29, 30], "origine": "regle"}
    assert resume["jours_manquants"][:2] == ["2026-06-22", "2026-06-23"]
    assert resume["jours_informatifs"] == ["2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31"]
```

- [ ] **Step 2: Vérifier le rouge**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/schedules/test_periode_a_saisir_service.py -q -p no:warnings`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Écrire le service**

```python
"""Charge ce qu'il faut pour juger la période à saisir d'un mois.

La fenêtre vient du même endroit que pour le moteur
(`periode_variables_service.resoudre_fenetre_variables`) ; les plannings des
mois couverts par l'union sont lus en une requête par mois ; le contrat borne
la période. Le jugement lui-même est dans `domain.periode_a_saisir`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.payroll.application.periode_variables_service import (
    resoudre_fenetre_variables,
)
from app.modules.schedules.domain.ecart_rules import parse_iso_date
from app.modules.schedules.domain.periode_a_saisir import PeriodeASaisir, periode_a_saisir
from app.modules.schedules.infrastructure.repository import schedule_repository
from app.shared.domain.employment_rules import is_forfait_jour
from app.shared.domain.periode_variables import bornes_mois_civil, semaines_iso


def _mois_couverts(debut: date, fin: date) -> list[tuple[int, int]]:
    mois: list[tuple[int, int]] = []
    annee, m = debut.year, debut.month
    while (annee, m) <= (fin.year, fin.month):
        mois.append((annee, m))
        annee, m = (annee + 1, 1) if m == 12 else (annee, m + 1)
    return mois


def _bornes_contrat(employee: dict[str, Any]) -> tuple[date | None, date | None]:
    """Entrée : `hire_date`. Sortie : dernier jour travaillé de la sortie en cours,
    sinon la fin de contrat — la résolution qu'utilise déjà le STC."""
    entree = parse_iso_date(employee.get("hire_date"))
    sortie = parse_iso_date(
        employee.get("exit_last_working_day") or employee.get("contract_end_date")
    )
    return entree, sortie


def _calendriers(ligne: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    if ligne is None:
        return None
    prevu = (ligne.get("planned_calendar") or {}).get("calendrier_prevu") or []
    reel = (ligne.get("actual_hours") or {}).get("calendrier_reel") or []
    return list(prevu), list(reel)


def charger_periodes_a_saisir(
    company_id: str,
    employees: list[dict[str, Any]],
    annee: int,
    mois: int,
) -> dict[str, PeriodeASaisir]:
    """La période à saisir de chaque salarié, en une lecture par mois couvert."""
    fenetre = resoudre_fenetre_variables(str(company_id), annee, mois)
    debut_mois, fin_mois = bornes_mois_civil(annee, mois)
    ids = [str(e["id"]) for e in employees if e.get("id")]
    lignes = {
        cle: schedule_repository.list_schedules_for_employees(ids, cle[0], cle[1])
        for cle in _mois_couverts(min(debut_mois, fenetre.debut), max(fin_mois, fenetre.fin))
    }
    resultat: dict[str, PeriodeASaisir] = {}
    for employee in employees:
        eid = str(employee.get("id") or "")
        if not eid:
            continue
        calendriers = {}
        for cle, par_salarie in lignes.items():
            cal = _calendriers(par_salarie.get(eid))
            if cal is not None:
                calendriers[cle] = cal
        entree, sortie = _bornes_contrat(employee)
        resultat[eid] = periode_a_saisir(
            annee=annee,
            mois=mois,
            fenetre=(fenetre.debut, fenetre.fin),
            calendriers=calendriers,
            date_entree=entree,
            date_sortie=sortie,
            forfait=is_forfait_jour(employee.get("statut"), employee.get("is_forfait_jour")),
            origine=fenetre.origine,
        )
    return resultat


def charger_periode_a_saisir(
    company_id: str, employee: dict[str, Any], annee: int, mois: int
) -> PeriodeASaisir:
    return charger_periodes_a_saisir(company_id, [employee], annee, mois)[str(employee["id"])]


def resume_api(periode: PeriodeASaisir) -> dict[str, Any]:
    """Les champs additifs des réponses (422, avertissements, anomalies)."""
    debut, fin = periode.fenetre
    return {
        "fenetre": {
            "debut": debut.isoformat(),
            "fin": fin.isoformat(),
            "semaines": semaines_iso(debut, fin),
            "origine": periode.origine,
        },
        "jours_manquants": [j.jour.isoformat() for j in periode.bloquants],
        "jours_informatifs": [j.jour.isoformat() for j in periode.informatifs],
    }


__all__ = ["charger_periode_a_saisir", "charger_periodes_a_saisir", "resume_api"]
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/schedules/test_periode_a_saisir.py tests/unit/schedules/test_periode_a_saisir_service.py -q -p no:warnings && .venv/bin/ruff check app/modules/schedules`
Expected: `12 passed`, ruff propre.

---

### Task 4: Le garde-fou de génération juge la période à saisir

**Files:**
- Modify: `backend/app/modules/payslips/application/dto.py:40-43`
- Modify: `backend/app/modules/payslips/application/commands.py:100-180` (`_fetch_month_schedule`, `_calendar_row_status`, `_check_calendar_guard`)
- Modify: `backend/app/modules/payslips/api/router.py:110-114`
- Test: `backend/tests/unit/payslips/test_generation_gardes.py`

**Interfaces:**
- Consumes: `charger_periode_a_saisir`, `resume_api`, `libelle_plages`.
- Produces: `PayslipCalendarIncompleteError(message, details)` avec `.details` ; 422 `{"code", "message", "fenetre", "jours_manquants", "jours_informatifs"}` ; avertissements `calendrier_incomplet_force` (forçage) et `jours_hors_fenetre` (informatifs seuls), tous deux avec les mêmes champs additifs.

- [ ] **Step 1: Adapter les doublures des tests existants et écrire les nouveaux (rouges)**

Dans `test_generation_gardes.py`, remplacer la doublure `_fetch_month_schedule` de `_patches` par les deux doublures du service, avec une fenêtre égale au mois civil de mai 2026 (les tests existants gardent leur sens) :

```python
from datetime import date

from app.shared.domain.periode_variables import FenetreVariables

_SERVICE = "app.modules.schedules.application.periode_a_saisir_service"


def _fenetre(debut: date, fin: date) -> FenetreVariables:
    return FenetreVariables(debut=debut, fin=fin, origine="regle")


class TestGardeCalendrierIncomplet:
    def _patches(self, schedule_row, fenetre=None):
        mock_repo_sched = patch(f"{_SERVICE}.schedule_repository")
        mock_fenetre = patch(
            f"{_SERVICE}.resoudre_fenetre_variables",
            return_value=fenetre or _fenetre(date(2026, 5, 1), date(2026, 5, 31)),
        )
        return (
            patch("app.modules.payslips.application.commands._employee_repository"),
            patch("app.modules.payslips.application.commands.employee_statut_reader"),
            patch("app.modules.payslips.application.commands.payslip_generator_provider"),
            _doublure_plannings(mock_repo_sched, schedule_row),
            patch("app.modules.payslips.application.commands._fetch_existing_payslip", return_value=None),
            mock_fenetre,
        )
```

avec, au niveau module :

```python
from contextlib import contextmanager


@contextmanager
def _doublure_plannings(patcher, schedule_row):
    """Le dépôt des plannings rend la même ligne pour tout mois demandé (mois civil = fenêtre)."""
    with patcher as mock_repo:
        mock_repo.list_schedules_for_employees.return_value = (
            {"emp-1": schedule_row} if schedule_row else {}
        )
        yield mock_repo
```

Chaque test existant déballe désormais six doublures : `p_repo, p_reader, p_provider, p_sched, p_valide, p_fenetre = self._patches(...)` et ajoute `p_fenetre` au `with`. Puis les nouveaux tests, dans la même classe :

```python
    def test_juillet_colorplast_bloque_sur_juin_pas_sur_la_fin_de_juillet(self):
        """Fenêtre 22/06 → 26/07 : juin vide bloque, les 27–31/07 n'entrent pas en compte."""
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=7)
        row = _schedule_complet(2026, 7)
        row["actual_hours"]["calendrier_reel"] = [
            d for d in row["actual_hours"]["calendrier_reel"] if d["jour"] <= 24
        ]
        p_repo, p_reader, p_provider, p_sched, p_valide, p_fenetre = self._patches(
            row, fenetre=_fenetre(date(2026, 6, 22), date(2026, 7, 26))
        )
        with p_repo as mock_repo, p_reader as mock_reader, p_provider, p_sched as mock_sched, p_valide, p_fenetre:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            # Juillet saisi jusqu'au 24 ; aucune ligne pour juin.
            mock_sched.list_schedules_for_employees.side_effect = lambda ids, y, m: (
                {"emp-1": row} if (y, m) == (2026, 7) else {}
            )
            with pytest.raises(PayslipCalendarIncompleteError) as exc:
                generate_payslip(cmd)

        assert "22/06–26/06, 29/06–30/06" in str(exc.value)
        assert exc.value.details["jours_manquants"][0] == "2026-06-22"
        # `_schedule_complet` marque aussi les week-ends « travail » : 25 → 31 hors fenêtre.
        assert exc.value.details["jours_informatifs"] == [
            f"2026-07-{j}" for j in range(25, 32)
        ]
        assert exc.value.details["fenetre"]["semaines"] == [26, 27, 28, 29, 30]

    def test_des_jours_hors_fenetre_seuls_ne_bloquent_pas_mais_se_disent(self):
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2026, month=7)
        juillet = _schedule_complet(2026, 7)
        juillet["actual_hours"]["calendrier_reel"] = [
            d for d in juillet["actual_hours"]["calendrier_reel"] if d["jour"] <= 24
        ]
        juin = _schedule_complet(2026, 6)
        mock_result = {"status": "success", "message": "OK", "download_url": "u"}
        p_repo, p_reader, p_provider, p_sched, p_valide, p_fenetre = self._patches(
            juillet, fenetre=_fenetre(date(2026, 6, 22), date(2026, 7, 26))
        )
        with p_repo as mock_repo, p_reader as mock_reader, p_provider as mock_provider, p_sched as mock_sched, p_valide, p_fenetre:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            mock_provider.generate_heures.return_value = mock_result
            mock_sched.list_schedules_for_employees.side_effect = lambda ids, y, m: (
                {"emp-1": juillet if m == 7 else juin}
            )
            result = generate_payslip(cmd)

        mock_provider.generate_heures.assert_called_once()
        codes = [w["code"] for w in result.warnings]
        assert codes == ["jours_hors_fenetre"]
        assert "25/07–31/07" in result.warnings[0]["message"]  # week-ends « travail » dans la fixture

    def test_le_forcage_nomme_les_jours_forces(self):
        cmd = GeneratePayslipInput(
            employee_id="emp-1", year=2026, month=5, force_calendrier_incomplet=True, requested_by="user-rh-1"
        )
        row = _schedule_complet(2026, 5)
        row["actual_hours"]["calendrier_reel"] = row["actual_hours"]["calendrier_reel"][:-1]
        mock_result = {"status": "success", "message": "OK", "download_url": "u"}
        p_repo, p_reader, p_provider, p_sched, p_valide, p_fenetre = self._patches(row)
        with p_repo as mock_repo, p_reader as mock_reader, p_provider as mock_provider, p_sched, p_valide, p_fenetre:
            mock_repo.get_by_id_only.return_value = dict(_COMPLETE_EMPLOYEE)
            mock_reader.get_employee_statut.return_value = "Non-Cadre"
            mock_provider.generate_heures.return_value = mock_result
            result = generate_payslip(cmd)

        warning = next(w for w in result.warnings if w["code"] == "calendrier_incomplet_force")
        assert warning["jours_manquants"] == ["2026-05-31"]
        assert "31/05" in warning["message"]
```

Et dans la classe de la route (`test_route_mappe_en_422_avec_code`), ajouter l'assertion que `detail` porte `jours_manquants` et `fenetre` (le test existant construit déjà un refus ; compléter son `assert` avec `assert "jours_manquants" in body["detail"] and "fenetre" in body["detail"]`).

- [ ] **Step 2: Vérifier le rouge**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/payslips/test_generation_gardes.py -q -p no:warnings`
Expected: les nouveaux tests échouent (`TypeError` sur `PayslipCalendarIncompleteError(message, details)`, `AttributeError: details`, ou refus attendu absent) ; les anciens peuvent échouer tant que `commands.py` lit encore `_fetch_month_schedule`.

- [ ] **Step 3: Implémenter**

`dto.py` :

```python
class PayslipCalendarIncompleteError(Exception):
    """Génération refusée : des jours de la période à saisir manquent (→ 422).

    `details` : `fenetre`, `jours_manquants`, `jours_informatifs` — repris tels
    quels dans le `detail` HTTP, en plus de `code` et `message`.
    """

    code = "calendrier_incomplet"

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details: dict[str, Any] = dict(details or {})
```

(`from typing import Any` déjà importé dans `dto.py` ; sinon l'ajouter.)

`commands.py` : supprimer `_fetch_month_schedule` et `_calendar_row_status` (plus aucun appelant après cette tâche — vérifier par `grep`), puis :

```python
def _check_calendar_guard(
    employee: dict[str, Any], cmd: GeneratePayslipInput
) -> dict[str, Any] | None:
    """Garde « période à saisir incomplète ».

    Juge l'union du mois civil et de la fenêtre des variables — ce que lit le
    moteur — via `charger_periode_a_saisir`. Refuse (422) si un jour de la
    fenêtre manque, sauf `force_calendrier_incomplet` explicite (tracé, warning
    en réponse). Des jours manquants hors fenêtre ne bloquent pas : ils seront
    saisis pour le mois suivant, on le dit.
    """
    from app.modules.schedules.application.periode_a_saisir_service import (
        charger_periode_a_saisir,
        resume_api,
    )
    from app.modules.schedules.domain.periode_a_saisir import libelle_plages

    periode = charger_periode_a_saisir(
        str(employee.get("company_id") or "").strip(), employee, cmd.year, cmd.month
    )
    details = resume_api(periode)
    debut, fin = periode.fenetre
    if periode.statut != "a_saisir":
        if not periode.informatifs:
            return None
        return {
            "code": "jours_hors_fenetre",
            "message": (
                f"{len(periode.informatifs)} jour(s) hors de la fenêtre des variables "
                f"({libelle_plages(j.jour for j in periode.informatifs)}) : ils seront "
                "saisis pour le mois suivant."
            ),
            **details,
        }
    bloquants = [j.jour for j in periode.bloquants]
    message = (
        f"{cmd.month:02d}/{cmd.year} — {len(bloquants)} jour(s) à saisir dans la fenêtre "
        f"des variables ({debut:%d/%m} → {fin:%d/%m}) : {libelle_plages(bloquants)}. "
        "Complétez le planning avant de générer, ou forcez explicitement la génération."
    )
    if not cmd.force_calendrier_incomplet:
        raise PayslipCalendarIncompleteError(message, details)
    logger.warning(
        "[generation] Période %02d/%d incomplète pour l'employé %s (%s) : "
        "génération FORCÉE par %s (%s).",
        cmd.month,
        cmd.year,
        cmd.employee_id,
        libelle_plages(bloquants),
        cmd.requested_by or "inconnu",
        cmd.requested_by_name or "nom inconnu",
    )
    return {
        "code": "calendrier_incomplet_force",
        "message": (
            f"Généré malgré {len(bloquants)} jour(s) non saisis "
            f"({libelle_plages(bloquants)}) — forçage explicite."
        ),
        **details,
    }
```

`router.py` :

```python
    if isinstance(exc, PayslipCalendarIncompleteError):
        raise HTTPException(
            status_code=422,
            detail={
                "code": PayslipCalendarIncompleteError.code,
                "message": str(exc),
                **getattr(exc, "details", {}),
            },
        ) from exc
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/payslips -q -p no:warnings && .venv/bin/ruff check app/modules/payslips tests/unit/payslips`
Expected: tous verts ; `grep -rn "_fetch_month_schedule\|_calendar_row_status" backend/app` ne rend rien.

---

### Task 5: La revue pré-paie juge la même période

**Files:**
- Modify: `backend/app/modules/payroll/schemas/preflight_responses.py:47-65`
- Modify: `backend/app/modules/payroll/application/preflight_anomalies.py:88-200`
- Test: `backend/tests/unit/payroll/test_preflight_anomalies.py`

**Interfaces:**
- Consumes: `charger_periodes_a_saisir`, `resume_api`, `libelle_plages`, `compute_row_status(..., a_saisir=)`.
- Produces: `PreflightAnomaly.jours_manquants: list[str]`, `PreflightAnomaly.fenetre: dict | None` ; message `heures_non_saisies` avec dates et fenêtre.

- [ ] **Step 1: Test rouge**

Ajouter dans `test_preflight_anomalies.py` une doublure du service (mêmes lignes pour tout mois) et un test :

```python
from datetime import date

from app.shared.domain.periode_variables import FenetreVariables

_SERVICE = "app.modules.schedules.application.periode_a_saisir_service"


def _patch_periode(schedules, *, fenetre):
    """Le service lit la fenêtre donnée et retrouve les mêmes lignes pour tout mois."""
    par_emp = {str(r["employee_id"]): r for r in (schedules or [])}
    p_repo = patch(f"{_SERVICE}.schedule_repository")
    p_fenetre = patch(f"{_SERVICE}.resoudre_fenetre_variables", return_value=fenetre)
    return p_repo, p_fenetre, par_emp


class TestPeriodeASaisir:
    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_l_anomalie_nomme_les_jours_de_la_fenetre(self, mock_supabase, mock_res, mock_badge, mock_mod):
        mock_mod.return_value = _default_mod_settings()
        mock_badge.return_value = {}
        mock_res.return_value = []
        planned = _full_june_2026_planned()
        actual = [d for d in _full_june_2026_actual() if d["jour"] <= 19]  # S26 (22–26/06) non saisie
        schedules = [{"employee_id": EMP_ID, "planned_calendar": {"calendrier_prevu": planned}, "actual_hours": {"calendrier_reel": actual}}]
        _configure_supabase(mock_supabase, schedules=schedules)
        # Fenêtre arrêtée au 21/06 (début au 1er pour ne pas dépendre d'une ligne de mai).
        p_repo, p_fenetre, par_emp = _patch_periode(
            schedules, fenetre=FenetreVariables(debut=date(2026, 6, 1), fin=date(2026, 6, 21), origine="regle")
        )
        with p_repo as mock_repo, p_fenetre:
            mock_repo.list_schedules_for_employees.return_value = par_emp
            response = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        non_saisies = [a for a in response.anomalies if a.type == "heures_non_saisies"]
        # Les 22–26/06 et 29–30/06 sont hors fenêtre : informatifs, pas d'anomalie.
        assert non_saisies == []

    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_un_jour_de_la_fenetre_manquant_fait_une_anomalie_datee(self, mock_supabase, mock_res, mock_badge, mock_mod):
        mock_mod.return_value = _default_mod_settings()
        mock_badge.return_value = {}
        mock_res.return_value = []
        planned = _full_june_2026_planned()
        actual = [d for d in _full_june_2026_actual() if d["jour"] != 15]
        schedules = [{"employee_id": EMP_ID, "planned_calendar": {"calendrier_prevu": planned}, "actual_hours": {"calendrier_reel": actual}}]
        _configure_supabase(mock_supabase, schedules=schedules)
        p_repo, p_fenetre, par_emp = _patch_periode(
            schedules, fenetre=FenetreVariables(debut=date(2026, 6, 1), fin=date(2026, 6, 30), origine="regle")
        )
        with p_repo as mock_repo, p_fenetre:
            mock_repo.list_schedules_for_employees.return_value = par_emp
            response = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        anomalie = next(a for a in response.anomalies if a.type == "heures_non_saisies")
        assert anomalie.jours_manquants == ["2026-06-15"]
        assert anomalie.fenetre["debut"] == "2026-06-01"
        assert "15/06" in anomalie.message
```

Les tests existants de la classe `TestBuildPreflightAnomalies` doivent aussi entourer leur appel des deux doublures (`_patch_periode(schedules, fenetre=FenetreVariables(date(2026, 6, 1), date(2026, 6, 30), "regle"))`) : mois civil = fenêtre, leur sens ne change pas.

- [ ] **Step 2: Vérifier le rouge**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_preflight_anomalies.py -q -p no:warnings`
Expected: `ValidationError` (champ `jours_manquants` inconnu) ou anomalie sans dates.

- [ ] **Step 3: Implémenter**

`preflight_responses.py`, dans `PreflightAnomaly` après `days_with_pointage_anomalies` :

```python
    #: Jours de la fenêtre des variables sans réel (ISO), pour `heures_non_saisies`.
    jours_manquants: List[str] = Field(default_factory=list)
    #: Fenêtre des variables jugée : {debut, fin, semaines, origine}.
    fenetre: Optional[Dict[str, Any]] = None
```

(`Dict`, `Any` : compléter l'import `typing` si besoin.)

`preflight_anomalies.py` : importer

```python
from app.modules.schedules.application.periode_a_saisir_service import (
    charger_periodes_a_saisir,
    resume_api,
)
from app.modules.schedules.domain.periode_a_saisir import libelle_plages
```

après le chargement de `schedule_by_emp` :

```python
    periodes = charger_periodes_a_saisir(company_id, employees, year, month)
```

et dans la boucle, remplacer l'appel et la construction de l'anomalie :

```python
        periode = periodes.get(eid)
        row_status = compute_row_status(
            planned_days,
            actual_days,
            year,
            month,
            forfait,
            a_saisir=(periode.statut == "a_saisir") if periode is not None else None,
        )

        if row_status == "a_saisir":
            resume = resume_api(periode) if periode is not None else {}
            bloquants = [j.jour for j in periode.bloquants] if periode is not None else []
            debut, fin = periode.fenetre if periode is not None else (None, None)
            anomaly = PreflightAnomaly(
                id=_anomaly_id(eid, "heures_non_saisies"),
                employee_id=eid,
                employee_name=name,
                team_id=team_id,
                type="heures_non_saisies",
                severity="bloquant",
                status="a_traiter",
                heures_prevues=heures_prevues,
                heures_faites=heures_faites,
                ecart=ecart,
                is_forfait_jour=forfait,
                jours_manquants=resume.get("jours_manquants", []),
                fenetre=resume.get("fenetre"),
                message=(
                    f"{len(bloquants)} jour(s) à saisir dans la fenêtre des variables "
                    f"({debut:%d/%m} → {fin:%d/%m}) : {libelle_plages(bloquants)}."
                    if bloquants
                    else "Calendrier du mois incomplet — heures planifiées manquantes."
                ),
            )
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/payroll/test_preflight_anomalies.py -q -p no:warnings && .venv/bin/ruff check app/modules/payroll/application/preflight_anomalies.py app/modules/payroll/schemas/preflight_responses.py`
Expected: tous verts.

---

### Task 6: Le tableau de bord compte `a_saisir` sur la même base

**Files:**
- Modify: `backend/app/modules/dashboard/application/analytics_gestion.py:105-175`
- Test: `backend/tests/unit/dashboard/test_analytics_calendriers_periode.py` (nouveau)

**Interfaces:**
- Consumes: `charger_periodes_a_saisir`, `compute_row_status(..., a_saisir=)`.

- [ ] **Step 1: Test rouge**

```python
"""Le tableau de bord et la génération ne peuvent plus se contredire : même juge."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.shared.domain.periode_variables import FenetreVariables

pytestmark = pytest.mark.unit

MODULE = "app.modules.dashboard.application.analytics_gestion"
SERVICE = "app.modules.schedules.application.periode_a_saisir_service"


def _juillet_saisi_jusqu_au_24():
    prevu = [
        {"jour": j, "type": "travail" if date(2026, 7, j).weekday() < 5 else "repos",
         "heures_prevues": 8.0 if date(2026, 7, j).weekday() < 5 else 0.0}
        for j in range(1, 32)
    ]
    reel = [{"jour": j, "heures_faites": 8.0} for j in range(1, 25) if date(2026, 7, j).weekday() < 5]
    return {"employee_id": "e1", "planned_calendar": {"calendrier_prevu": prevu}, "actual_hours": {"calendrier_reel": reel}}


def _supabase(schedules):
    sb = MagicMock()
    employes = MagicMock()
    employes.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "e1", "statut": "Non-Cadre", "is_forfait_jour": False}]
    )
    plannings = MagicMock()
    plannings.select.return_value.eq.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=schedules
    )
    sb.table.side_effect = lambda name: employes if name == "employees" else plannings
    return sb


@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.resoudre_fenetre_variables")
def test_juillet_saisi_jusqu_au_24_est_saisi_si_la_fenetre_s_arrete_au_26(mock_fenetre, mock_repo):
    from app.modules.dashboard.application.analytics_gestion import _build_calendriers_overview

    ligne = _juillet_saisi_jusqu_au_24()
    mock_fenetre.return_value = FenetreVariables(debut=date(2026, 6, 22), fin=date(2026, 7, 26), origine="regle")
    juin = {"employee_id": "e1", "planned_calendar": {"calendrier_prevu": [
        {"jour": j, "type": "travail" if date(2026, 6, j).weekday() < 5 else "repos", "heures_prevues": 8.0 if date(2026, 6, j).weekday() < 5 else 0.0} for j in range(1, 31)
    ]}, "actual_hours": {"calendrier_reel": [
        {"jour": j, "heures_faites": 8.0} for j in range(1, 31) if date(2026, 6, j).weekday() < 5
    ]}}
    mock_repo.list_schedules_for_employees.side_effect = lambda ids, y, m: {"e1": ligne if m == 7 else juin}

    with patch(f"{MODULE}.supabase", _supabase([ligne])):
        overview = _build_calendriers_overview("c1", 2026, 7)

    assert (overview.saisis, overview.a_saisir) == (1, 0)
```

(Vérifier les noms de champs de `CalendriersAnalytics` dans `app/modules/dashboard/domain/value_objects.py` — `saisis`, `a_saisir` — et adapter l'assertion si le modèle les nomme autrement.)

- [ ] **Step 2: Vérifier le rouge**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/dashboard/test_analytics_calendriers_periode.py -q -p no:warnings`
Expected: `(0, 1)` au lieu de `(1, 0)` — le mois civil incomplet est encore jugé seul.

- [ ] **Step 3: Implémenter**

Dans `_build_calendriers_overview`, après `schedule_by_emp` :

```python
    from app.modules.schedules.application.periode_a_saisir_service import (
        charger_periodes_a_saisir,
    )

    periodes = charger_periodes_a_saisir(company_id, employees, year, month)
```

et dans la boucle :

```python
        periode = periodes.get(eid)
        row_status = compute_row_status(
            planned_days,
            actual_days,
            year,
            month,
            forfait,
            a_saisir=(periode.statut == "a_saisir") if periode is not None else None,
        )
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/dashboard -q -p no:warnings && .venv/bin/ruff check app/modules/dashboard/application/analytics_gestion.py`
Expected: verts.

---

### Task 7: Suite complète, contrôle sur le test, documentation

**Files:**
- Modify: `docs/colorplast-reprise-passation.md` (§5, un paragraphe « garde-fou et fenêtre »)
- Modify: mémoire `lecture-pointages-orientation-et-semaines.md` ou nouvelle mémoire `periode-a-saisir-fenetre.md` (projet : « le contrôle amont juge l'union mois civil ∪ fenêtre, comme le moteur »)

- [ ] **Step 1: Suite unitaire complète**

Run: `cd backend && .venv/bin/python -m pytest tests/unit -q -p no:warnings 2>&1 | tail -3`
Expected: seuls `test_app_env_defaut_est_prod` et `test_api_failure_manual_fallback` rouges (environnement).

- [ ] **Step 2: Contrôle réel, en lecture, sur la base test**

Script jetable dans le scratchpad (pas dans le dépôt) : pour les sept salariés Colorplast, `charger_periodes_a_saisir(SOCIETE, employes, 2026, 7)` et afficher statut, bloquants, informatifs. Attendu au 20/09 (avant saisie de juin) : les cinq (Bugny, Cotte, Espinosa, Fuckar, Gautheron) `a_saisir` avec bloquants 22/06–26/06 et 29/06–30/06 et informatifs 27/07–31/07 ; Demory et Girerd `a_saisir` sur juin seulement (leur juillet est complet). Si le résultat diffère, c'est la règle ou le chargement qu'il faut regarder, pas la base.

- [ ] **Step 3: Documenter**

Passation §5 : trois phrases — ce que le garde-fou juge désormais, le 422 avec dates, ce qu'il reste à faire pour juillet (saisir S26 et S27 en juin). Mémoire : le principe et le piège (« le mois civil n'est pas la période de la paie »).

- [ ] **Step 4: Présenter à Alexandre**

Bilan des tests, liste des fichiers, sortie du contrôle du Step 2. Commit et déploiement uniquement sur sa demande.
