# Arrêts maladie en jours calendaires — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Saisir un arrêt de travail « du … au … » et le décompter en jours calendaires (week-ends/fériés compris) jusqu'à la prévoyance, plus réparation des arrêts existants.

**Architecture:** L'expansion période→jours vit côté serveur (commande de création d'absence) ; la projection au calendrier de paie est déverrouillée pour que les jours non travaillés d'un arrêt deviennent `arret_maladie` ; le moteur maintien/IJSS/prévoyance (déjà calendaire) n'est pas touché. Spec : `docs/superpowers/specs/2026-09-01-arrets-jours-calendaires-design.md`.

**Tech Stack:** FastAPI + Pydantic v2, Supabase (PostgREST), pytest ; React + TS, shadcn Calendar (react-day-picker), date-fns, vitest.

## Global Constraints

- Repo : `/Users/alex/Desktop/EYWAI/EYWAI`, branche `dev-arrets-jours-calendaires` (déjà créée).
- Tests backend : `cd /Users/alex/Desktop/EYWAI/EYWAI/backend && ./venv/bin/python -m pytest <cible> -q`.
- Tests frontend : `cd /Users/alex/Desktop/EYWAI/EYWAI/frontend && npm test -- <fichier>`.
- Code, commentaires et messages de commit en français, dans le style du module (voir fichiers voisins).
- Ne PAS modifier : `maintien_salaire_service.py`, `calcul_absences.py`, `dashboard/application/service.py`, `transport_allowance.py`, la branche « mois non planifié » (insert) de `update_calendar_from_days`.
- Types d'arrêt concernés par le calendaire : `IJSS_ELIGIBLE_TYPES` (= `arret_maladie`, `arret_at`, `arret_maladie_pro`, `arret_maternite`, `arret_paternite`) ; exception : `arret_type == "mi_temps_therapeutique"` reste jour par jour.
- Fin de chaque tâche : commit avec `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Helper partagé `daterange_days`

**Files:**
- Modify: `backend/app/shared/domain/absence_calendar.py`
- Modify: `backend/app/modules/dsn_import/domain/dsn_absence_exit_mapping.py:65-73`
- Test: `backend/tests/unit/absences/test_expansion_calendaire.py` (nouveau)

**Interfaces:**
- Produces: `app.shared.domain.absence_calendar.daterange_days(start: date, end: date) -> list[date]` — tous les jours calendaires bornes incluses ; `end < start` → `[start]` (comportement DSN historique conservé). Consommé par les tâches 3 et 8.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/absences/test_expansion_calendaire.py` :

```python
"""Expansion calendaire des arrêts : helper partagé, schéma API, commande.

Spec : docs/superpowers/specs/2026-09-01-arrets-jours-calendaires-design.md
"""

from datetime import date

from app.shared.domain.absence_calendar import daterange_days


def test_daterange_days_couvre_week_ends_et_bornes():
    # vendredi 14/08/2026 → lundi 17/08/2026 : le week-end est inclus
    jours = daterange_days(date(2026, 8, 14), date(2026, 8, 17))
    assert jours == [
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 16),
        date(2026, 8, 17),
    ]


def test_daterange_days_fin_avant_debut_renvoie_le_debut():
    assert daterange_days(date(2026, 8, 17), date(2026, 8, 14)) == [date(2026, 8, 17)]


def test_import_dsn_reexporte_le_helper_partage():
    from app.modules.dsn_import.domain import dsn_absence_exit_mapping

    assert dsn_absence_exit_mapping.daterange_days is daterange_days
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd /Users/alex/Desktop/EYWAI/EYWAI/backend && ./venv/bin/python -m pytest tests/unit/absences/test_expansion_calendaire.py -q`
Expected: FAIL — `ImportError: cannot import name 'daterange_days'`

- [ ] **Step 3: Implémenter**

Dans `backend/app/shared/domain/absence_calendar.py` : ajouter `from datetime import date, timedelta` sous `from __future__ import annotations`, puis avant `is_absence_day` :

```python
def daterange_days(start: date, end: date) -> list[date]:
    """Tous les jours calendaires de `start` à `end`, bornes incluses.

    Un arrêt de travail est une période calendaire (Cerfa : week-ends et fériés
    compris) : c'est l'expansion de référence pour les arrêts. `end < start`
    renvoie `[start]` — comportement historique de l'import DSN, conservé.
    """
    if end < start:
        return [start]
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days
```

Ajouter `"daterange_days",` à `__all__`.

Dans `dsn_absence_exit_mapping.py` : supprimer la définition locale de `daterange_days` (l.65-73) et ajouter en tête d'imports `from app.shared.domain.absence_calendar import daterange_days` (import au niveau module : les usages internes `:101`/`:140` et tout `from ...dsn_absence_exit_mapping import daterange_days` existant continuent de fonctionner). Vérifier les autres importeurs : `grep -rn "daterange_days" app/ scripts/ tests/ --include='*.py'` — ne rien casser.

- [ ] **Step 4: Vérifier le vert**

Run: `./venv/bin/python -m pytest tests/unit/absences/test_expansion_calendaire.py tests/unit/dsn_import -q`
Expected: PASS (les tests dsn_import existants restent verts)

- [ ] **Step 5: Commit**

```bash
git add backend/app/shared/domain/absence_calendar.py backend/app/modules/dsn_import/domain/dsn_absence_exit_mapping.py backend/tests/unit/absences/test_expansion_calendaire.py
git commit -m "refactor(absences): promouvoir daterange_days en domaine partagé"
```

---

### Task 2: Schéma API — saisie par période

**Files:**
- Modify: `backend/app/modules/absences/schemas/requests.py:50-71`
- Test: `backend/tests/unit/absences/test_expansion_calendaire.py`

**Interfaces:**
- Produces: `AbsenceRequestCreate.date_debut: Optional[date]`, `AbsenceRequestCreate.date_fin: Optional[date]`, `selected_days: List[date] = []` (désormais optionnel). Règles : période complète, `date_fin >= date_debut`, période réservée aux `_ARRETS_TYPES_PRINCIPAUX`, refusée si `arret_type == "mi_temps_therapeutique"`, jamais mélangée à `selected_days`, et « ni jours ni période » refusé.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `test_expansion_calendaire.py` :

```python
import pytest
from pydantic import ValidationError

from app.modules.absences.schemas.requests import AbsenceRequestCreate


def _payload_arret(**overrides):
    payload = {
        "employee_id": "emp-1",
        "type": "arret_maladie",
        "arret_type": "maladie_simple",
    }
    payload.update(overrides)
    return payload


def test_schema_accepte_une_periode_pour_un_arret():
    req = AbsenceRequestCreate(
        **_payload_arret(date_debut=date(2026, 8, 17), date_fin=date(2026, 9, 18))
    )
    assert req.date_debut == date(2026, 8, 17)
    assert req.selected_days == []


def test_schema_refuse_une_periode_incomplete():
    with pytest.raises(ValidationError, match="début ET une date de fin"):
        AbsenceRequestCreate(**_payload_arret(date_debut=date(2026, 8, 17)))


def test_schema_refuse_fin_avant_debut():
    with pytest.raises(ValidationError, match="antérieure"):
        AbsenceRequestCreate(
            **_payload_arret(date_debut=date(2026, 9, 18), date_fin=date(2026, 8, 17))
        )


def test_schema_refuse_periode_et_jours_melanges():
    with pytest.raises(ValidationError, match="pas les deux"):
        AbsenceRequestCreate(
            **_payload_arret(
                date_debut=date(2026, 8, 17),
                date_fin=date(2026, 8, 21),
                selected_days=[date(2026, 8, 17)],
            )
        )


def test_schema_refuse_periode_pour_un_conge_paye():
    with pytest.raises(ValidationError, match="réservée aux arrêts"):
        AbsenceRequestCreate(
            employee_id="emp-1",
            type="conge_paye",
            date_debut=date(2026, 8, 17),
            date_fin=date(2026, 8, 21),
        )


def test_schema_refuse_periode_pour_mi_temps_therapeutique():
    with pytest.raises(ValidationError, match="jour par jour"):
        AbsenceRequestCreate(
            **_payload_arret(
                arret_type="mi_temps_therapeutique",
                date_debut=date(2026, 8, 17),
                date_fin=date(2026, 8, 21),
            )
        )


def test_schema_refuse_sans_jours_ni_periode():
    with pytest.raises(ValidationError, match="au moins un jour"):
        AbsenceRequestCreate(**_payload_arret())


def test_schema_jours_seuls_comportement_inchange():
    req = AbsenceRequestCreate(**_payload_arret(selected_days=[date(2026, 8, 17)]))
    assert req.selected_days == [date(2026, 8, 17)]
    assert req.date_debut is None
```

- [ ] **Step 2: Vérifier l'échec**

Run: `./venv/bin/python -m pytest tests/unit/absences/test_expansion_calendaire.py -q`
Expected: FAIL — `ValidationError` inattendues (`date_debut` champ inconnu / `selected_days` requis)

- [ ] **Step 3: Implémenter**

Dans `requests.py`, classe `AbsenceRequestCreate` :

```python
    employee_id: str
    type: AbsenceType
    # Saisie jour par jour (congés, mi-temps thérapeutique, historique)…
    selected_days: List[date] = []
    # …ou saisie par période calendaire (arrêts) : le serveur étend en jours,
    # week-ends et fériés compris (spec 2026-09-01 arrêts jours calendaires).
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
```

Puis ajouter après `arret_type_required_for_arrets` :

```python
    @model_validator(mode="after")
    def periode_ou_jours(self) -> "AbsenceRequestCreate":
        a_periode = self.date_debut is not None or self.date_fin is not None
        if a_periode:
            if self.date_debut is None or self.date_fin is None:
                raise ValueError(
                    "Une période d'arrêt doit porter une date de début ET une date de fin."
                )
            if self.date_fin < self.date_debut:
                raise ValueError(
                    "La date de fin de l'arrêt est antérieure à sa date de début."
                )
            if self.selected_days:
                raise ValueError(
                    "Fournissez soit des jours sélectionnés, soit une période, pas les deux."
                )
            if self.type not in _ARRETS_TYPES_PRINCIPAUX:
                raise ValueError(
                    "La saisie par période (du … au …) est réservée aux arrêts de travail."
                )
            if self.arret_type == "mi_temps_therapeutique":
                raise ValueError(
                    "Un mi-temps thérapeutique se saisit jour par jour "
                    "(le salarié travaille partiellement), pas par période."
                )
        elif not self.selected_days:
            raise ValueError("Veuillez sélectionner au moins un jour ou une période.")
        return self
```

- [ ] **Step 4: Vérifier le vert**

Run: `./venv/bin/python -m pytest tests/unit/absences/test_expansion_calendaire.py tests/unit/absences/test_domain.py tests/integration/absences -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/absences/schemas/requests.py backend/tests/unit/absences/test_expansion_calendaire.py
git commit -m "feat(absences): le schéma de création accepte une période d'arrêt"
```

---

### Task 3: Commande — expansion calendaire à la création

**Files:**
- Modify: `backend/app/modules/absences/application/commands.py:152-161`
- Test: `backend/tests/unit/absences/test_expansion_calendaire.py`

**Interfaces:**
- Consumes: `daterange_days` (Task 1), champs `date_debut`/`date_fin` (Task 2).
- Produces: `create_absence_request` stocke en base `selected_days` = tous les jours calendaires de la période quand `date_debut`/`date_fin` sont de vraies `date`. Aucune migration : le stockage reste `selected_days`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `test_expansion_calendaire.py` (style de `tests/unit/absences/test_commands.py`) :

```python
from unittest.mock import MagicMock, patch

from app.modules.absences.application import commands


def _request_data_periode():
    request_data = MagicMock()
    request_data.selected_days = []
    request_data.date_debut = date(2026, 8, 14)  # vendredi
    request_data.date_fin = date(2026, 8, 17)  # lundi
    request_data.type = "arret_maladie"
    request_data.employee_id = "emp-1"
    request_data.event_subtype = None
    request_data.comment = None
    request_data.attachment_url = None
    request_data.filename = None
    request_data.arret_type = "maladie_simple"
    return request_data


def test_creation_par_periode_stocke_tous_les_jours_calendaires():
    with patch(
        "app.modules.absences.application.commands.get_employee_company_id",
        return_value="comp-1",
    ):
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.create.return_value = {"id": "req-1"}
            commands.create_absence_request(_request_data_periode())

    call_data = repo.create.call_args[0][0]
    assert call_data["selected_days"] == [
        "2026-08-14",
        "2026-08-15",
        "2026-08-16",
        "2026-08-17",
    ]


def test_creation_par_jours_ignore_les_faux_attributs_periode():
    # MagicMock auto-crée date_debut/date_fin (non-dates) : pas d'expansion.
    request_data = MagicMock()
    request_data.selected_days = [date(2026, 8, 14)]
    request_data.type = "rtt"
    request_data.employee_id = "emp-1"
    request_data.event_subtype = None
    request_data.comment = None
    request_data.attachment_url = None
    request_data.filename = None

    with patch(
        "app.modules.absences.application.commands.get_employee_company_id",
        return_value="comp-1",
    ):
        with patch(
            "app.modules.absences.application.commands.absence_repository"
        ) as repo:
            repo.create.return_value = {"id": "req-2"}
            commands.create_absence_request(request_data)

    assert repo.create.call_args[0][0]["selected_days"] == ["2026-08-14"]
```

- [ ] **Step 2: Vérifier l'échec**

Run: `./venv/bin/python -m pytest tests/unit/absences/test_expansion_calendaire.py -q`
Expected: FAIL — `test_creation_par_periode…` : `ValueError: Veuillez sélectionner au moins un jour.`

- [ ] **Step 3: Implémenter**

Dans `commands.py`, ajouter `daterange_days` à l'import existant de `app.shared.domain.absence_calendar` (ou créer l'import s'il n'existe pas dans ce fichier), puis remplacer le début de `create_absence_request` :

```python
    selected_days = getattr(request_data, "selected_days", None) or []
    date_debut = getattr(request_data, "date_debut", None)
    date_fin = getattr(request_data, "date_fin", None)
    # Saisie par période (arrêts) : l'expansion calendaire est faite SERVEUR,
    # pour que toute origine de saisie produise des jours cohérents, week-ends
    # et fériés compris. `isinstance` : ne se déclenche que sur de vraies dates
    # (schéma API) — pas sur les payloads DSN (déjà expansés) ni les doubles de
    # test.
    if isinstance(date_debut, date) and isinstance(date_fin, date):
        selected_days = daterange_days(date_debut, date_fin)
    if not selected_days:
        raise ValueError("Veuillez sélectionner au moins un jour.")
```

- [ ] **Step 4: Vérifier le vert**

Run: `./venv/bin/python -m pytest tests/unit/absences/test_expansion_calendaire.py tests/unit/absences/test_commands.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/absences/application/commands.py backend/tests/unit/absences/test_expansion_calendaire.py
git commit -m "feat(absences): expansion calendaire serveur d'une période d'arrêt"
```

---

### Task 4: Projection au calendrier — déverrouiller week-ends/repos/fériés pour les arrêts

**Files:**
- Modify: `backend/app/modules/absences/infrastructure/providers.py:247-330`
- Test: `backend/tests/unit/schedules/test_planned_calendar_preservation.py` (harnais `_provider_avec_calendrier` existant, l.385)

**Interfaces:**
- Consumes: harnais `_provider_avec_calendrier(monkeypatch, calendrier_existant)` → `(provider, capture)` ; `capture["ecrit"]` = calendrier écrit.
- Produces: pour un type d'arrêt (`is_arret`), `update_calendar_from_days` convertit désormais les jours `weekend`/`repos`/`ferie` (en plus de `travail`/`work`) en `arret_maladie` avec `heures_prevues = 0`. Types non-arrêt : comportement inchangé. Jours `conge`/`conges_payes`/`rtt` jamais écrasés.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `test_planned_calendar_preservation.py` (après `test_les_jours_de_remplissage_ne_sont_pas_marques`) :

```python
def test_validation_arret_convertit_week_ends_repos_et_feries(monkeypatch):
    """Un arrêt est calendaire (Cerfa) : ses jours non travaillés deviennent
    arret_maladie, sinon le bulletin tronque l'arrêt au dernier jour ouvré et
    perd des jours d'IJSS / maintien / prévoyance en bord de mois."""
    from datetime import date

    existant = [
        {"jour": 14, "type": "travail", "heures_prevues": 7.0},
        {"jour": 15, "type": "weekend", "heures_prevues": 0},
        {"jour": 16, "type": "repos", "heures_prevues": 0},
        {"jour": 17, "type": "ferie", "heures_prevues": 0},
    ]
    provider, capture = _provider_avec_calendrier(monkeypatch, existant)

    provider.update_calendar_from_days(
        "emp-1",
        [date(2026, 8, j) for j in (14, 15, 16, 17)],
        "arret_maladie",
        arret_type="maladie_simple",
    )

    for jour in (14, 15, 16, 17):
        entree = next(e for e in capture["ecrit"] if e["jour"] == jour)
        assert entree["type"] == "arret_maladie", f"jour {jour}"
        assert entree["heures_prevues"] == 0
        assert entree["origine"] == "absence"
        assert entree["arret_type"] == "maladie_simple"


def test_validation_conge_ne_convertit_pas_les_week_ends(monkeypatch):
    """Le déverrouillage calendaire ne vaut que pour les arrêts : un congé payé
    continue de ne se poser que sur des jours de travail planifiés."""
    from datetime import date

    existant = [
        {"jour": 14, "type": "travail", "heures_prevues": 7.0},
        {"jour": 15, "type": "weekend", "heures_prevues": 0},
    ]
    provider, capture = _provider_avec_calendrier(monkeypatch, existant)

    provider.update_calendar_from_days(
        "emp-1", [date(2026, 8, 14), date(2026, 8, 15)], "conge_paye"
    )

    jour14 = next(e for e in capture["ecrit"] if e["jour"] == 14)
    jour15 = next(e for e in capture["ecrit"] if e["jour"] == 15)
    assert jour14["type"] == "conges_payes"
    assert jour15["type"] == "weekend"


def test_validation_arret_ne_requalifie_pas_un_conge_pose(monkeypatch):
    """La requalification congé→arrêt est un sujet séparé (cf.
    dev-lot1-preservation-planning) : un jour déjà en congé reste intact."""
    from datetime import date

    existant = [{"jour": 14, "type": "conges_payes", "heures_prevues": 0}]
    provider, capture = _provider_avec_calendrier(monkeypatch, existant)

    provider.update_calendar_from_days(
        "emp-1", [date(2026, 8, 14)], "arret_maladie", arret_type="maladie_simple"
    )

    assert capture["ecrit"][0]["type"] == "conges_payes"
```

- [ ] **Step 2: Vérifier l'échec**

Run: `./venv/bin/python -m pytest tests/unit/schedules/test_planned_calendar_preservation.py -q`
Expected: FAIL — `test_validation_arret_convertit_week_ends_repos_et_feries` (jours 15-17 restent `weekend`/`repos`/`ferie`) ; les 2 autres nouveaux tests passent déjà (non-régression).

- [ ] **Step 3: Implémenter**

Dans `providers.py`, après le calcul de `new_calendar_type` (l.249-251), ajouter :

```python
        # Un arrêt de travail est calendaire (Cerfa) : il couvre aussi les
        # jours non travaillés. Sans cette conversion, le bulletin (min/max des
        # jours typés arret_maladie) tronque l'arrêt au dernier jour ouvré et
        # perd des jours d'IJSS / maintien / prévoyance en bord de mois. Les
        # congés, eux, ne se posent que sur des jours de travail planifiés.
        types_convertibles = (
            ("travail", "work", "weekend", "repos", "ferie")
            if is_arret
            else ("travail", "work")
        )
```

Puis remplacer la condition l.330 (et son commentaire WORK_TYPES l.327-329) par :

```python
                    # `types_convertibles` : cf. commentaire au calcul — un jour
                    # 'work' écrit par apply-model doit aussi pouvoir devenir
                    # une absence.
                    if (
                        entry.get("jour") in day_list
                        and entry.get("type") in types_convertibles
                    ):
```

`entry["heures_prevues"] = 0` existant (l.332) reste : les jours non travaillés en avaient déjà 0 → aucune sur-déduction (la retenue passe par `heures_prevues`).

- [ ] **Step 4: Vérifier le vert**

Run: `./venv/bin/python -m pytest tests/unit/schedules tests/unit/absences -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/absences/infrastructure/providers.py backend/tests/unit/schedules/test_planned_calendar_preservation.py
git commit -m "fix(absences): les week-ends et fériés d'un arrêt deviennent arret_maladie au calendrier"
```

---

### Task 5: Verrous de non-régression aval (bulletin + prime de présence)

**Files:**
- Test: `backend/tests/unit/payroll/test_arret_vrai_debut.py`
- Test: `backend/tests/unit/payroll_variables/test_generate_monthly_presence.py`

Ces deux tests passent SANS changement de code : ils figent des décisions de la spec (aucune tolérance à une « correction » future qui retirerait les week-ends).

- [ ] **Step 1: Ajouter le test bulletin**

Dans `test_arret_vrai_debut.py`, après `test_arret_fallback_premier_jour_du_mois_sans_vrai_debut` :

```python
def test_arret_finissant_un_dimanche_conserve_le_dimanche_en_date_fin():
    """30/08/2026 = dimanche. Depuis l'expansion calendaire (spec 2026-09-01),
    les week-ends d'un arrêt sont typés arret_maladie : la date_fin extraite
    pour maintien/IJSS/prévoyance est ce dimanche, pas le dernier jour ouvré."""
    cal = [
        {"date_complete": "2026-08-28", "type": "arret_maladie",
         "arret_type": "maladie_simple"},
        {"date_complete": "2026-08-29", "type": "arret_maladie",
         "arret_type": "maladie_simple"},
        {"date_complete": "2026-08-30", "type": "arret_maladie",
         "arret_type": "maladie_simple"},
    ]
    arret = _extraire_arret_pour_maintien(cal, _Ctx(), date(2026, 8, 1), date(2026, 8, 31))
    assert arret["date_fin"] == "2026-08-30"
```

- [ ] **Step 2: Ajouter le test prime de présence**

Dans `test_generate_monthly_presence.py` (adapter les imports au style du fichier) :

```python
def test_un_dimanche_d_arret_disqualifie_la_semaine_de_presence():
    """Décision figée (spec arrêts calendaires 2026-09-01) : un arrêt couvrant
    le week-end disqualifie la semaine — l'arrêt couvre réellement ce jour."""
    from datetime import date

    from app.modules.payroll_variables.domain.presence_week import (
        week_has_disqualifying_absence,
    )

    lundi = date(2026, 8, 24)
    assert week_has_disqualifying_absence(lundi, {date(2026, 8, 30)}) is True
```

- [ ] **Step 3: Vérifier le vert**

Run: `./venv/bin/python -m pytest tests/unit/payroll/test_arret_vrai_debut.py tests/unit/payroll_variables/test_generate_monthly_presence.py -q`
Expected: PASS immédiat (verrous)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/unit/payroll/test_arret_vrai_debut.py backend/tests/unit/payroll_variables/test_generate_monthly_presence.py
git commit -m "test(paie): figer le décompte calendaire d'un arrêt finissant le week-end"
```

---

### Task 6: Frontend — utilitaire de période d'arrêt

**Files:**
- Create: `frontend/src/lib/arretPeriode.ts`
- Test: `frontend/src/lib/arretPeriode.test.ts`

**Interfaces:**
- Produces: `nbJoursCalendaires(from: Date, to: Date): number` (bornes incluses) et `formatPeriodeArret(from: Date, to?: Date): string` → « Du 17/08/2026 au 18/09/2026 (33 jours calendaires) » / « Du 17/08/2026 au … ». Consommé par la tâche 7.

- [ ] **Step 1: Écrire les tests qui échouent**

`frontend/src/lib/arretPeriode.test.ts` :

```ts
import { describe, expect, it } from "vitest";

import { formatPeriodeArret, nbJoursCalendaires } from "./arretPeriode";

describe("nbJoursCalendaires", () => {
  it("compte bornes incluses, week-ends compris (17/08 → 18/09 = 33)", () => {
    expect(nbJoursCalendaires(new Date(2026, 7, 17), new Date(2026, 8, 18))).toBe(33);
  });

  it("un seul jour vaut 1", () => {
    expect(nbJoursCalendaires(new Date(2026, 7, 17), new Date(2026, 7, 17))).toBe(1);
  });
});

describe("formatPeriodeArret", () => {
  it("formate la période complète avec le compte calendaire", () => {
    expect(formatPeriodeArret(new Date(2026, 7, 17), new Date(2026, 8, 18))).toBe(
      "Du 17/08/2026 au 18/09/2026 (33 jours calendaires)",
    );
  });

  it("formate le singulier", () => {
    expect(formatPeriodeArret(new Date(2026, 7, 17), new Date(2026, 7, 17))).toBe(
      "Du 17/08/2026 au 17/08/2026 (1 jour calendaire)",
    );
  });

  it("période en cours de sélection", () => {
    expect(formatPeriodeArret(new Date(2026, 7, 17))).toBe("Du 17/08/2026 au …");
  });
});
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd /Users/alex/Desktop/EYWAI/EYWAI/frontend && npm test -- src/lib/arretPeriode.test.ts`
Expected: FAIL — module `./arretPeriode` introuvable

- [ ] **Step 3: Implémenter**

`frontend/src/lib/arretPeriode.ts` :

```ts
// Période calendaire d'un arrêt de travail (spec 2026-09-01) : l'expansion en
// jours est faite par le serveur ; le front ne fait que compter et afficher.
import { differenceInCalendarDays, format } from "date-fns";

/** Nombre de jours calendaires d'une période, bornes incluses. */
export function nbJoursCalendaires(from: Date, to: Date): number {
  return differenceInCalendarDays(to, from) + 1;
}

/** Libellé du sélecteur de période d'arrêt. */
export function formatPeriodeArret(from: Date, to?: Date): string {
  const debut = format(from, "dd/MM/yyyy");
  if (!to) return `Du ${debut} au …`;
  const fin = format(to, "dd/MM/yyyy");
  const n = nbJoursCalendaires(from, to);
  const s = n > 1 ? "s" : "";
  return `Du ${debut} au ${fin} (${n} jour${s} calendaire${s})`;
}
```

- [ ] **Step 4: Vérifier le vert**

Run: `npm test -- src/lib/arretPeriode.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/arretPeriode.ts frontend/src/lib/arretPeriode.test.ts
git commit -m "feat(frontend): utilitaire de période calendaire d'arrêt"
```

---

### Task 7: Frontend — le modal RH saisit un arrêt « du … au … »

**Files:**
- Modify: `frontend/src/api/absences.ts:169-178`
- Modify: `frontend/src/components/AbsenceRequestModal.tsx`

**Interfaces:**
- Consumes: `formatPeriodeArret`, `nbJoursCalendaires` (Task 6) ; champs backend `date_debut`/`date_fin` (Task 2).
- Produces: en mode `rh_arret`, pour un type d'arrêt avec `arret_type ≠ mi_temps_therapeutique`, le payload envoie `date_debut`/`date_fin` (pas de `selected_days`). Mi-temps thérapeutique et modes `employee`/`rh_leave` : inchangés.

- [ ] **Step 1: Adapter le type de payload**

Dans `api/absences.ts` :

```ts
export interface AbsenceCreationPayload {
  employee_id: string;
  type: 'conge_paye' | 'rtt' | 'jtc' | 'repos_compensateur' | 'recuperation_modulation' | 'evenement_familial' | 'arret_maladie' | 'arret_at' | 'arret_paternite' | 'arret_maternite' | 'arret_maladie_pro';
  /** Saisie jour par jour ('YYYY-MM-DD') — congés, mi-temps thérapeutique. */
  selected_days?: string[];
  /** Saisie par période calendaire — arrêts : le backend étend en jours, week-ends compris. */
  date_debut?: string;
  date_fin?: string;
  comment?: string | null;
  attachment_url?: string | null;
  filename?: string | null;
  event_subtype?: string | null; // Requis si type = evenement_familial
  arret_type?: ArretType | null;
}
```

- [ ] **Step 2: Basculer le modal en mode période pour les arrêts**

Dans `AbsenceRequestModal.tsx` :

a) Imports : ajouter `import { type DateRange } from "react-day-picker";` et `import { formatPeriodeArret } from "@/lib/arretPeriode";`.

b) État (près de `selectedDays`, l.166) :

```tsx
  const [arretRange, setArretRange] = useState<DateRange | undefined>(undefined);
```

et dans l'effet de réinitialisation à l'ouverture (l.179-193), ajouter `setArretRange(undefined);`.

c) Sous les états, le sélecteur de mode de saisie :

```tsx
  // Un arrêt (hors mi-temps thérapeutique : travail partiel) se saisit en
  // période calendaire « du … au … » — l'expansion en jours est serveur.
  const isSaisiePeriode =
    isRhArret &&
    isArretPrincipalType(absenceType) &&
    arretType !== "mi_temps_therapeutique";
```

d) `doSubmit` (l.236-243, l.267-280) — garde d'entrée et payload :

```tsx
    if (isSaisiePeriode) {
      if (!arretRange?.from || !arretRange?.to) return;
    } else if (!selectedDays || selectedDays.length === 0) {
      return;
    }
```

et construire le payload ainsi :

```tsx
      const payload: absencesApi.AbsenceCreationPayload = {
        employee_id: employeeId,
        type: absenceType as absencesApi.AbsenceCreationPayload["type"],
        comment: comment || null,
        attachment_url: attachmentUrl,
        filename: filename,
      };
      if (isSaisiePeriode && arretRange?.from && arretRange?.to) {
        payload.date_debut = format(arretRange.from, "yyyy-MM-dd");
        payload.date_fin = format(arretRange.to, "yyyy-MM-dd");
      } else {
        payload.selected_days = (selectedDays ?? []).map((day) =>
          format(day, "yyyy-MM-dd"),
        );
      }
```

(la constante `formattedDays` l.243 disparaît dans ce remaniement).

e) `handleSave` (l.330-337) — validation :

```tsx
    if (isSaisiePeriode) {
      if (!arretRange?.from || !arretRange?.to) {
        setError("Veuillez sélectionner la période d'arrêt (du … au …).");
        return;
      }
    } else if (!selectedDays || selectedDays.length === 0) {
      setError(
        isRhArret
          ? "Veuillez sélectionner au moins un jour d'arrêt."
          : "Veuillez sélectionner au moins un jour de congé.",
      );
      return;
    }
```

f) Bouton du popover (l.545-552) — libellé :

```tsx
                  {isSaisiePeriode
                    ? arretRange?.from
                      ? formatPeriodeArret(arretRange.from, arretRange.to)
                      : "Cliquez pour choisir la période"
                    : selectedDaysCount > 0
                      ? `${selectedDaysCount} jour${selectedDaysCount > 1 ? "s" : ""} sélectionné${selectedDaysCount > 1 ? "s" : ""}`
                      : isRhArret
                        ? "Cliquez pour choisir la période"
                        : "Cliquez pour choisir les dates"}
```

g) Calendrier (l.554-591) — rendu conditionnel :

```tsx
              <PopoverContent className="w-auto p-0" align="start">
                {isSaisiePeriode ? (
                  <Calendar
                    mode="range"
                    selected={arretRange}
                    onSelect={(range) => {
                      setError("");
                      setArretRange(range);
                    }}
                    numberOfMonths={2}
                    defaultMonth={arretRange?.from}
                    initialFocus
                    locale={fr}
                  />
                ) : (
                  <Calendar
                    mode="multiple"
                    ... (bloc existant inchangé)
                  />
                )}
              </PopoverContent>
```

- [ ] **Step 3: Vérifier types, lint et tests**

Run: `cd /Users/alex/Desktop/EYWAI/EYWAI/frontend && npm run lint && npm run build && npm test`
Expected: lint OK, build OK, tests verts (dont `arretPeriode.test.ts`)

- [ ] **Step 4: Vérification visuelle (optionnelle si environnement dispo)**

Lancer le front (`npm run dev`), ouvrir Absences RH → « + Enregistrer un arrêt » : le choix « Maladie simple » affiche un calendrier de plage sur 2 mois ; choisir « Mi-temps thérapeutique » rebascule en multi-sélection.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/absences.ts frontend/src/components/AbsenceRequestModal.tsx
git commit -m "feat(frontend): saisie d'un arrêt par période calendaire (du … au …)"
```

---

### Task 8: Script de réparation des arrêts existants

**Files:**
- Create: `backend/scripts/reparer_arrets_calendaires.py`
- Test: `backend/tests/unit/absences/test_reparer_arrets_calendaires.py`

**Interfaces:**
- Consumes: `daterange_days` (Task 1), provider déverrouillé (Task 4), `commands.calendar_update_provider` / `commands.build_historique_arrets_annee` / `commands.resolve_nombre_enfants_employee` / `commands.absence_repository`.
- Produces: script CLI `venv/bin/python -m scripts.reparer_arrets_calendaires [--apply] [--depuis 2026-08-01]` ; fonctions pures testables `jours_apres_expansion(selected_days) -> (complets, ajoutes)` et `arret_cible(row, depuis) -> bool`.

- [ ] **Step 1: Écrire les tests qui échouent**

`backend/tests/unit/absences/test_reparer_arrets_calendaires.py` :

```python
"""Fonctions pures du script de réparation des arrêts calendaires."""

from datetime import date

from scripts.reparer_arrets_calendaires import arret_cible, jours_apres_expansion


def test_expansion_comble_les_week_ends():
    complets, ajoutes = jours_apres_expansion(["2026-08-14", "2026-08-17"])
    assert complets == ["2026-08-14", "2026-08-15", "2026-08-16", "2026-08-17"]
    assert ajoutes == ["2026-08-15", "2026-08-16"]


def test_expansion_deja_complete_est_idempotente():
    complets, ajoutes = jours_apres_expansion(["2026-08-14", "2026-08-15"])
    assert complets == ["2026-08-14", "2026-08-15"]
    assert ajoutes == []


def test_cible_respecte_la_borne_depuis():
    row = {
        "status": "validated",
        "type": "arret_maladie",
        "arret_type": "maladie_simple",
        "selected_days": ["2026-07-01", "2026-07-10"],
    }
    assert arret_cible(row, date(2026, 8, 1)) is False
    a_cheval = {**row, "selected_days": ["2026-07-28", "2026-08-03"]}
    assert arret_cible(a_cheval, date(2026, 8, 1)) is True


def test_cible_exclut_mi_temps_therapeutique_non_valides_et_non_arrets():
    base = {
        "status": "validated",
        "type": "arret_maladie",
        "arret_type": "maladie_simple",
        "selected_days": ["2026-08-10"],
    }
    assert arret_cible(base, date(2026, 8, 1)) is True
    assert arret_cible({**base, "arret_type": "mi_temps_therapeutique"}, date(2026, 8, 1)) is False
    assert arret_cible({**base, "status": "pending"}, date(2026, 8, 1)) is False
    assert arret_cible({**base, "type": "conge_paye"}, date(2026, 8, 1)) is False
```

- [ ] **Step 2: Vérifier l'échec**

Run: `./venv/bin/python -m pytest tests/unit/absences/test_reparer_arrets_calendaires.py -q`
Expected: FAIL — module `scripts.reparer_arrets_calendaires` introuvable

- [ ] **Step 3: Implémenter le script**

`backend/scripts/reparer_arrets_calendaires.py` (mêmes conventions que `scripts/backfill_origine_absence.py` : sys.path, dry-run par défaut, rapport) :

```python
#!/usr/bin/env python3
"""Répare les arrêts existants pour le décompte calendaire (spec 2026-09-01).

Avant ce lot, ① la saisie jour par jour laissait des trous (week-ends non
cliqués) dans `selected_days`, et ② la projection au calendrier ignorait les
week-ends même saisis. Pour chaque arrêt validé ciblé, ce script :

1. comble `selected_days` en période calendaire continue min→max (un
   enregistrement d'absence = UNE période, par construction du modèle) ;
2. re-projette le calendrier de paie via le même chemin que la validation
   (`update_calendar_from_days`, désormais déverrouillé pour les week-ends).

Cibles : `absence_requests` validées, type dans IJSS_ELIGIBLE_TYPES,
`arret_type != mi_temps_therapeutique` (travail partiel : jour par jour),
avec au moins un jour >= --depuis (défaut 2026-08-01 — ne pas toucher les
calendriers qui sous-tendent les bulletins Colorplast 01→06/2026 convergés).

Sans `--apply`, rien n'est écrit : rapport de simulation seulement.

Usage :
    venv/bin/python -m scripts.reparer_arrets_calendaires
    venv/bin/python -m scripts.reparer_arrets_calendaires --depuis 2026-08-01 --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.modules.absences.domain.enums import IJSS_ELIGIBLE_TYPES  # noqa: E402
from app.shared.domain.absence_calendar import daterange_days  # noqa: E402


def _as_date(raw: Any) -> Optional[date]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def jours_apres_expansion(selected_days: List[Any]) -> Tuple[List[str], List[str]]:
    """(période calendaire complète min→max triée, jours ajoutés)."""
    parses = sorted({d for d in (_as_date(x) for x in selected_days or []) if d})
    if not parses:
        return [], []
    complets = [d.isoformat() for d in daterange_days(parses[0], parses[-1])]
    existants = {d.isoformat() for d in parses}
    return complets, [d for d in complets if d not in existants]


def arret_cible(row: Dict[str, Any], depuis: date) -> bool:
    """Arrêt validé, calendaire par nature, avec au moins un jour >= depuis."""
    if str(row.get("status") or "") != "validated":
        return False
    if str(row.get("type") or "") not in IJSS_ELIGIBLE_TYPES:
        return False
    if str(row.get("arret_type") or "") == "mi_temps_therapeutique":
        return False
    jours = [d for d in (_as_date(x) for x in row.get("selected_days") or []) if d]
    return bool(jours) and max(jours) >= depuis


def _reprojeter(row: Dict[str, Any], jours_iso: List[str]) -> None:
    """Rejoue la projection calendrier comme la validation d'absence."""
    from app.modules.absences.application import commands

    employee_id = str(row["employee_id"])
    absence_type = str(row["type"])
    jours = [date.fromisoformat(d) for d in jours_iso]
    historique = commands.build_historique_arrets_annee(
        employee_id, jours[0].year, exclude_request_id=str(row["id"])
    )
    sub = row.get("subrogation_active")
    commands.calendar_update_provider.update_calendar_from_days(
        employee_id,
        jours,
        absence_type,
        arret_type=str(row["arret_type"]) if row.get("arret_type") else None,
        subrogation_active=sub if isinstance(sub, bool) else None,
        nombre_enfants=commands.resolve_nombre_enfants_employee(employee_id),
        historique_arrets_annee=historique or None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="écrit (défaut : simulation)")
    parser.add_argument(
        "--depuis",
        type=date.fromisoformat,
        default=date(2026, 8, 1),
        help="ne traite que les arrêts ayant au moins un jour >= cette date",
    )
    args = parser.parse_args()

    from app.modules.absences.application import commands
    from app.modules.absences.infrastructure.pagination import fetch_all_rows

    lignes = fetch_all_rows(
        "absence_requests",
        select="id, employee_id, company_id, type, arret_type, status, "
        "selected_days, subrogation_active",
        filters={"status": "validated"},
    )
    cibles = [r for r in lignes if arret_cible(r, args.depuis)]
    total_ajoutes = 0
    for row in cibles:
        complets, ajoutes = jours_apres_expansion(row.get("selected_days") or [])
        total_ajoutes += len(ajoutes)
        etiquette = f"{row['id']} employé={row['employee_id']} {complets[0]}→{complets[-1]}"
        print(f"- {etiquette} : {len(ajoutes)} jour(s) à combler {ajoutes or ''}")
        if args.apply:
            if ajoutes:
                commands.absence_repository.update(
                    str(row["id"]), {"selected_days": complets}
                )
            # Re-projection systématique : les week-ends déjà présents dans
            # selected_days étaient ignorés par l'ancienne projection.
            _reprojeter(row, complets)
    mode = "APPLIQUÉ" if args.apply else "SIMULATION (rien écrit — relancer avec --apply)"
    print(f"\n{len(cibles)} arrêt(s) ciblé(s), {total_ajoutes} jour(s) comblé(s) — {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

NOTE exécution : vérifier la signature réelle de `fetch_all_rows` (`app/modules/absences/infrastructure/pagination.py`) et l'adapter si besoin (ex. filtre PostgREST via builder) — `scripts/backfill_origine_absence.py` montre l'usage de référence.

- [ ] **Step 4: Vérifier le vert**

Run: `./venv/bin/python -m pytest tests/unit/absences/test_reparer_arrets_calendaires.py -q`
Expected: PASS

- [ ] **Step 5: Dry-run local (lecture seule, base prod — AUCUN --apply)**

Run: `cd /Users/alex/Desktop/EYWAI/EYWAI/backend && ./venv/bin/python -m scripts.reparer_arrets_calendaires`
Expected: rapport listant au moins l'arrêt de Marion GAUTHERON (17/08→18/09/2026) avec ses week-ends à combler. **Ne pas lancer `--apply`** : l'exécution réelle (test puis prod) est validée par Alexandre après revue.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/reparer_arrets_calendaires.py backend/tests/unit/absences/test_reparer_arrets_calendaires.py
git commit -m "feat(scripts): réparer les arrêts existants en périodes calendaires"
```

---

### Task 9: Suites complètes et lint

**Files:** aucun nouveau — vérification globale.

- [ ] **Step 1: Backend ciblé large**

Run: `cd /Users/alex/Desktop/EYWAI/EYWAI/backend && ./venv/bin/python -m pytest tests/unit/absences tests/unit/schedules tests/unit/payroll tests/unit/payroll_variables tests/unit/exports tests/unit/dsn_import tests/integration/absences -q`
Expected: PASS

- [ ] **Step 2: Backend complet**

Run: `./venv/bin/python -m pytest tests/unit -q` (long : lancer en arrière-plan si besoin)
Expected: PASS (dette ruff pré-existante non concernée)

- [ ] **Step 3: Ruff sur les fichiers touchés**

Run: `./venv/bin/python -m ruff check app/shared/domain/absence_calendar.py app/modules/absences app/modules/dsn_import/domain/dsn_absence_exit_mapping.py scripts/reparer_arrets_calendaires.py`
Expected: aucun nouveau finding

- [ ] **Step 4: Frontend complet**

Run: `cd /Users/alex/Desktop/EYWAI/EYWAI/frontend && npm run lint && npm run build && npm test`
Expected: PASS

- [ ] **Step 5: Commit final éventuel (corrections issues des suites)**

```bash
git add -A && git commit -m "fix(absences): corrections issues des suites complètes"
```
(uniquement s'il y a eu des corrections)
