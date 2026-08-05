# Suivi des périodes d'essai — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre à Elsa d'activer, paramétrer et suivre les périodes d'essai de n'importe quel salarié, à tout moment après sa création.

**Architecture :** une table dédiée `trial_periods` devient la source unique, en remplacement du champ `employees.periode_essai` (jsonb vide sur les 241 salariés, donc rien à migrer). Le calcul de la date de fin et la résolution du barème société sont des fonctions pures du domaine, testées ; l'écriture passe par une seule commande applicative. Le frontend gagne une page de suivi calquée sur `ResidencePermits.tsx` et une carte de fiche salarié toujours visible.

**Tech Stack :** FastAPI / Python 3.12, Supabase PostgreSQL 17, React / Vite / TypeScript, shadcn-ui, TanStack Query, pytest, vitest.

**Spec :** `docs/superpowers/specs/2026-08-05-periodes-essai-design.md`

## Global Constraints

- Le dépôt est **public** : aucune donnée nominative dans le code, les tests ou les docs. Les noms de salariés utilisés en test sont fictifs.
- Migration à horodatage **unique et postérieur à `20260805100000`**, l'horodatage étant la clé primaire de la CLI Supabase. Appliquer d'abord sur l'environnement de test.
- RLS **activée dès la création** de toute table, avec policy `SELECT` restreinte à `user_company_accesses` et écriture réservée au `service_role` — pattern de `supabase/migrations/20260803160000_company_dsn_settings.sql`.
- Le moteur reste **généraliste** : aucune règle spécifique à un salarié ou à une société codée en dur.
- La CI ne bloque que sur `backend/tests/unit`. Les 51 échecs d'intégration (`schedules`, `saisies_avances`) sont préexistants et ne jugent pas ce changement.
- Ne jamais `git add -A` : d'autres sessions travaillent sur la même branche. Stager les chemins explicitement.
- Messages de commit en français, terminés par `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## Structure des fichiers

**Backend — nouveau module `trial_periods`** (le domaine du calcul reste dans `employees`, où il vit déjà) :

| Fichier | Responsabilité |
|---|---|
| `backend/app/modules/employees/domain/trial_period_dates.py` | Calcul pur de la date de fin (créé) |
| `backend/app/modules/employees/domain/trial_period_bareme.py` | Résolution pure du barème société (créé) |
| `backend/app/modules/employees/domain/trial_period_shared.py` | Constantes partagées ; `compute_trial_period_end` délègue au nouveau calcul (modifié) |
| `backend/app/modules/trial_periods/domain/constants.py` | Statuts, unités, table (créé) |
| `backend/app/modules/trial_periods/infrastructure/queries.py` | Noms de table et projections (créé) |
| `backend/app/modules/trial_periods/infrastructure/repository.py` | Persistance Supabase (créé) |
| `backend/app/modules/trial_periods/application/commands.py` | Créer, modifier, confirmer, renouveler (créé) |
| `backend/app/modules/trial_periods/application/queries.py` | Listes de la page de suivi (créé) |
| `backend/app/modules/trial_periods/schemas/requests.py` / `responses.py` | Contrats d'API (créés) |
| `backend/app/modules/trial_periods/api/router.py` | Routes (créé) |
| `backend/app/api/router.py` | Enregistrement du routeur (modifié) |

**Frontend :**

| Fichier | Responsabilité |
|---|---|
| `frontend/src/api/trialPeriods.ts` | Client d'API (créé) |
| `frontend/src/pages/rh/TrialPeriods.tsx` | Page de suivi en trois sections (créé) |
| `frontend/src/components/employee-detail/EmployeeDetailTrialPeriodCard.tsx` | Carte toujours visible, renouvellement (réécrit) |
| `frontend/src/lib/trialPeriodUtils.ts` | Calcul de fin côté client, aligné sur le backend (modifié) |
| `frontend/src/App.tsx`, `frontend/src/components/ui/app-sidebar.tsx`, `frontend/src/pages/index.ts` | Route et entrée de menu (modifiés) |

---

### Task 1 : Calcul pur de la date de fin

Le cœur juridique du chantier. `compute_trial_period_end` fait aujourd'hui `hire + N mois`, soit un jour de trop : une période de deux mois débutant le 1er mars y finit le 1er mai alors qu'elle expire le 30 avril à minuit.

**Files:**
- Create: `backend/app/modules/employees/domain/trial_period_dates.py`
- Test: `backend/tests/unit/employees/test_trial_period_dates.py`

**Interfaces:**
- Consumes: rien
- Produces: `compute_trial_end(start: date, duration_value: int, duration_unit: str, renewal_value: int | None = None, renewal_unit: str | None = None) -> date | None`

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/employees/test_trial_period_dates.py` :

```python
"""Calcul de la fin de période d'essai (décompte de quantième à quantième)."""

from datetime import date

import pytest

from app.modules.employees.domain.trial_period_dates import compute_trial_end


@pytest.mark.parametrize(
    "start, value, unit, expected",
    [
        # Deux mois à compter du 1er mars expirent le 30 avril, pas le 1er mai.
        (date(2026, 3, 1), 2, "mois", date(2026, 4, 30)),
        # Le quantième 31 février n'existe pas : la période court jusqu'au
        # dernier jour du mois d'arrivée.
        (date(2026, 1, 31), 1, "mois", date(2026, 2, 28)),
        (date(2028, 1, 31), 1, "mois", date(2028, 2, 29)),
        (date(2026, 3, 31), 1, "mois", date(2026, 4, 30)),
        (date(2026, 3, 16), 1, "mois", date(2026, 4, 15)),
        (date(2026, 3, 1), 4, "mois", date(2026, 6, 30)),
        # Le jour d'embauche compte comme premier jour.
        (date(2026, 3, 2), 8, "jours", date(2026, 3, 9)),
        (date(2026, 3, 2), 1, "jours", date(2026, 3, 2)),
        (date(2026, 3, 2), 2, "semaines", date(2026, 3, 15)),
    ],
)
def test_fin_sans_renouvellement(start, value, unit, expected):
    assert compute_trial_end(start, value, unit) == expected


def test_renouvellement_prolonge_depuis_la_fin_initiale():
    # 1er mars + 2 mois = 30 avril ; renouvelée 2 mois, elle repart le 1er mai
    # et expire le 30 juin.
    assert compute_trial_end(
        date(2026, 3, 1), 2, "mois", renewal_value=2, renewal_unit="mois"
    ) == date(2026, 6, 30)


def test_renouvellement_en_jours():
    assert compute_trial_end(
        date(2026, 3, 2), 8, "jours", renewal_value=8, renewal_unit="jours"
    ) == date(2026, 3, 17)


def test_renouvellement_bascule_sur_un_quantieme_inexistant():
    # 30 décembre + 1 mois = 29 janvier ; renouvelée 1 mois, elle repart le
    # 30 janvier et le quantième 30 février n'existe pas.
    assert compute_trial_end(
        date(2025, 12, 30), 1, "mois", renewal_value=1, renewal_unit="mois"
    ) == date(2026, 2, 28)


@pytest.mark.parametrize("value", [0, -1])
def test_duree_non_positive_refusee(value):
    assert compute_trial_end(date(2026, 3, 1), value, "mois") is None


def test_unite_inconnue_refusee():
    assert compute_trial_end(date(2026, 3, 1), 2, "trimestres") is None
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/employees/test_trial_period_dates.py -v
```

Attendu : `ModuleNotFoundError: No module named 'app.modules.employees.domain.trial_period_dates'`.

- [ ] **Step 3 : écrire l'implémentation minimale**

Créer `backend/app/modules/employees/domain/trial_period_dates.py` :

```python
"""Calcul de la fin de période d'essai.

Le décompte va de quantième à quantième et la période expire la veille du
quantième correspondant : deux mois à compter du 1er mars s'achèvent le
30 avril à minuit. Quand ce quantième n'existe pas dans le mois d'arrivée
(31 janvier + 1 mois), la période court jusqu'au dernier jour du mois.

Une rupture notifiée après cette date est prononcée hors période d'essai,
donc requalifiée : le jour compte.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta

UNIT_DAYS = "jours"
UNIT_WEEKS = "semaines"
UNIT_MONTHS = "mois"

VALID_UNITS = frozenset({UNIT_DAYS, UNIT_WEEKS, UNIT_MONTHS})


def _normalize_unit(unit: object) -> Optional[str]:
    raw = str(unit or "").strip().lower()
    if raw.startswith("jour"):
        return UNIT_DAYS
    if raw.startswith("sem"):
        return UNIT_WEEKS
    if raw.startswith("mois"):
        return UNIT_MONTHS
    return None


def _last_day_of_period(start: date, value: int, unit: str) -> date:
    """Dernier jour inclus d'une période de `value` `unit` commençant à `start`."""
    if unit == UNIT_DAYS:
        return start + timedelta(days=value - 1)
    if unit == UNIT_WEEKS:
        return start + timedelta(weeks=value) - timedelta(days=1)

    target = start + relativedelta(months=value)
    if target.day == start.day:
        # Le quantième existe : la période expire la veille.
        return target - timedelta(days=1)
    # relativedelta a tronqué au dernier jour du mois (31 janvier + 1 mois
    # donne le 28 février) : c'est déjà le dernier jour de la période.
    return target


def compute_trial_end(
    start: date,
    duration_value: int,
    duration_unit: str,
    renewal_value: Optional[int] = None,
    renewal_unit: Optional[str] = None,
) -> Optional[date]:
    """Dernier jour de la période d'essai, renouvellement inclus.

    Retourne None si la durée ou l'unité sont inexploitables.
    """
    unit = _normalize_unit(duration_unit)
    if unit is None:
        return None
    try:
        value = int(duration_value)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None

    end = _last_day_of_period(start, value, unit)

    if renewal_value is None:
        return end

    r_unit = _normalize_unit(renewal_unit) or unit
    try:
        r_value = int(renewal_value)
    except (TypeError, ValueError):
        return end
    if r_value <= 0:
        return end

    # Le renouvellement repart le lendemain de la fin initiale.
    return _last_day_of_period(end + timedelta(days=1), r_value, r_unit)


__all__ = [
    "UNIT_DAYS",
    "UNIT_WEEKS",
    "UNIT_MONTHS",
    "VALID_UNITS",
    "compute_trial_end",
]
```

- [ ] **Step 4 : lancer le test pour vérifier qu'il passe**

```bash
cd backend && python -m pytest tests/unit/employees/test_trial_period_dates.py -v
```

Attendu : 14 tests PASSED.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/modules/employees/domain/trial_period_dates.py backend/tests/unit/employees/test_trial_period_dates.py
git commit -m "fix(essai): calcul de fin de période d'essai au bon jour

Le décompte allait de quantième à quantième sans retirer la veille : une
période de deux mois ouverte le 1er mars finissait le 1er mai au lieu du
30 avril. Sans données en base, le bug n'a jamais produit d'effet ; il
aurait fait requalifier une rupture notifiée le dernier jour affiché.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2 : Brancher l'existant sur le nouveau calcul

`compute_trial_period_end` est lu par le statut affiché, les relances et le tableau de bord. Il doit rendre la même date que Task 1.

**Files:**
- Modify: `backend/app/modules/employees/domain/trial_period_shared.py:29-50`
- Test: `backend/tests/unit/employees/test_trial_period_shared_dates.py`

**Interfaces:**
- Consumes: `compute_trial_end` (Task 1)
- Produces: `compute_trial_period_end(hire_date_raw, periode_essai) -> date | None`, signature inchangée

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/employees/test_trial_period_shared_dates.py` :

```python
"""compute_trial_period_end doit rendre la même date que le calcul de référence."""

from datetime import date

from app.modules.employees.domain.trial_period_shared import compute_trial_period_end


def test_deux_mois_finissent_la_veille_du_quantieme():
    assert compute_trial_period_end(
        "2026-03-01", {"duree_initiale": 2, "unite": "mois"}
    ) == date(2026, 4, 30)


def test_quantieme_inexistant_va_au_dernier_jour_du_mois():
    assert compute_trial_period_end(
        "2026-01-31", {"duree_initiale": 1, "unite": "mois"}
    ) == date(2026, 2, 28)


def test_jours_comptent_le_jour_d_embauche():
    assert compute_trial_period_end(
        "2026-03-02", {"duree_initiale": 8, "unite": "jours"}
    ) == date(2026, 3, 9)


def test_ancienne_cle_duree_toujours_acceptee():
    assert compute_trial_period_end(
        "2026-03-01", {"duree": 2, "unite": "mois"}
    ) == date(2026, 4, 30)


def test_donnees_absentes():
    assert compute_trial_period_end(None, {"duree_initiale": 2, "unite": "mois"}) is None
    assert compute_trial_period_end("2026-03-01", None) is None
    assert compute_trial_period_end("2026-03-01", {"duree_initiale": 0}) is None
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/employees/test_trial_period_shared_dates.py -v
```

Attendu : les deux premiers tests échouent (`2026-05-01 != 2026-04-30`, `2026-02-28` obtenu par hasard ou non selon le cas), le test `jours` échoue (`2026-03-10 != 2026-03-09`).

- [ ] **Step 3 : réécrire la fonction**

Dans `backend/app/modules/employees/domain/trial_period_shared.py`, remplacer le corps de `compute_trial_period_end` (lignes 29-50) par :

```python
def compute_trial_period_end(
    hire_date_raw: Any,
    periode_essai: Any,
) -> Optional[date]:
    """Fin de période d'essai à partir du jsonb historique.

    Conservée pour les lectures existantes ; le calcul lui-même vit dans
    trial_period_dates, partagé avec la table trial_periods.
    """
    hire = parse_date(hire_date_raw)
    if hire is None or not isinstance(periode_essai, dict):
        return None

    duree_raw = periode_essai.get("duree_initiale", periode_essai.get("duree"))
    try:
        duree = int(duree_raw)
    except (TypeError, ValueError):
        return None

    return compute_trial_end(hire, duree, str(periode_essai.get("unite") or "mois"))
```

Et remplacer l'import `from datetime import date, datetime, timedelta` par `from datetime import date, datetime`, supprimer l'import `relativedelta` devenu inutile, ajouter en tête :

```python
from app.modules.employees.domain.trial_period_dates import compute_trial_end
```

- [ ] **Step 4 : lancer les tests**

```bash
cd backend && python -m pytest tests/unit/employees/ -v
```

Attendu : tous PASSED. Si un test préexistant de `test_trial_period*.py` attend l'ancienne date d'un jour trop tard, corriger **le test** — c'est le comportement attendu qui était faux — et le signaler dans le message de commit.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/modules/employees/domain/trial_period_shared.py backend/tests/unit/employees/
git commit -m "refactor(essai): centraliser le calcul de fin dans trial_period_dates

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3 : Résolution du barème société

**Files:**
- Create: `backend/app/modules/employees/domain/trial_period_bareme.py`
- Test: `backend/tests/unit/employees/test_trial_period_bareme.py`

**Interfaces:**
- Consumes: `UNIT_MONTHS`, `UNIT_DAYS`, `UNIT_WEEKS` (Task 1)
- Produces:
  - `DEFAULT_BAREME: tuple[dict, ...]`
  - `DEFAULT_ALERT_DAYS: int = 15`
  - `DEFAULT_EXCLUDED_CONTRACTS: frozenset[str]`
  - `TrialProposal` (dataclass : `duration_value: int`, `duration_unit: str`, `renewal_allowed: bool`)
  - `resolve_trial_proposal(company_settings: dict, contract_type: str, statut: str, contract_duration_months: float | None = None) -> TrialProposal | None`
  - `resolve_alert_days(company_settings: dict) -> int`

En production il n'existe que quatre combinaisons : CDI Non-Cadre 187, CDD Non-Cadre 26, CDI Cadre 25, Apprentissage 3. La base ne connaît que `Cadre` / `Non-Cadre` : la maîtrise, qui vaut trois mois en droit, est noyée dans les non-cadres et s'ajuste au cas par cas.

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/employees/test_trial_period_bareme.py` :

```python
"""Barème de période d'essai par société, avec repli légal."""

from app.modules.employees.domain.trial_period_bareme import (
    DEFAULT_ALERT_DAYS,
    resolve_alert_days,
    resolve_trial_proposal,
)


def test_cdi_non_cadre_deux_mois_par_defaut():
    p = resolve_trial_proposal({}, "CDI", "Non-Cadre")
    assert (p.duration_value, p.duration_unit, p.renewal_allowed) == (2, "mois", True)


def test_cdi_cadre_quatre_mois_par_defaut():
    p = resolve_trial_proposal({}, "CDI", "Cadre")
    assert (p.duration_value, p.duration_unit) == (4, "mois")


def test_apprentissage_exclu():
    assert resolve_trial_proposal({}, "Apprentissage", "Non-Cadre") is None


def test_stage_exclu():
    assert resolve_trial_proposal({}, "Stage", "Non-Cadre") is None


def test_cdd_court_un_jour_par_semaine_plafonne_a_deux_semaines():
    # Contrat de 4 mois, soit environ 17 semaines : le plafond de 14 jours
    # s'applique.
    p = resolve_trial_proposal({}, "CDD", "Non-Cadre", contract_duration_months=4)
    assert (p.duration_value, p.duration_unit, p.renewal_allowed) == (14, "jours", False)


def test_cdd_tres_court_sous_le_plafond():
    # Contrat de 6 semaines : 6 jours d'essai.
    p = resolve_trial_proposal(
        {}, "CDD", "Non-Cadre", contract_duration_months=6 / 4.348
    )
    assert (p.duration_value, p.duration_unit) == (6, "jours")


def test_cdd_long_un_mois():
    p = resolve_trial_proposal({}, "CDD", "Non-Cadre", contract_duration_months=9)
    assert (p.duration_value, p.duration_unit) == (1, "mois")


def test_cdd_sans_duree_connue_retombe_sur_un_mois():
    p = resolve_trial_proposal({}, "CDD", "Non-Cadre", contract_duration_months=None)
    assert (p.duration_value, p.duration_unit) == (1, "mois")


def test_bareme_societe_surcharge_le_defaut():
    settings = {
        "periode_essai": {
            "bareme": [
                {
                    "contract_type": "CDI",
                    "statut": "Cadre",
                    "duree": 3,
                    "unite": "mois",
                    "renouvellement": False,
                }
            ]
        }
    }
    p = resolve_trial_proposal(settings, "CDI", "Cadre")
    assert (p.duration_value, p.duration_unit, p.renewal_allowed) == (3, "mois", False)
    # Les lignes non surchargées gardent le défaut légal.
    assert resolve_trial_proposal(settings, "CDI", "Non-Cadre").duration_value == 2


def test_exclusions_parametrables():
    settings = {"periode_essai": {"exclusions": ["CDD"]}}
    assert resolve_trial_proposal(settings, "CDD", "Non-Cadre") is None


def test_regle_cdd_desactivable():
    settings = {"periode_essai": {"regle_legale_cdd": False, "bareme": [
        {"contract_type": "CDD", "statut": "Non-Cadre", "duree": 3, "unite": "semaines",
         "renouvellement": False}
    ]}}
    p = resolve_trial_proposal(settings, "CDD", "Non-Cadre", contract_duration_months=4)
    assert (p.duration_value, p.duration_unit) == (3, "semaines")


def test_delai_d_alerte_par_defaut_et_surcharge():
    assert resolve_alert_days({}) == DEFAULT_ALERT_DAYS
    assert resolve_alert_days({"periode_essai": {"alerte_jours": 30}}) == 30
    # Une valeur absurde retombe sur le défaut.
    assert resolve_alert_days({"periode_essai": {"alerte_jours": 0}}) == DEFAULT_ALERT_DAYS
    assert resolve_alert_days({"periode_essai": {"alerte_jours": "trente"}}) == DEFAULT_ALERT_DAYS


def test_casse_et_espaces_ignores():
    p = resolve_trial_proposal({}, "  cdi ", "cadre")
    assert p.duration_value == 4
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/employees/test_trial_period_bareme.py -v
```

Attendu : `ModuleNotFoundError`.

- [ ] **Step 3 : écrire l'implémentation**

Créer `backend/app/modules/employees/domain/trial_period_bareme.py` :

```python
"""Barème de période d'essai : proposition par type de contrat et statut.

Le barème propose, il n'impose pas — la durée reste modifiable salarié par
salarié. Les valeurs par défaut sont les durées légales (L1221-19 pour le CDI,
L1242-10 pour le CDD). La base ne distinguant que Cadre et Non-Cadre, la
maîtrise — trois mois en droit — n'a pas de ligne propre et s'ajuste à la main.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from app.modules.employees.domain.trial_period_dates import (
    UNIT_DAYS,
    UNIT_MONTHS,
)

DEFAULT_ALERT_DAYS = 15

DEFAULT_BAREME: Tuple[Dict[str, Any], ...] = (
    {
        "contract_type": "CDI",
        "statut": "Non-Cadre",
        "duree": 2,
        "unite": UNIT_MONTHS,
        "renouvellement": True,
    },
    {
        "contract_type": "CDI",
        "statut": "Cadre",
        "duree": 4,
        "unite": UNIT_MONTHS,
        "renouvellement": True,
    },
    {
        "contract_type": "CDD",
        "statut": "Non-Cadre",
        "duree": 1,
        "unite": UNIT_MONTHS,
        "renouvellement": False,
    },
    {
        "contract_type": "CDD",
        "statut": "Cadre",
        "duree": 1,
        "unite": UNIT_MONTHS,
        "renouvellement": False,
    },
)

DEFAULT_EXCLUDED_CONTRACTS = frozenset(
    {"apprentissage", "professionnalisation", "stage", "convention de stage"}
)

# Un CDD de six mois ou moins ouvre un jour d'essai par semaine de contrat,
# plafonné à deux semaines (L1242-10).
CDD_SHORT_THRESHOLD_MONTHS = 6
CDD_SHORT_CAP_DAYS = 14
WEEKS_PER_MONTH = 4.348


@dataclass(frozen=True)
class TrialProposal:
    duration_value: int
    duration_unit: str
    renewal_allowed: bool


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _section(company_settings: Any) -> Dict[str, Any]:
    if not isinstance(company_settings, dict):
        return {}
    section = company_settings.get("periode_essai")
    return section if isinstance(section, dict) else {}


def resolve_alert_days(company_settings: Any) -> int:
    raw = _section(company_settings).get("alerte_jours")
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_ALERT_DAYS
    return days if days > 0 else DEFAULT_ALERT_DAYS


def _is_excluded(section: Dict[str, Any], contract_type: str) -> bool:
    raw = section.get("exclusions")
    if isinstance(raw, (list, tuple)):
        excluded = {_norm(x) for x in raw}
    else:
        excluded = set(DEFAULT_EXCLUDED_CONTRACTS)
    return _norm(contract_type) in excluded


def _cdd_proposal(contract_duration_months: Optional[float]) -> TrialProposal:
    if contract_duration_months is None or contract_duration_months > CDD_SHORT_THRESHOLD_MONTHS:
        return TrialProposal(1, UNIT_MONTHS, False)
    weeks = int(contract_duration_months * WEEKS_PER_MONTH)
    days = max(1, min(weeks, CDD_SHORT_CAP_DAYS))
    return TrialProposal(days, UNIT_DAYS, False)


def _find_line(
    section: Dict[str, Any],
    contract_type: str,
    statut: str,
) -> Optional[Dict[str, Any]]:
    custom = section.get("bareme")
    lines = list(custom) if isinstance(custom, (list, tuple)) else []
    lines.extend(DEFAULT_BAREME)
    for line in lines:
        if not isinstance(line, dict):
            continue
        if _norm(line.get("contract_type")) != _norm(contract_type):
            continue
        if _norm(line.get("statut")) != _norm(statut):
            continue
        return line
    return None


def resolve_trial_proposal(
    company_settings: Any,
    contract_type: str,
    statut: str,
    contract_duration_months: Optional[float] = None,
) -> Optional[TrialProposal]:
    """Période d'essai proposée, ou None si le contrat n'en ouvre pas."""
    section = _section(company_settings)

    if _is_excluded(section, contract_type):
        return None

    line = _find_line(section, contract_type, statut)
    if line is None:
        return None

    # La règle légale CDD prime sur la ligne de barème, sauf si la société l'a
    # explicitement désactivée pour saisir une durée fixe.
    if _norm(contract_type) == "cdd" and section.get("regle_legale_cdd", True):
        return _cdd_proposal(contract_duration_months)

    try:
        duree = int(line.get("duree"))
    except (TypeError, ValueError):
        return None
    if duree <= 0:
        return None

    return TrialProposal(
        duration_value=duree,
        duration_unit=str(line.get("unite") or UNIT_MONTHS),
        renewal_allowed=bool(line.get("renouvellement", False)),
    )


__all__ = [
    "DEFAULT_ALERT_DAYS",
    "DEFAULT_BAREME",
    "DEFAULT_EXCLUDED_CONTRACTS",
    "TrialProposal",
    "resolve_alert_days",
    "resolve_trial_proposal",
]
```

- [ ] **Step 4 : lancer le test**

```bash
cd backend && python -m pytest tests/unit/employees/test_trial_period_bareme.py -v
```

Attendu : 13 tests PASSED.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/modules/employees/domain/trial_period_bareme.py backend/tests/unit/employees/test_trial_period_bareme.py
git commit -m "feat(essai): barème de période d'essai paramétrable par société

Durées légales par défaut, surchargeables ligne par ligne dans les
réglages société. Règle CDD du jour par semaine plafonnée à deux
semaines, désactivable.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4 : Migration de la table `trial_periods`

**Files:**
- Create: `supabase/migrations/20260806090000_trial_periods.sql`

**Interfaces:**
- Consumes: rien
- Produces: table `public.trial_periods`

Si l'horodatage `20260806090000` est déjà pris par une autre session, en choisir un plus tardif — il est clé primaire côté CLI Supabase.

- [ ] **Step 1 : écrire la migration**

Créer `supabase/migrations/20260806090000_trial_periods.sql` :

```sql
-- Suivi des périodes d'essai. Remplace employees.periode_essai (jsonb), vide
-- sur les 241 salariés actifs : rien à reprendre.
--
-- end_date est une colonne réelle et non générée : le calcul relève du droit
-- du travail (veille du quantième, dernier jour du mois quand le quantième
-- n'existe pas, prolongation par renouvellement) et vit dans le domaine
-- Python, où il se teste cas par cas.

CREATE TABLE IF NOT EXISTS public.trial_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,

    start_date date NOT NULL,
    duration_value integer NOT NULL,
    duration_unit text NOT NULL DEFAULT 'mois',
    renewal_allowed boolean NOT NULL DEFAULT false,

    renewed_at date,
    renewal_duration_value integer,
    renewal_duration_unit text,
    renewed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,

    end_date date NOT NULL,
    status text NOT NULL DEFAULT 'en_cours',

    confirmed_at timestamptz,
    confirmed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,

    CONSTRAINT trial_periods_duration_positive CHECK (duration_value > 0),
    CONSTRAINT trial_periods_duration_unit_check
        CHECK (duration_unit IN ('jours', 'semaines', 'mois')),
    CONSTRAINT trial_periods_renewal_unit_check
        CHECK (renewal_duration_unit IS NULL
               OR renewal_duration_unit IN ('jours', 'semaines', 'mois')),
    CONSTRAINT trial_periods_renewal_positive
        CHECK (renewal_duration_value IS NULL OR renewal_duration_value > 0),
    CONSTRAINT trial_periods_renewal_complete
        CHECK (num_nulls(renewed_at, renewal_duration_value, renewal_duration_unit) IN (0, 3)),
    CONSTRAINT trial_periods_status_check
        CHECK (status IN ('en_cours', 'confirmee', 'rompue')),
    CONSTRAINT trial_periods_end_after_start CHECK (end_date >= start_date)
);

COMMENT ON TABLE public.trial_periods IS
    'Périodes d''essai : paramétrage, renouvellement effectif et issue.';

COMMENT ON COLUMN public.trial_periods.start_date IS
    'Début de la période, initialisé à la date d''entrée mais modifiable : un contrat peut débuter après l''embauche déclarée.';

COMMENT ON COLUMN public.trial_periods.end_date IS
    'Dernier jour inclus, calculé côté backend. Une rupture notifiée après cette date est hors période d''essai.';

COMMENT ON COLUMN public.trial_periods.renewal_allowed IS
    'Le renouvellement est-il ouvert par la convention : une possibilité, pas une décision.';

COMMENT ON COLUMN public.trial_periods.renewed_at IS
    'Date de la décision de renouvellement, qui doit être notifiée avant le terme initial.';

COMMENT ON COLUMN public.trial_periods.status IS
    'rompue est écrit par le module des sorties (type fin_periode_essai).';

-- Une seule période active par salarié ; une réembauche crée la sienne.
CREATE UNIQUE INDEX IF NOT EXISTS trial_periods_one_active_per_employee
    ON public.trial_periods (employee_id)
    WHERE status = 'en_cours';

CREATE INDEX IF NOT EXISTS trial_periods_company_status_end
    ON public.trial_periods (company_id, status, end_date);

ALTER TABLE public.trial_periods ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS trial_periods_select ON public.trial_periods;
CREATE POLICY trial_periods_select ON public.trial_periods
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

-- Écriture réservée au backend (service_role) : pas de policy INSERT/UPDATE client.
```

- [ ] **Step 2 : appliquer sur l'environnement de test**

Via le workflow dispatchable décrit dans `docs/guide-environnement-test.md` :

```bash
gh workflow run deploy-test-env.yml -f migration=20260806090000_trial_periods.sql
gh run watch
```

Attendu : le run passe au vert.

- [ ] **Step 3 : vérifier la structure sur le test**

Interroger l'environnement de test (MCP `supabase-eywai-test`) :

```sql
select column_name, data_type, is_nullable
from information_schema.columns
where table_name = 'trial_periods' order by ordinal_position;

select polname from pg_policies where tablename = 'trial_periods';

select relrowsecurity from pg_class where relname = 'trial_periods';
```

Attendu : 19 colonnes, une policy `trial_periods_select`, `relrowsecurity = true`.

- [ ] **Step 4 : vérifier que les contraintes mordent**

```sql
-- Doit échouer : durée nulle
insert into trial_periods (company_id, employee_id, start_date, duration_value, end_date)
select company_id, id, '2026-03-01', 0, '2026-04-30' from employees limit 1;
```

Attendu : `violates check constraint "trial_periods_duration_positive"`.

- [ ] **Step 5 : commiter**

```bash
git add supabase/migrations/20260806090000_trial_periods.sql
git commit -m "feat(essai): table trial_periods avec RLS

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5 : Constantes et persistance

**Files:**
- Create: `backend/app/modules/trial_periods/__init__.py`, `domain/__init__.py`, `domain/constants.py`, `infrastructure/__init__.py`, `infrastructure/queries.py`, `infrastructure/repository.py`
- Test: `backend/tests/unit/trial_periods/__init__.py`, `backend/tests/unit/trial_periods/test_constants.py`

**Interfaces:**
- Consumes: `UNIT_DAYS`, `UNIT_WEEKS`, `UNIT_MONTHS` (Task 1)
- Produces:
  - `STATUS_EN_COURS = "en_cours"`, `STATUS_CONFIRMEE = "confirmee"`, `STATUS_ROMPUE = "rompue"`
  - `TABLE_TRIAL_PERIODS = "trial_periods"`
  - `SELECT_TRIAL_WITH_EMPLOYEE: str`
  - `SupabaseTrialPeriodsRepository` avec `create(data) -> dict`, `get_by_id(tp_id) -> dict | None`, `get_active_for_employee(employee_id) -> dict | None`, `update(tp_id, data) -> dict`, `list_for_company(company_id, statuses) -> list[dict]`

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/trial_periods/__init__.py` (vide) et `backend/tests/unit/trial_periods/test_constants.py` :

```python
"""Constantes du module trial_periods, alignées sur les contraintes SQL."""

from app.modules.trial_periods.domain.constants import (
    STATUS_CONFIRMEE,
    STATUS_EN_COURS,
    STATUS_ROMPUE,
    VALID_STATUSES,
)
from app.modules.trial_periods.infrastructure.queries import TABLE_TRIAL_PERIODS


def test_statuts_conformes_a_la_contrainte_sql():
    assert VALID_STATUSES == frozenset({"en_cours", "confirmee", "rompue"})
    assert STATUS_EN_COURS == "en_cours"
    assert STATUS_CONFIRMEE == "confirmee"
    assert STATUS_ROMPUE == "rompue"


def test_nom_de_table():
    assert TABLE_TRIAL_PERIODS == "trial_periods"
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/trial_periods/test_constants.py -v
```

Attendu : `ModuleNotFoundError`.

- [ ] **Step 3 : écrire les modules**

Créer les `__init__.py` vides pour `backend/app/modules/trial_periods/`, `.../domain/`, `.../infrastructure/`, `.../application/`, `.../schemas/`, `.../api/`.

`backend/app/modules/trial_periods/domain/constants.py` :

```python
"""Statuts d'une période d'essai, alignés sur la contrainte CHECK de la table."""

from __future__ import annotations

STATUS_EN_COURS = "en_cours"
STATUS_CONFIRMEE = "confirmee"
STATUS_ROMPUE = "rompue"

VALID_STATUSES = frozenset({STATUS_EN_COURS, STATUS_CONFIRMEE, STATUS_ROMPUE})

__all__ = [
    "STATUS_CONFIRMEE",
    "STATUS_EN_COURS",
    "STATUS_ROMPUE",
    "VALID_STATUSES",
]
```

`backend/app/modules/trial_periods/infrastructure/queries.py` :

```python
"""Table et projections des périodes d'essai."""

from __future__ import annotations

TABLE_TRIAL_PERIODS = "trial_periods"

SELECT_TRIAL_WITH_EMPLOYEE = (
    "*, employee:employees(id, first_name, last_name, hire_date, "
    "contract_type, statut, employment_status)"
)

__all__ = ["SELECT_TRIAL_WITH_EMPLOYEE", "TABLE_TRIAL_PERIODS"]
```

`backend/app/modules/trial_periods/infrastructure/repository.py` :

```python
"""Persistance des périodes d'essai via Supabase."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from app.core.database import supabase
from app.modules.trial_periods.domain.constants import STATUS_EN_COURS
from app.modules.trial_periods.infrastructure.queries import (
    SELECT_TRIAL_WITH_EMPLOYEE,
    TABLE_TRIAL_PERIODS,
)


def _attach_employee_name(row: Dict[str, Any]) -> Dict[str, Any]:
    employee = row.pop("employee", None) or {}
    if employee:
        first = employee.get("first_name") or ""
        last = employee.get("last_name") or ""
        row["employee_name"] = f"{first} {last}".strip() or None
        row["hire_date"] = employee.get("hire_date")
        row["contract_type"] = employee.get("contract_type")
        row["statut"] = employee.get("statut")
    return row


class SupabaseTrialPeriodsRepository:
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        res = supabase.table(TABLE_TRIAL_PERIODS).insert(data).execute()
        if not res.data:
            raise RuntimeError("Insert trial_periods sans données retournées")
        return res.data[0]

    def get_by_id(self, trial_period_id: str) -> Optional[Dict[str, Any]]:
        res = (
            supabase.table(TABLE_TRIAL_PERIODS)
            .select(SELECT_TRIAL_WITH_EMPLOYEE)
            .eq("id", trial_period_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return _attach_employee_name(dict(rows[0])) if rows else None

    def get_active_for_employee(self, employee_id: str) -> Optional[Dict[str, Any]]:
        res = (
            supabase.table(TABLE_TRIAL_PERIODS)
            .select(SELECT_TRIAL_WITH_EMPLOYEE)
            .eq("employee_id", employee_id)
            .eq("status", STATUS_EN_COURS)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return _attach_employee_name(dict(rows[0])) if rows else None

    def update(self, trial_period_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "updated_at": datetime.now(timezone.utc).isoformat()}
        res = (
            supabase.table(TABLE_TRIAL_PERIODS)
            .update(payload)
            .eq("id", trial_period_id)
            .execute()
        )
        if not res.data:
            raise RuntimeError(f"Période d'essai {trial_period_id} introuvable")
        return res.data[0]

    def list_for_company(
        self,
        company_id: str,
        statuses: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            supabase.table(TABLE_TRIAL_PERIODS)
            .select(SELECT_TRIAL_WITH_EMPLOYEE)
            .eq("company_id", company_id)
        )
        if statuses:
            query = query.in_("status", list(statuses))
        res = query.order("end_date").execute()
        return [_attach_employee_name(dict(row)) for row in (res.data or [])]


repository = SupabaseTrialPeriodsRepository()

__all__ = ["SupabaseTrialPeriodsRepository", "repository"]
```

- [ ] **Step 4 : lancer le test**

```bash
cd backend && python -m pytest tests/unit/trial_periods/ -v
```

Attendu : 2 tests PASSED.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/modules/trial_periods/ backend/tests/unit/trial_periods/
git commit -m "feat(essai): persistance des périodes d'essai

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6 : Commandes applicatives

**Files:**
- Create: `backend/app/modules/trial_periods/application/commands.py`
- Test: `backend/tests/unit/trial_periods/test_commands.py`

**Interfaces:**
- Consumes: `compute_trial_end` (Task 1), `resolve_trial_proposal` (Task 3), `repository` (Task 5)
- Produces:
  - `build_create_payload(company_id, employee_id, start_date, duration_value, duration_unit, renewal_allowed, created_by) -> dict`
  - `build_renewal_payload(trial_period: dict, renewed_at: date, renewal_duration_value: int, renewal_duration_unit: str, renewed_by: str) -> dict`
  - `build_confirm_payload(confirmed_by: str) -> dict`
  - `create_trial_period(...)`, `update_trial_period(...)`, `confirm_trial_period(...)`, `renew_trial_period(...)`

Les fonctions `build_*` sont pures et portent la logique testée ; les fonctions d'écriture les enchaînent avec le repository.

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/trial_periods/test_commands.py` :

```python
"""Construction des payloads de période d'essai."""

from datetime import date

import pytest

from app.modules.trial_periods.application.commands import (
    build_confirm_payload,
    build_create_payload,
    build_renewal_payload,
)
from app.modules.trial_periods.domain.constants import STATUS_CONFIRMEE


def test_creation_calcule_la_date_de_fin():
    payload = build_create_payload(
        company_id="c1",
        employee_id="e1",
        start_date=date(2026, 3, 1),
        duration_value=2,
        duration_unit="mois",
        renewal_allowed=True,
        created_by="u1",
    )
    assert payload["end_date"] == "2026-04-30"
    assert payload["status"] == "en_cours"
    assert payload["start_date"] == "2026-03-01"
    assert payload["renewal_allowed"] is True
    assert payload["created_by"] == "u1"


def test_creation_refuse_une_duree_inexploitable():
    with pytest.raises(ValueError, match="durée"):
        build_create_payload(
            company_id="c1",
            employee_id="e1",
            start_date=date(2026, 3, 1),
            duration_value=0,
            duration_unit="mois",
            renewal_allowed=False,
            created_by="u1",
        )


def test_renouvellement_repousse_la_fin():
    trial = {
        "start_date": "2026-03-01",
        "duration_value": 2,
        "duration_unit": "mois",
        "renewal_allowed": True,
        "renewed_at": None,
    }
    payload = build_renewal_payload(
        trial,
        renewed_at=date(2026, 4, 20),
        renewal_duration_value=2,
        renewal_duration_unit="mois",
        renewed_by="u1",
    )
    assert payload["end_date"] == "2026-06-30"
    assert payload["renewed_at"] == "2026-04-20"
    assert payload["renewal_duration_value"] == 2
    assert payload["renewed_by"] == "u1"


def test_renouvellement_refuse_si_la_convention_ne_l_ouvre_pas():
    trial = {
        "start_date": "2026-03-01",
        "duration_value": 2,
        "duration_unit": "mois",
        "renewal_allowed": False,
        "renewed_at": None,
    }
    with pytest.raises(ValueError, match="renouvellement"):
        build_renewal_payload(
            trial,
            renewed_at=date(2026, 4, 20),
            renewal_duration_value=2,
            renewal_duration_unit="mois",
            renewed_by="u1",
        )


def test_renouvellement_refuse_une_seconde_fois():
    trial = {
        "start_date": "2026-03-01",
        "duration_value": 2,
        "duration_unit": "mois",
        "renewal_allowed": True,
        "renewed_at": "2026-04-20",
    }
    with pytest.raises(ValueError, match="déjà"):
        build_renewal_payload(
            trial,
            renewed_at=date(2026, 4, 25),
            renewal_duration_value=1,
            renewal_duration_unit="mois",
            renewed_by="u1",
        )


def test_renouvellement_refuse_apres_le_terme():
    # Le renouvellement doit être notifié avant la fin de la période initiale.
    trial = {
        "start_date": "2026-03-01",
        "duration_value": 2,
        "duration_unit": "mois",
        "renewal_allowed": True,
        "renewed_at": None,
    }
    with pytest.raises(ValueError, match="terme"):
        build_renewal_payload(
            trial,
            renewed_at=date(2026, 5, 2),
            renewal_duration_value=2,
            renewal_duration_unit="mois",
            renewed_by="u1",
        )


def test_confirmation():
    payload = build_confirm_payload("u1")
    assert payload["status"] == STATUS_CONFIRMEE
    assert payload["confirmed_by"] == "u1"
    assert payload["confirmed_at"]
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/trial_periods/test_commands.py -v
```

Attendu : `ModuleNotFoundError`.

- [ ] **Step 3 : écrire l'implémentation**

Créer `backend/app/modules/trial_periods/application/commands.py` :

```python
"""Écriture des périodes d'essai."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from app.modules.employees.domain.trial_period_dates import compute_trial_end
from app.modules.employees.domain.trial_period_shared import parse_date
from app.modules.trial_periods.domain.constants import (
    STATUS_CONFIRMEE,
    STATUS_EN_COURS,
)
from app.modules.trial_periods.infrastructure.repository import repository


def build_create_payload(
    company_id: str,
    employee_id: str,
    start_date: date,
    duration_value: int,
    duration_unit: str,
    renewal_allowed: bool,
    created_by: Optional[str],
) -> Dict[str, Any]:
    end = compute_trial_end(start_date, duration_value, duration_unit)
    if end is None:
        raise ValueError("durée de période d'essai inexploitable")

    return {
        "company_id": company_id,
        "employee_id": employee_id,
        "start_date": start_date.isoformat(),
        "duration_value": int(duration_value),
        "duration_unit": duration_unit,
        "renewal_allowed": bool(renewal_allowed),
        "end_date": end.isoformat(),
        "status": STATUS_EN_COURS,
        "created_by": created_by,
    }


def build_renewal_payload(
    trial_period: Dict[str, Any],
    renewed_at: date,
    renewal_duration_value: int,
    renewal_duration_unit: str,
    renewed_by: Optional[str],
) -> Dict[str, Any]:
    if not trial_period.get("renewal_allowed"):
        raise ValueError("le renouvellement n'est pas ouvert pour cette période")
    if trial_period.get("renewed_at"):
        raise ValueError("période déjà renouvelée : la loi n'en autorise qu'un")

    start = parse_date(trial_period.get("start_date"))
    if start is None:
        raise ValueError("date de début illisible")

    initial_end = compute_trial_end(
        start,
        trial_period.get("duration_value"),
        trial_period.get("duration_unit"),
    )
    if initial_end is None:
        raise ValueError("durée de période d'essai inexploitable")

    # Le renouvellement doit être notifié avant le terme initial, sans quoi il
    # est inopposable et le contrat est définitivement conclu.
    if renewed_at > initial_end:
        raise ValueError("renouvellement notifié après le terme de la période")

    end = compute_trial_end(
        start,
        trial_period.get("duration_value"),
        trial_period.get("duration_unit"),
        renewal_value=renewal_duration_value,
        renewal_unit=renewal_duration_unit,
    )
    if end is None:
        raise ValueError("durée de renouvellement inexploitable")

    return {
        "renewed_at": renewed_at.isoformat(),
        "renewal_duration_value": int(renewal_duration_value),
        "renewal_duration_unit": renewal_duration_unit,
        "renewed_by": renewed_by,
        "end_date": end.isoformat(),
    }


def build_confirm_payload(confirmed_by: Optional[str]) -> Dict[str, Any]:
    return {
        "status": STATUS_CONFIRMEE,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "confirmed_by": confirmed_by,
    }


def build_update_payload(
    trial_period: Dict[str, Any],
    start_date: Optional[date],
    duration_value: Optional[int],
    duration_unit: Optional[str],
    renewal_allowed: Optional[bool],
) -> Dict[str, Any]:
    start = start_date or parse_date(trial_period.get("start_date"))
    if start is None:
        raise ValueError("date de début illisible")
    value = duration_value if duration_value is not None else trial_period.get("duration_value")
    unit = duration_unit or trial_period.get("duration_unit")

    end = compute_trial_end(
        start,
        value,
        unit,
        renewal_value=trial_period.get("renewal_duration_value"),
        renewal_unit=trial_period.get("renewal_duration_unit"),
    )
    if end is None:
        raise ValueError("durée de période d'essai inexploitable")

    payload: Dict[str, Any] = {
        "start_date": start.isoformat(),
        "duration_value": int(value),
        "duration_unit": unit,
        "end_date": end.isoformat(),
    }
    if renewal_allowed is not None:
        payload["renewal_allowed"] = bool(renewal_allowed)
    return payload


def create_trial_period(**kwargs: Any) -> Dict[str, Any]:
    return repository.create(build_create_payload(**kwargs))


def update_trial_period(
    trial_period_id: str,
    start_date: Optional[date] = None,
    duration_value: Optional[int] = None,
    duration_unit: Optional[str] = None,
    renewal_allowed: Optional[bool] = None,
) -> Dict[str, Any]:
    current = repository.get_by_id(trial_period_id)
    if current is None:
        raise ValueError("période d'essai introuvable")
    payload = build_update_payload(
        current, start_date, duration_value, duration_unit, renewal_allowed
    )
    return repository.update(trial_period_id, payload)


def confirm_trial_period(trial_period_id: str, confirmed_by: Optional[str]) -> Dict[str, Any]:
    return repository.update(trial_period_id, build_confirm_payload(confirmed_by))


def renew_trial_period(
    trial_period_id: str,
    renewed_at: date,
    renewal_duration_value: int,
    renewal_duration_unit: str,
    renewed_by: Optional[str],
) -> Dict[str, Any]:
    current = repository.get_by_id(trial_period_id)
    if current is None:
        raise ValueError("période d'essai introuvable")
    payload = build_renewal_payload(
        current, renewed_at, renewal_duration_value, renewal_duration_unit, renewed_by
    )
    return repository.update(trial_period_id, payload)


__all__ = [
    "build_confirm_payload",
    "build_create_payload",
    "build_renewal_payload",
    "build_update_payload",
    "confirm_trial_period",
    "create_trial_period",
    "renew_trial_period",
    "update_trial_period",
]
```

- [ ] **Step 4 : lancer le test**

```bash
cd backend && python -m pytest tests/unit/trial_periods/ -v
```

Attendu : 9 tests PASSED.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/modules/trial_periods/application/commands.py backend/tests/unit/trial_periods/test_commands.py
git commit -m "feat(essai): commandes de création, confirmation et renouvellement

Le renouvellement est refusé après le terme initial : notifié trop tard,
il est inopposable et le contrat est définitivement conclu.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7 : Requêtes de la page de suivi

**Files:**
- Create: `backend/app/modules/trial_periods/application/queries.py`
- Test: `backend/tests/unit/trial_periods/test_queries.py`

**Interfaces:**
- Consumes: `repository` (Task 5), `resolve_alert_days` (Task 3), `STATUS_EN_COURS` (Task 5)
- Produces:
  - `TO_QUALIFY_WINDOW_DAYS: int = 240`
  - `split_sections(trials: list[dict], alert_days: int, reference: date) -> dict` avec les clés `en_cours`, `a_confirmer`
  - `select_to_qualify(employees: list[dict], covered_ids: set[str], reference: date) -> list[dict]`

Le seuil de qualification est de huit mois (240 jours) : c'est la durée maximale légale d'une période d'essai, cadre renouvelé une fois. Au-delà il n'y a plus rien à suivre.

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/trial_periods/test_queries.py` :

```python
"""Répartition des périodes d'essai en sections de suivi."""

from datetime import date

from app.modules.trial_periods.application.queries import (
    select_to_qualify,
    split_sections,
)

REF = date(2026, 8, 5)


def _trial(end: str, status: str = "en_cours"):
    return {"id": f"tp-{end}", "end_date": end, "status": status}


def test_en_cours_et_a_confirmer_separes_par_le_delai_d_alerte():
    trials = [
        _trial("2026-12-31"),  # loin
        _trial("2026-08-15"),  # dans 10 jours, sous l'alerte de 15
        _trial("2026-07-01"),  # dépassée
    ]
    sections = split_sections(trials, alert_days=15, reference=REF)
    assert [t["end_date"] for t in sections["en_cours"]] == ["2026-12-31"]
    assert [t["end_date"] for t in sections["a_confirmer"]] == ["2026-07-01", "2026-08-15"]


def test_le_delai_d_alerte_est_inclusif():
    sections = split_sections([_trial("2026-08-20")], alert_days=15, reference=REF)
    assert len(sections["a_confirmer"]) == 1


def test_les_periodes_closes_sont_ecartees():
    trials = [_trial("2026-07-01", status="confirmee"), _trial("2026-07-02", status="rompue")]
    sections = split_sections(trials, alert_days=15, reference=REF)
    assert sections["en_cours"] == []
    assert sections["a_confirmer"] == []


def test_a_qualifier_ne_retient_que_les_embauches_recentes_sans_periode():
    employees = [
        {"id": "e1", "hire_date": "2026-07-01", "employment_status": "actif"},
        {"id": "e2", "hire_date": "2020-01-01", "employment_status": "actif"},
        {"id": "e3", "hire_date": "2026-06-01", "employment_status": "actif"},
        {"id": "e4", "hire_date": "2026-07-15", "employment_status": "en_sortie"},
        {"id": "e5", "hire_date": None, "employment_status": "actif"},
    ]
    result = select_to_qualify(employees, covered_ids={"e3"}, reference=REF)
    assert [e["id"] for e in result] == ["e1"]


def test_a_qualifier_prend_en_onboarding():
    employees = [{"id": "e1", "hire_date": "2026-07-01", "employment_status": "en_onboarding"}]
    assert [e["id"] for e in select_to_qualify(employees, set(), REF)] == ["e1"]


def test_a_qualifier_borne_a_huit_mois():
    # 240 jours avant le 5 août 2026 : le 8 décembre 2025.
    employees = [
        {"id": "dedans", "hire_date": "2025-12-10", "employment_status": "actif"},
        {"id": "dehors", "hire_date": "2025-12-01", "employment_status": "actif"},
    ]
    assert [e["id"] for e in select_to_qualify(employees, set(), REF)] == ["dedans"]
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/trial_periods/test_queries.py -v
```

Attendu : `ModuleNotFoundError`.

- [ ] **Step 3 : écrire l'implémentation**

Créer `backend/app/modules/trial_periods/application/queries.py` :

```python
"""Lectures des périodes d'essai pour la page de suivi."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Set

from app.core.database import supabase
from app.modules.employees.domain.trial_period_bareme import resolve_alert_days
from app.modules.employees.domain.trial_period_shared import parse_date
from app.modules.trial_periods.domain.constants import STATUS_EN_COURS
from app.modules.trial_periods.infrastructure.repository import repository

# Huit mois : la durée maximale légale d'une période d'essai, cadre renouvelé
# une fois. Au-delà, il n'y a plus rien à qualifier.
TO_QUALIFY_WINDOW_DAYS = 240

_TRACKED_STATUSES = frozenset({"actif", "en_onboarding"})


def split_sections(
    trials: Iterable[Dict[str, Any]],
    alert_days: int,
    reference: date,
) -> Dict[str, List[Dict[str, Any]]]:
    """Sépare les périodes actives entre « en cours » et « à confirmer »."""
    en_cours: List[Dict[str, Any]] = []
    a_confirmer: List[Dict[str, Any]] = []

    for trial in trials:
        if str(trial.get("status") or "") != STATUS_EN_COURS:
            continue
        end = parse_date(trial.get("end_date"))
        if end is None:
            continue
        if (end - reference).days <= alert_days:
            a_confirmer.append(trial)
        else:
            en_cours.append(trial)

    key = lambda t: str(t.get("end_date") or "")  # noqa: E731
    return {"en_cours": sorted(en_cours, key=key), "a_confirmer": sorted(a_confirmer, key=key)}


def select_to_qualify(
    employees: Iterable[Dict[str, Any]],
    covered_ids: Set[str],
    reference: date,
) -> List[Dict[str, Any]]:
    """Salariés actifs récemment embauchés et sans période d'essai."""
    out: List[Dict[str, Any]] = []
    for emp in employees:
        if str(emp.get("employment_status") or "").strip().lower() not in _TRACKED_STATUSES:
            continue
        if str(emp.get("id") or "") in covered_ids:
            continue
        hire = parse_date(emp.get("hire_date"))
        if hire is None:
            continue
        if (reference - hire).days > TO_QUALIFY_WINDOW_DAYS:
            continue
        out.append(emp)
    return sorted(out, key=lambda e: str(e.get("hire_date") or ""), reverse=True)


def fetch_company_settings(company_id: str) -> Dict[str, Any]:
    res = (
        supabase.table("companies")
        .select("settings")
        .eq("id", company_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    settings = rows[0].get("settings") if rows else None
    return settings if isinstance(settings, dict) else {}


def fetch_employees(company_id: str) -> List[Dict[str, Any]]:
    res = (
        supabase.table("employees")
        .select("id, first_name, last_name, hire_date, contract_type, statut, "
                "employment_status, contract_end_date")
        .eq("company_id", company_id)
        .execute()
    )
    return list(res.data or [])


def get_tracking_page(
    company_id: str,
    reference: Optional[date] = None,
) -> Dict[str, Any]:
    """Les trois sections de la page de suivi."""
    ref = reference or date.today()
    settings = fetch_company_settings(company_id)
    alert_days = resolve_alert_days(settings)

    trials = repository.list_for_company(company_id)
    sections = split_sections(trials, alert_days, ref)

    covered = {str(t.get("employee_id")) for t in trials if t.get("status") == STATUS_EN_COURS}
    to_qualify = select_to_qualify(fetch_employees(company_id), covered, ref)

    return {
        "alert_days": alert_days,
        "en_cours": sections["en_cours"],
        "a_confirmer": sections["a_confirmer"],
        "a_qualifier": to_qualify,
    }


__all__ = [
    "TO_QUALIFY_WINDOW_DAYS",
    "fetch_company_settings",
    "fetch_employees",
    "get_tracking_page",
    "select_to_qualify",
    "split_sections",
]
```

- [ ] **Step 4 : lancer le test**

```bash
cd backend && python -m pytest tests/unit/trial_periods/ -v
```

Attendu : 15 tests PASSED.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/modules/trial_periods/application/queries.py backend/tests/unit/trial_periods/test_queries.py
git commit -m "feat(essai): sections de la page de suivi

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8 : Schémas et routes

**Files:**
- Create: `backend/app/modules/trial_periods/schemas/requests.py`, `schemas/responses.py`, `api/router.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/unit/trial_periods/test_schemas.py`

**Interfaces:**
- Consumes: commandes (Task 6), requêtes (Task 7), `VALID_STATUSES` (Task 5)
- Produces: routes `GET /api/trial-periods/tracking`, `POST /api/trial-periods`, `PATCH /api/trial-periods/{id}`, `POST /api/trial-periods/{id}/confirm`, `POST /api/trial-periods/{id}/renew`

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/trial_periods/test_schemas.py` :

```python
"""Validation des entrées d'API."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.trial_periods.schemas.requests import (
    TrialPeriodCreate,
    TrialPeriodRenew,
    TrialPeriodUpdate,
)


def test_creation_valide():
    body = TrialPeriodCreate(
        employee_id="e1",
        start_date=date(2026, 3, 1),
        duration_value=2,
        duration_unit="mois",
        renewal_allowed=True,
    )
    assert body.duration_unit == "mois"


def test_creation_refuse_une_unite_inconnue():
    with pytest.raises(ValidationError):
        TrialPeriodCreate(
            employee_id="e1",
            start_date=date(2026, 3, 1),
            duration_value=2,
            duration_unit="trimestres",
            renewal_allowed=False,
        )


def test_creation_refuse_une_duree_nulle():
    with pytest.raises(ValidationError):
        TrialPeriodCreate(
            employee_id="e1",
            start_date=date(2026, 3, 1),
            duration_value=0,
            duration_unit="mois",
            renewal_allowed=False,
        )


def test_mise_a_jour_partielle():
    body = TrialPeriodUpdate(duration_value=3)
    assert body.duration_unit is None
    assert body.duration_value == 3


def test_renouvellement_exige_ses_trois_champs():
    body = TrialPeriodRenew(
        renewed_at=date(2026, 4, 20), duration_value=2, duration_unit="mois"
    )
    assert body.duration_value == 2
    with pytest.raises(ValidationError):
        TrialPeriodRenew(renewed_at=date(2026, 4, 20), duration_value=2)
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/trial_periods/test_schemas.py -v
```

Attendu : `ModuleNotFoundError`.

- [ ] **Step 3 : écrire les schémas et le routeur**

`backend/app/modules/trial_periods/schemas/requests.py` :

```python
"""Entrées d'API des périodes d'essai."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

TrialUnit = Literal["jours", "semaines", "mois"]


class TrialPeriodCreate(BaseModel):
    employee_id: str
    start_date: date
    duration_value: int = Field(gt=0)
    duration_unit: TrialUnit = "mois"
    renewal_allowed: bool = False


class TrialPeriodUpdate(BaseModel):
    start_date: Optional[date] = None
    duration_value: Optional[int] = Field(default=None, gt=0)
    duration_unit: Optional[TrialUnit] = None
    renewal_allowed: Optional[bool] = None


class TrialPeriodRenew(BaseModel):
    renewed_at: date
    duration_value: int = Field(gt=0)
    duration_unit: TrialUnit


class TrialPeriodApplyBareme(BaseModel):
    employee_ids: list[str] = Field(min_length=1)
```

`backend/app/modules/trial_periods/schemas/responses.py` :

```python
"""Sorties d'API des périodes d'essai."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class TrialPeriod(BaseModel):
    id: str
    company_id: str
    employee_id: str
    employee_name: Optional[str] = None
    start_date: date
    duration_value: int
    duration_unit: str
    renewal_allowed: bool
    renewed_at: Optional[date] = None
    renewal_duration_value: Optional[int] = None
    renewal_duration_unit: Optional[str] = None
    end_date: date
    status: str
    confirmed_at: Optional[datetime] = None
    hire_date: Optional[date] = None
    contract_type: Optional[str] = None
    statut: Optional[str] = None


class TrialPeriodTracking(BaseModel):
    alert_days: int
    en_cours: List[TrialPeriod]
    a_confirmer: List[TrialPeriod]
    a_qualifier: List[Dict[str, Any]]
```

`backend/app/modules/trial_periods/api/router.py` :

```python
"""API des périodes d'essai."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.employees.domain.trial_period_bareme import resolve_trial_proposal
from app.modules.trial_periods.application import commands, queries
from app.modules.trial_periods.infrastructure.repository import repository
from app.modules.trial_periods.schemas.requests import (
    TrialPeriodApplyBareme,
    TrialPeriodCreate,
    TrialPeriodRenew,
    TrialPeriodUpdate,
)
from app.modules.trial_periods.schemas.responses import TrialPeriodTracking
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/trial-periods", tags=["TrialPeriods"])

_RH_ROLES = {"admin", "rh", "collaborateur_rh", "super_admin"}


def _require_rh(user: User) -> None:
    if str(getattr(user, "role", "")).strip().lower() not in _RH_ROLES:
        raise HTTPException(status_code=403, detail="Accès réservé aux profils RH")


def _company_id(user: User) -> str:
    company_id = getattr(user, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=400, detail="Société active introuvable")
    return str(company_id)


@router.get("/tracking", response_model=TrialPeriodTracking)
def get_tracking(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    _require_rh(current_user)
    return queries.get_tracking_page(_company_id(current_user))


@router.post("")
def create(
    body: TrialPeriodCreate,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_rh(current_user)
    try:
        return commands.create_trial_period(
            company_id=_company_id(current_user),
            employee_id=body.employee_id,
            start_date=body.start_date,
            duration_value=body.duration_value,
            duration_unit=body.duration_unit,
            renewal_allowed=body.renewal_allowed,
            created_by=str(getattr(current_user, "id", "") or "") or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{trial_period_id}")
def update(
    trial_period_id: str,
    body: TrialPeriodUpdate,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_rh(current_user)
    try:
        return commands.update_trial_period(
            trial_period_id,
            start_date=body.start_date,
            duration_value=body.duration_value,
            duration_unit=body.duration_unit,
            renewal_allowed=body.renewal_allowed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{trial_period_id}/confirm")
def confirm(
    trial_period_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_rh(current_user)
    return commands.confirm_trial_period(
        trial_period_id, str(getattr(current_user, "id", "") or "") or None
    )


@router.post("/{trial_period_id}/renew")
def renew(
    trial_period_id: str,
    body: TrialPeriodRenew,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_rh(current_user)
    try:
        return commands.renew_trial_period(
            trial_period_id,
            renewed_at=body.renewed_at,
            renewal_duration_value=body.duration_value,
            renewal_duration_unit=body.duration_unit,
            renewed_by=str(getattr(current_user, "id", "") or "") or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/apply-bareme")
def apply_bareme(
    body: TrialPeriodApplyBareme,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Crée les périodes d'essai proposées par le barème, sans écraser l'existant."""
    _require_rh(current_user)
    company_id = _company_id(current_user)
    user_id = str(getattr(current_user, "id", "") or "") or None

    settings = queries.fetch_company_settings(company_id)
    employees = {str(e["id"]): e for e in queries.fetch_employees(company_id)}

    created: List[str] = []
    skipped: List[Dict[str, str]] = []
    for employee_id in body.employee_ids:
        emp = employees.get(employee_id)
        if emp is None:
            skipped.append({"employee_id": employee_id, "raison": "salarié introuvable"})
            continue
        if repository.get_active_for_employee(employee_id):
            skipped.append({"employee_id": employee_id, "raison": "période déjà active"})
            continue
        hire = emp.get("hire_date")
        if not hire:
            skipped.append({"employee_id": employee_id, "raison": "date d'entrée manquante"})
            continue
        proposal = resolve_trial_proposal(
            settings,
            str(emp.get("contract_type") or ""),
            str(emp.get("statut") or ""),
            _contract_duration_months(emp),
        )
        if proposal is None:
            skipped.append({"employee_id": employee_id, "raison": "contrat sans période d'essai"})
            continue
        commands.create_trial_period(
            company_id=company_id,
            employee_id=employee_id,
            start_date=date.fromisoformat(str(hire)[:10]),
            duration_value=proposal.duration_value,
            duration_unit=proposal.duration_unit,
            renewal_allowed=proposal.renewal_allowed,
            created_by=user_id,
        )
        created.append(employee_id)

    return {"created": created, "skipped": skipped}


def _contract_duration_months(employee: Dict[str, Any]) -> float | None:
    hire = employee.get("hire_date")
    end = employee.get("contract_end_date")
    if not hire or not end:
        return None
    try:
        d1 = date.fromisoformat(str(hire)[:10])
        d2 = date.fromisoformat(str(end)[:10])
    except ValueError:
        return None
    return max(0.0, (d2 - d1).days / 30.44)
```

Dans `backend/app/api/router.py`, ajouter l'import à côté des autres et l'inclusion à côté des autres `include_router` :

```python
from app.modules.trial_periods.api.router import router as trial_periods_router
```

```python
router.include_router(trial_periods_router)
```

- [ ] **Step 4 : lancer les tests et vérifier que l'application démarre**

```bash
cd backend && python -m pytest tests/unit/trial_periods/ -v && python -c "from app.main import app; print(len(app.routes), 'routes')"
```

Attendu : 20 tests PASSED, puis le nombre de routes affiché sans erreur d'import.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/modules/trial_periods/ backend/app/api/router.py backend/tests/unit/trial_periods/test_schemas.py
git commit -m "feat(essai): API des périodes d'essai

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9 : Alimenter les relances et le tableau de bord

Les relances et le badge lisent aujourd'hui `employees.periode_essai`. Elles doivent lire la table, et le délai d'alerte devient celui du barème société.

**Files:**
- Modify: `backend/app/modules/employees/domain/deadline_reminders.py:76-81,106`
- Modify: `backend/app/modules/notifications/application/hr_deadline_reminders.py:29-39`
- Test: `backend/tests/unit/employees/test_deadline_reminders_trial.py`

**Interfaces:**
- Consumes: `TABLE_TRIAL_PERIODS` (Task 5), `resolve_alert_days` (Task 3)
- Produces: `_trial_deadline` lit `emp["trial_period"]`, dictionnaire joint par la couche infrastructure

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/employees/test_deadline_reminders_trial.py` :

```python
"""Les relances de période d'essai lisent la table, plus le jsonb."""

from datetime import date

from app.modules.employees.domain.deadline_reminders import (
    REMINDER_TYPE_TRIAL,
    list_hr_deadline_candidates,
)

REF = date(2026, 8, 5)


def _employee(trial):
    return {
        "id": "e1",
        "first_name": "Alex",
        "last_name": "Martin",
        "employment_status": "actif",
        "hire_date": "2026-06-01",
        "trial_period": trial,
    }


def test_periode_active_dans_la_fenetre_declenche_une_relance():
    emp = _employee({"end_date": "2026-08-15", "status": "en_cours"})
    candidates = list_hr_deadline_candidates([emp], reference_date=REF)
    trials = [c for c in candidates if c.reminder_type == REMINDER_TYPE_TRIAL]
    assert len(trials) == 1
    assert trials[0].deadline == date(2026, 8, 15)


def test_periode_confirmee_ne_declenche_rien():
    emp = _employee({"end_date": "2026-08-15", "status": "confirmee"})
    candidates = list_hr_deadline_candidates([emp], reference_date=REF)
    assert [c for c in candidates if c.reminder_type == REMINDER_TYPE_TRIAL] == []


def test_periode_rompue_ne_declenche_rien():
    emp = _employee({"end_date": "2026-08-15", "status": "rompue"})
    candidates = list_hr_deadline_candidates([emp], reference_date=REF)
    assert [c for c in candidates if c.reminder_type == REMINDER_TYPE_TRIAL] == []


def test_absence_de_periode_ne_declenche_rien():
    emp = _employee(None)
    candidates = list_hr_deadline_candidates([emp], reference_date=REF)
    assert [c for c in candidates if c.reminder_type == REMINDER_TYPE_TRIAL] == []
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/employees/test_deadline_reminders_trial.py -v
```

Attendu : le premier test échoue — `_trial_deadline` lit encore `periode_essai`.

- [ ] **Step 3 : modifier la lecture**

Dans `backend/app/modules/employees/domain/deadline_reminders.py`, remplacer `_trial_deadline` :

```python
def _trial_deadline(emp: Dict[str, Any]) -> Optional[date]:
    """Fin de la période d'essai active, jointe depuis la table trial_periods."""
    trial = emp.get("trial_period")
    if not isinstance(trial, dict):
        return None
    if str(trial.get("status") or "") != "en_cours":
        return None
    return parse_date(trial.get("end_date"))
```

Supprimer l'import local de `is_trial_eligible_for_reminder` devenu inutile dans cette fonction.

Dans `backend/app/modules/notifications/application/hr_deadline_reminders.py`, remplacer la projection de `fetch_employees_for_hr_deadline_reminders` :

```python
        .select(
            "id, first_name, last_name, employment_status, contract_type, "
            "contract_end_date, hire_date, "
            "is_subject_to_residence_permit, residence_permit_expiry_date, "
            "trial_period:trial_periods(end_date, status)"
        )
```

Supabase renvoie une liste pour une relation inverse : normaliser juste après la requête, avant le `return` :

```python
    rows = list(resp.data or [])
    for row in rows:
        trials = row.get("trial_period")
        if isinstance(trials, list):
            active = [t for t in trials if t.get("status") == "en_cours"]
            row["trial_period"] = active[0] if active else None
    return rows
```

- [ ] **Step 4 : lancer les tests**

```bash
cd backend && python -m pytest tests/unit/employees/ tests/unit/notifications/ -v
```

Attendu : tous PASSED. Corriger les tests préexistants qui construisaient un `periode_essai` jsonb pour piloter une relance : ils doivent désormais passer `trial_period`.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/modules/employees/domain/deadline_reminders.py backend/app/modules/notifications/application/hr_deadline_reminders.py backend/tests/unit/
git commit -m "feat(essai): relances alimentées par la table trial_periods

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10 : Statut enrichi de la fiche salarié

`calculate_trial_period_status` alimente le badge d'en-tête, la colonne « Essai J-x » et le filtre `trial_ending`. Il doit lire la table.

**Files:**
- Modify: `backend/app/modules/employees/domain/trial_period.py`
- Modify: `backend/app/modules/employees/application/queries.py` (projection incluant `trial_period`)
- Test: `backend/tests/unit/employees/test_trial_period.py` (existant, à compléter)

**Interfaces:**
- Consumes: table `trial_periods` jointe sous la clé `trial_period`
- Produces: `calculate_trial_period_status(hire_date_raw, trial_period, employment_status, reference_date=None) -> dict` — **le paramètre `periode_essai` devient `trial_period` et le paramètre `contract_type` disparaît**, inutilisé

- [ ] **Step 1 : écrire le test qui échoue**

Ajouter à `backend/tests/unit/employees/test_trial_period.py` :

```python
def test_statut_depuis_la_table():
    from datetime import date

    from app.modules.employees.domain.trial_period import calculate_trial_period_status

    result = calculate_trial_period_status(
        "2026-06-01",
        {"end_date": "2026-08-15", "status": "en_cours"},
        "actif",
        reference_date=date(2026, 8, 5),
    )
    assert result["trial_period_applicable"] is True
    assert result["trial_period_status"] == "ending_soon"
    assert result["trial_period_end_date"] == "2026-08-15"
    assert result["trial_period_days_remaining"] == 10


def test_statut_confirme_depuis_la_table():
    from datetime import date

    from app.modules.employees.domain.trial_period import calculate_trial_period_status

    result = calculate_trial_period_status(
        "2026-06-01",
        {"end_date": "2026-08-15", "status": "confirmee"},
        "actif",
        reference_date=date(2026, 8, 5),
    )
    assert result["trial_period_status"] == "confirmed"


def test_a_completer_pour_une_embauche_recente_sans_periode():
    from datetime import date

    from app.modules.employees.domain.trial_period import calculate_trial_period_status

    result = calculate_trial_period_status(
        "2026-07-20", None, "actif", reference_date=date(2026, 8, 5)
    )
    assert result["trial_period_status"] == "to_complete"
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/employees/test_trial_period.py -v
```

Attendu : les nouveaux tests échouent.

- [ ] **Step 3 : réécrire le module**

Remplacer le contenu de `backend/app/modules/employees/domain/trial_period.py` par :

```python
"""Règles pures : statut calculé de la période d'essai, pour affichage RH."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from app.modules.employees.domain.trial_period_bareme import DEFAULT_ALERT_DAYS
from app.modules.employees.domain.trial_period_shared import parse_date

TRIAL_STATUS_IN_PROGRESS = "in_progress"
TRIAL_STATUS_ENDING_SOON = "ending_soon"
TRIAL_STATUS_ENDED = "ended"
TRIAL_STATUS_CONFIRMED = "confirmed"
TRIAL_STATUS_TO_COMPLETE = "to_complete"

RECENT_HIRE_DAYS_FOR_TO_COMPLETE = 90

_TRACKED_EMPLOYMENT_STATUSES = frozenset({"actif", "en_onboarding"})


def _empty_enrichment() -> Dict[str, Any]:
    return {
        "trial_period_applicable": False,
        "trial_period_status": None,
        "trial_period_end_date": None,
        "trial_period_days_remaining": None,
        "trial_period_renewal_possible": None,
    }


def calculate_trial_period_status(
    hire_date_raw: Any,
    trial_period: Any,
    employment_status: Any,
    reference_date: Optional[date] = None,
    alert_days: int = DEFAULT_ALERT_DAYS,
) -> Dict[str, Any]:
    """Statut enrichi de la période d'essai, à partir de la ligne trial_periods."""
    ref = reference_date or date.today()
    status_norm = str(employment_status or "actif").strip().lower()

    if status_norm not in _TRACKED_EMPLOYMENT_STATUSES:
        return _empty_enrichment()

    if not isinstance(trial_period, dict):
        hire = parse_date(hire_date_raw)
        if hire is not None and (ref - hire).days <= RECENT_HIRE_DAYS_FOR_TO_COMPLETE:
            return {
                "trial_period_applicable": True,
                "trial_period_status": TRIAL_STATUS_TO_COMPLETE,
                "trial_period_end_date": None,
                "trial_period_days_remaining": None,
                "trial_period_renewal_possible": None,
            }
        return _empty_enrichment()

    end = parse_date(trial_period.get("end_date"))
    renewal = trial_period.get("renewal_allowed")
    if renewal is not None:
        renewal = bool(renewal)

    if str(trial_period.get("status") or "") == "confirmee":
        return {
            "trial_period_applicable": True,
            "trial_period_status": TRIAL_STATUS_CONFIRMED,
            "trial_period_end_date": end.isoformat() if end else None,
            "trial_period_days_remaining": None,
            "trial_period_renewal_possible": renewal,
        }

    if end is None:
        return _empty_enrichment()

    days_remaining = (end - ref).days
    if days_remaining < 0:
        status = TRIAL_STATUS_ENDED
    elif days_remaining <= alert_days:
        status = TRIAL_STATUS_ENDING_SOON
    else:
        status = TRIAL_STATUS_IN_PROGRESS

    return {
        "trial_period_applicable": True,
        "trial_period_status": status,
        "trial_period_end_date": end.isoformat(),
        "trial_period_days_remaining": days_remaining,
        "trial_period_renewal_possible": renewal,
    }


__all__ = [
    "TRIAL_STATUS_CONFIRMED",
    "TRIAL_STATUS_ENDED",
    "TRIAL_STATUS_ENDING_SOON",
    "TRIAL_STATUS_IN_PROGRESS",
    "TRIAL_STATUS_TO_COMPLETE",
    "calculate_trial_period_status",
]
```

Chercher tous les appelants et adapter la projection et l'appel :

```bash
cd backend && grep -rn "calculate_trial_period_status" app/ --include="*.py"
```

Pour chaque appelant, ajouter `trial_period:trial_periods(end_date, status, renewal_allowed)` à la projection Supabase, normaliser la liste en un dictionnaire comme en Task 9, et passer ce dictionnaire à la place de `periode_essai`.

- [ ] **Step 4 : lancer les tests**

```bash
cd backend && python -m pytest tests/unit/ -q
```

Attendu : tous PASSED. Adapter les tests préexistants qui passaient un jsonb `{"duree_initiale": ...}`.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/modules/employees/ backend/tests/unit/employees/
git commit -m "feat(essai): badge et filtres alimentés par la table

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 11 : Libellé de période d'essai dans les contrats

`format_periode_essai` alimente les contrats PDF et DOCX en lisant le jsonb.

**Files:**
- Modify: `backend/app/shared/infrastructure/pdf/helpers.py`
- Test: `backend/tests/unit/shared/test_format_periode_essai.py`

**Interfaces:**
- Consumes: dictionnaire `trial_period` joint
- Produces: `format_periode_essai(employee: dict) -> str`, signature inchangée

- [ ] **Step 1 : écrire le test qui échoue**

Créer `backend/tests/unit/shared/test_format_periode_essai.py` :

```python
"""Libellé de période d'essai dans les contrats générés."""

from app.shared.infrastructure.pdf.helpers import format_periode_essai

REPLI = (
    "Conformément aux dispositions légales et conventionnelles applicables "
    "à l'emploi concerné"
)


def test_depuis_la_table_avec_renouvellement():
    label = format_periode_essai(
        {"trial_period": {"duration_value": 2, "duration_unit": "mois", "renewal_allowed": True}}
    )
    assert label.startswith("2 mois, renouvelable une fois")


def test_depuis_la_table_sans_renouvellement():
    label = format_periode_essai(
        {"trial_period": {"duration_value": 1, "duration_unit": "jours", "renewal_allowed": False}}
    )
    assert label.startswith("1 jour,")
    assert "renouvelable" not in label


def test_accord_du_pluriel():
    label = format_periode_essai(
        {"trial_period": {"duration_value": 3, "duration_unit": "semaines", "renewal_allowed": False}}
    )
    assert label.startswith("3 semaines,")


def test_valeur_explicite_prioritaire():
    label = format_periode_essai(
        {"periode_essai_duree": "2 mois renouvelables", "trial_period": {"duration_value": 4}}
    )
    assert label == "2 mois renouvelables"


def test_repli_quand_la_periode_n_existe_pas_encore():
    # La génération du contrat peut précéder la création de la période.
    assert format_periode_essai({}) == REPLI
    assert format_periode_essai({"trial_period": None}) == REPLI
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && python -m pytest tests/unit/shared/test_format_periode_essai.py -v
```

Attendu : les tests lisant `trial_period` échouent.

- [ ] **Step 3 : réécrire le helper**

Dans `backend/app/shared/infrastructure/pdf/helpers.py`, remplacer le corps de `format_periode_essai` :

```python
def format_periode_essai(employee: Dict[str, Any]) -> str:
    """Libellé de la période d'essai pour le contrat.

    La génération peut précéder la création de la période : le repli légal
    reste la sortie par défaut.
    """
    for key in ("periode_essai_duree", "trial_period_duration", "duree_periode_essai"):
        val = employee.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()

    trial = employee.get("trial_period")
    if isinstance(trial, dict):
        try:
            duree = int(trial.get("duration_value"))
        except (TypeError, ValueError):
            duree = 0
        if duree > 0:
            unite = str(trial.get("duration_unit") or "mois").lower()
            if unite.startswith("jour"):
                label = "jour" if duree == 1 else "jours"
            elif unite.startswith("sem"):
                label = "semaine" if duree == 1 else "semaines"
            else:
                label = "mois"
            base = f"{duree} {label}"
            if trial.get("renewal_allowed"):
                return (
                    f"{base}, renouvelable une fois conformément aux dispositions "
                    "légales et conventionnelles"
                )
            return (
                f"{base}, conformément aux dispositions légales et "
                "conventionnelles applicables"
            )

    return (
        "Conformément aux dispositions légales et conventionnelles applicables "
        "à l'emploi concerné"
    )
```

- [ ] **Step 4 : lancer les tests**

```bash
cd backend && python -m pytest tests/unit/shared/ -v
```

Attendu : tous PASSED.

- [ ] **Step 5 : commiter**

```bash
git add backend/app/shared/infrastructure/pdf/helpers.py backend/tests/unit/shared/test_format_periode_essai.py
git commit -m "feat(essai): libellé de contrat depuis la table

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 12 : Calcul de fin côté client

Le frontend affiche un aperçu de la date de fin. Il doit rendre la même date que le backend, sans quoi l'aperçu contredit la fiche.

**Files:**
- Modify: `frontend/src/lib/trialPeriodUtils.ts`
- Test: `frontend/src/lib/__tests__/trialPeriodUtils.test.ts`

**Interfaces:**
- Consumes: rien
- Produces: `computeTrialPeriodEndDate(hireDateIso, duree, unite) -> Date | null`, signature inchangée, résultat décalé d'un jour par rapport à l'actuel

- [ ] **Step 1 : écrire le test qui échoue**

Créer `frontend/src/lib/__tests__/trialPeriodUtils.test.ts` :

```typescript
import { describe, expect, it } from "vitest";
import { computeTrialPeriodEndDate } from "../trialPeriodUtils";

const iso = (d: Date | null) => (d ? d.toISOString().slice(0, 10) : null);

describe("computeTrialPeriodEndDate", () => {
  it("termine la veille du quantième", () => {
    expect(iso(computeTrialPeriodEndDate("2026-03-01", 2, "mois"))).toBe("2026-04-30");
  });

  it("va au dernier jour du mois quand le quantième n'existe pas", () => {
    expect(iso(computeTrialPeriodEndDate("2026-01-31", 1, "mois"))).toBe("2026-02-28");
    expect(iso(computeTrialPeriodEndDate("2028-01-31", 1, "mois"))).toBe("2028-02-29");
  });

  it("compte le jour d'embauche dans les jours", () => {
    expect(iso(computeTrialPeriodEndDate("2026-03-02", 8, "jours"))).toBe("2026-03-09");
  });

  it("compte les semaines", () => {
    expect(iso(computeTrialPeriodEndDate("2026-03-02", 2, "semaines"))).toBe("2026-03-15");
  });

  it("refuse une durée nulle", () => {
    expect(computeTrialPeriodEndDate("2026-03-01", 0, "mois")).toBeNull();
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd frontend && npx vitest run src/lib/__tests__/trialPeriodUtils.test.ts
```

Attendu : `expected '2026-05-01' to be '2026-04-30'`.

- [ ] **Step 3 : corriger le calcul**

Dans `frontend/src/lib/trialPeriodUtils.ts`, remplacer `computeTrialPeriodEndDate` :

```typescript
export function computeTrialPeriodEndDate(
  hireDateIso: string,
  duree: number,
  unite: TrialPeriodUnit,
): Date | null {
  if (!hireDateIso || duree <= 0) return null;
  const hire = parseISO(hireDateIso.slice(0, 10));
  if (Number.isNaN(hire.getTime())) return null;

  // La période expire la veille du quantième correspondant : deux mois à
  // compter du 1er mars s'achèvent le 30 avril, pas le 1er mai.
  if (unite === "jours") return addDays(hire, duree - 1);
  if (unite === "semaines") return addDays(hire, duree * 7 - 1);

  const target = addMonths(hire, duree);
  // addMonths a tronqué au dernier jour du mois (31 janvier + 1 mois donne le
  // 28 février) : c'est déjà le dernier jour de la période.
  if (target.getDate() !== hire.getDate()) return target;
  return addDays(target, -1);
}
```

- [ ] **Step 4 : lancer le test**

```bash
cd frontend && npx vitest run src/lib/__tests__/trialPeriodUtils.test.ts
```

Attendu : 5 tests PASSED.

- [ ] **Step 5 : commiter**

```bash
git add frontend/src/lib/trialPeriodUtils.ts frontend/src/lib/__tests__/trialPeriodUtils.test.ts
git commit -m "fix(essai): aperçu de fin de période d'essai au bon jour

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 13 : Client d'API frontend

**Files:**
- Create: `frontend/src/api/trialPeriods.ts`

**Interfaces:**
- Consumes: routes de Task 8
- Produces: `TrialPeriod`, `TrialPeriodTracking`, `fetchTrialPeriodTracking()`, `createTrialPeriod(body)`, `updateTrialPeriod(id, body)`, `confirmTrialPeriod(id)`, `renewTrialPeriod(id, body)`, `applyBareme(employeeIds)`

- [ ] **Step 1 : lire le client existant pour en copier les conventions**

```bash
cd frontend && sed -n 1,40p src/api/employeeLoans.ts
```

- [ ] **Step 2 : écrire le client**

Créer `frontend/src/api/trialPeriods.ts` :

```typescript
import { apiClient } from "./apiClient";

export type TrialPeriodUnit = "jours" | "semaines" | "mois";

export interface TrialPeriod {
  id: string;
  company_id: string;
  employee_id: string;
  employee_name: string | null;
  start_date: string;
  duration_value: number;
  duration_unit: TrialPeriodUnit;
  renewal_allowed: boolean;
  renewed_at: string | null;
  renewal_duration_value: number | null;
  renewal_duration_unit: TrialPeriodUnit | null;
  end_date: string;
  status: "en_cours" | "confirmee" | "rompue";
  confirmed_at: string | null;
  hire_date: string | null;
  contract_type: string | null;
  statut: string | null;
}

export interface EmployeeToQualify {
  id: string;
  first_name: string;
  last_name: string;
  hire_date: string | null;
  contract_type: string | null;
  statut: string | null;
}

export interface TrialPeriodTracking {
  alert_days: number;
  en_cours: TrialPeriod[];
  a_confirmer: TrialPeriod[];
  a_qualifier: EmployeeToQualify[];
}

export async function fetchTrialPeriodTracking(): Promise<TrialPeriodTracking> {
  const { data } = await apiClient.get<TrialPeriodTracking>("/api/trial-periods/tracking");
  return data;
}

export async function createTrialPeriod(body: {
  employee_id: string;
  start_date: string;
  duration_value: number;
  duration_unit: TrialPeriodUnit;
  renewal_allowed: boolean;
}): Promise<TrialPeriod> {
  const { data } = await apiClient.post<TrialPeriod>("/api/trial-periods", body);
  return data;
}

export async function updateTrialPeriod(
  id: string,
  body: {
    start_date?: string;
    duration_value?: number;
    duration_unit?: TrialPeriodUnit;
    renewal_allowed?: boolean;
  },
): Promise<TrialPeriod> {
  const { data } = await apiClient.patch<TrialPeriod>(`/api/trial-periods/${id}`, body);
  return data;
}

export async function confirmTrialPeriod(id: string): Promise<TrialPeriod> {
  const { data } = await apiClient.post<TrialPeriod>(`/api/trial-periods/${id}/confirm`);
  return data;
}

export async function renewTrialPeriod(
  id: string,
  body: { renewed_at: string; duration_value: number; duration_unit: TrialPeriodUnit },
): Promise<TrialPeriod> {
  const { data } = await apiClient.post<TrialPeriod>(`/api/trial-periods/${id}/renew`, body);
  return data;
}

export async function applyBareme(
  employeeIds: string[],
): Promise<{ created: string[]; skipped: { employee_id: string; raison: string }[] }> {
  const { data } = await apiClient.post("/api/trial-periods/apply-bareme", {
    employee_ids: employeeIds,
  });
  return data;
}
```

- [ ] **Step 3 : vérifier la compilation**

```bash
cd frontend && npx tsc --noEmit
```

Attendu : aucune erreur. Si `apiClient` n'expose pas ces méthodes, aligner sur ce que fait `src/api/employeeLoans.ts`.

- [ ] **Step 4 : commiter**

```bash
git add frontend/src/api/trialPeriods.ts
git commit -m "feat(essai): client d'API des périodes d'essai

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 14 : Page de suivi

**Files:**
- Create: `frontend/src/pages/rh/TrialPeriods.tsx`
- Modify: `frontend/src/pages/index.ts`, `frontend/src/App.tsx`, `frontend/src/components/ui/app-sidebar.tsx`

**Interfaces:**
- Consumes: `fetchTrialPeriodTracking`, `confirmTrialPeriod`, `applyBareme` (Task 13)
- Produces: route `/trial-periods`, entrée de menu « Périodes d'essai » dans le groupe *Effectifs*

- [ ] **Step 1 : lire la page modèle**

```bash
cd frontend && sed -n 1,80p src/pages/rh/ResidencePermits.tsx
```

Reprendre sa structure : `useQuery`, en-tête de page, cartes de section, tableau shadcn, états de chargement et d'erreur.

- [ ] **Step 2 : écrire la page**

Créer `frontend/src/pages/rh/TrialPeriods.tsx` :

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { differenceInCalendarDays, format, parseISO } from "date-fns";
import { fr } from "date-fns/locale";
import { Loader2 } from "lucide-react";
import {
  applyBareme,
  confirmTrialPeriod,
  fetchTrialPeriodTracking,
  type EmployeeToQualify,
  type TrialPeriod,
} from "@/api/trialPeriods";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/use-toast";

const TRACKING_KEY = ["trial-periods", "tracking"] as const;

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return format(parseISO(iso.slice(0, 10)), "d MMMM yyyy", { locale: fr });
}

function daysLeft(iso: string): number {
  return differenceInCalendarDays(parseISO(iso.slice(0, 10)), new Date());
}

function errorMessage(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback
  );
}

export default function TrialPeriods() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data, isLoading, isError } = useQuery({
    queryKey: TRACKING_KEY,
    queryFn: fetchTrialPeriodTracking,
  });

  // Déclaré avant les mutations : leurs callbacks s'en servent pour nommer les
  // salariés écartés.
  const nameOf = (employeeId: string): string => {
    const emp = data?.a_qualifier.find((e) => e.id === employeeId);
    return emp ? `${emp.first_name} ${emp.last_name}`.trim() : employeeId;
  };

  const confirmMutation = useMutation({
    mutationFn: confirmTrialPeriod,
    onSuccess: () => {
      toast({ title: "Embauche confirmée", description: "Le suivi de période d'essai est clos." });
      void queryClient.invalidateQueries({ queryKey: TRACKING_KEY });
    },
    onError: (error) =>
      toast({
        title: "Erreur",
        description: errorMessage(error, "Impossible de confirmer l'embauche."),
        variant: "destructive",
      }),
  });

  const applyMutation = useMutation({
    mutationFn: applyBareme,
    onSuccess: (result) => {
      // Une sélection partiellement traitée ne doit pas passer pour un succès
      // complet : les salariés écartés sont nommés avec leur raison.
      if (result.skipped.length > 0) {
        toast({
          title: `${result.created.length} période(s) créée(s), ${result.skipped.length} écartée(s)`,
          description: result.skipped
            .map((s) => `${nameOf(s.employee_id)} : ${s.raison}`)
            .join(" · "),
        });
      } else {
        toast({ title: `${result.created.length} période(s) d'essai créée(s)` });
      }
      setSelected(new Set());
      void queryClient.invalidateQueries({ queryKey: TRACKING_KEY });
    },
    onError: (error) =>
      toast({
        title: "Erreur",
        description: errorMessage(error, "Impossible d'appliquer le barème."),
        variant: "destructive",
      }),
  });

  const toggle = (employeeId: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-8 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Chargement des périodes d&apos;essai…
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-8 text-destructive">
        Impossible de charger les périodes d&apos;essai.
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Périodes d&apos;essai</h1>
        <p className="text-sm text-muted-foreground">
          Suivi des périodes en cours, des confirmations à prononcer et des embauches
          récentes encore sans période d&apos;essai. Alerte réglée à {data.alert_days} jours.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>À confirmer ({data.a_confirmer.length})</CardTitle>
          <CardDescription>
            Périodes dont le terme est atteint ou proche. Passé ce terme sans décision,
            l&apos;embauche est définitivement acquise.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.a_confirmer.length === 0 ? (
            <p className="text-sm text-muted-foreground">Rien à confirmer.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Contrat</TableHead>
                  <TableHead>Fin</TableHead>
                  <TableHead>Échéance</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.a_confirmer.map((trial: TrialPeriod) => {
                  const left = daysLeft(trial.end_date);
                  return (
                    <TableRow key={trial.id}>
                      <TableCell>
                        <Link className="hover:underline" to={`/employees/${trial.employee_id}`}>
                          {trial.employee_name || "—"}
                        </Link>
                      </TableCell>
                      <TableCell>
                        {trial.contract_type || "—"} · {trial.statut || "—"}
                      </TableCell>
                      <TableCell>{formatDate(trial.end_date)}</TableCell>
                      <TableCell>
                        <Badge variant={left < 0 ? "destructive" : "secondary"}>
                          {left < 0 ? `Dépassée de ${-left} j` : `J-${left}`}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          disabled={confirmMutation.isPending}
                          onClick={() => confirmMutation.mutate(trial.id)}
                        >
                          Confirmer l&apos;embauche
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>En cours ({data.en_cours.length})</CardTitle>
          <CardDescription>Périodes actives, hors fenêtre d&apos;alerte.</CardDescription>
        </CardHeader>
        <CardContent>
          {data.en_cours.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune période en cours.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Contrat</TableHead>
                  <TableHead>Début</TableHead>
                  <TableHead>Fin prévue</TableHead>
                  <TableHead>Renouvellement</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.en_cours.map((trial: TrialPeriod) => (
                  <TableRow key={trial.id}>
                    <TableCell>
                      <Link className="hover:underline" to={`/employees/${trial.employee_id}`}>
                        {trial.employee_name || "—"}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {trial.contract_type || "—"} · {trial.statut || "—"}
                    </TableCell>
                    <TableCell>{formatDate(trial.start_date)}</TableCell>
                    <TableCell>
                      {formatDate(trial.end_date)} · J-{daysLeft(trial.end_date)}
                    </TableCell>
                    <TableCell>
                      {trial.renewed_at
                        ? `Renouvelée le ${formatDate(trial.renewed_at)}`
                        : trial.renewal_allowed
                          ? "Possible"
                          : "Non prévu"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div>
            <CardTitle>À qualifier ({data.a_qualifier.length})</CardTitle>
            <CardDescription>
              Salariés entrés il y a moins de huit mois sans période d&apos;essai
              enregistrée. Le barème société propose une durée ; elle reste modifiable
              depuis la fiche.
            </CardDescription>
          </div>
          <Button
            disabled={selected.size === 0 || applyMutation.isPending}
            onClick={() => applyMutation.mutate([...selected])}
          >
            {applyMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Appliquer le barème ({selected.size})
          </Button>
        </CardHeader>
        <CardContent>
          {data.a_qualifier.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Toutes les embauches récentes sont qualifiées.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10" />
                  <TableHead>Salarié</TableHead>
                  <TableHead>Contrat</TableHead>
                  <TableHead>Date d&apos;entrée</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.a_qualifier.map((emp: EmployeeToQualify) => (
                  <TableRow key={emp.id}>
                    <TableCell>
                      <Checkbox
                        checked={selected.has(emp.id)}
                        onCheckedChange={() => toggle(emp.id)}
                        aria-label={`Sélectionner ${emp.first_name} ${emp.last_name}`}
                      />
                    </TableCell>
                    <TableCell>
                      <Link className="hover:underline" to={`/employees/${emp.id}`}>
                        {`${emp.first_name} ${emp.last_name}`.trim()}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {emp.contract_type || "—"} · {emp.statut || "—"}
                    </TableCell>
                    <TableCell>{formatDate(emp.hire_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

Si `ResidencePermits.tsx` exporte sa page en nommé plutôt qu'en défaut, aligner l'export sur elle et adapter `pages/index.ts` en conséquence. Vérifier également que la route des fiches est bien `/employees/:id` en lisant `App.tsx` — sinon corriger les `Link`.

- [ ] **Step 3 : brancher la route et le menu**

Dans `frontend/src/pages/index.ts`, exporter la page comme ses voisines.

Dans `frontend/src/App.tsx`, à côté de la ligne 218 :

```tsx
<Route path="/trial-periods" element={<Pages.TrialPeriods />} />
```

Dans `frontend/src/components/ui/app-sidebar.tsx`, dans le groupe « Effectifs » (lignes 126-135), après « Départs » :

```tsx
      { title: "Périodes d'essai", url: "/trial-periods", icon: CalendarClock },
```

Importer `CalendarClock` depuis `lucide-react` avec les autres icônes.

- [ ] **Step 4 : vérifier**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

Attendu : aucune erreur.

- [ ] **Step 5 : commiter**

```bash
git add frontend/src/pages/rh/TrialPeriods.tsx frontend/src/pages/index.ts frontend/src/App.tsx frontend/src/components/ui/app-sidebar.tsx
git commit -m "feat(essai): page de suivi des périodes d'essai

Trois sections — à confirmer, en cours, à qualifier — accessibles depuis
le menu Effectifs. C'est l'endroit qu'Elsa n'avait pas trouvé.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 15 : Carte de la fiche salarié

**Files:**
- Modify: `frontend/src/components/employee-detail/EmployeeDetailTrialPeriodCard.tsx`
- Modify: `frontend/src/features/employee-detail/types.ts` (champ `trial_period`)

**Interfaces:**
- Consumes: `createTrialPeriod`, `updateTrialPeriod`, `confirmTrialPeriod`, `renewTrialPeriod` (Task 13)
- Produces: carte visible pour tout salarié actif

- [ ] **Step 1 : retirer le masquage**

Remplacer les lignes 88-93 :

```tsx
  const showCard =
    employee.trial_period_applicable ||
    employee.trial_period_status === "to_complete" ||
    form.enabled;

  if (!showCard) return null;
```

par :

```tsx
  // La carte reste visible pour tout salarié actif : c'est le point d'entrée
  // permettant d'activer le suivi après la création, quelle que soit son
  // ancienneté. Sa condition précédente la masquait pour 239 salariés sur 241.
  const trackable =
    employee.employment_status === "actif" ||
    employee.employment_status === "en_onboarding";

  if (!trackable) return null;
```

- [ ] **Step 2 : brancher les mutations sur la nouvelle API**

Remplacer l'enregistrement du jsonb par `createTrialPeriod` quand `employee.trial_period` est absent, `updateTrialPeriod` sinon. La confirmation appelle `confirmTrialPeriod(employee.trial_period.id)`.

- [ ] **Step 3 : ajouter le renouvellement**

Sous les champs de durée, n'afficher le bloc que si `employee.trial_period?.renewal_allowed` est vrai et `renewed_at` nul : une date de décision, une durée, une unité, et un bouton « Enregistrer le renouvellement » appelant `renewTrialPeriod`.

Quand `renewed_at` est renseigné, afficher à la place une ligne de rappel : « Renouvelée le <date> pour <durée> — fin repoussée au <end_date> ».

Le backend refuse un renouvellement notifié après le terme initial (Task 6) : remonter le message d'erreur tel quel dans le toast, il explique le refus.

- [ ] **Step 4 : afficher la trace de confirmation**

Quand `status === "confirmee"`, afficher « Embauche confirmée le <confirmed_at> » sous le badge.

- [ ] **Step 5 : vérifier**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

Attendu : aucune erreur.

- [ ] **Step 6 : commiter**

```bash
git add frontend/src/components/employee-detail/EmployeeDetailTrialPeriodCard.tsx frontend/src/features/employee-detail/types.ts
git commit -m "feat(essai): carte de période d'essai visible sur toute fiche active

La condition d'affichage exigeait une période déjà renseignée ou moins de
90 jours d'ancienneté : elle masquait la carte pour 239 salariés sur 241,
rendant impossible l'activation du suivi après la création.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 16 : Réglages société

**Files:**
- Modify: `frontend/src/pages/rh/CompanyPage.tsx` (ou le composant de réglages qu'elle monte)
- Modify: `backend/app/modules/companies/application/commands.py`

**Interfaces:**
- Consumes: `DEFAULT_BAREME`, `DEFAULT_ALERT_DAYS` (Task 3)
- Produces: `companies.settings.periode_essai` éditable

- [ ] **Step 1 : autoriser la clé côté backend**

Dans `update_company_settings`, à côté des clés déjà traitées (`medical_follow_up_enabled`, `public_holidays`), ajouter :

```python
    if "periode_essai" in settings_delta:
        incoming = settings_delta["periode_essai"]
        current_settings["periode_essai"] = incoming if isinstance(incoming, dict) else {}
```

- [ ] **Step 2 : écrire le test**

Ajouter à `backend/tests/unit/companies/test_commands.py` (le créer s'il n'existe pas, en copiant la structure d'un test de commandes voisin) :

```python
def test_le_bareme_de_periode_d_essai_est_enregistre(monkeypatch):
    from app.modules.companies.application import commands

    stored = {}

    class _Repo:
        def get_settings(self, company_id):
            return {"medical_follow_up_enabled": True}

        def update_settings(self, company_id, settings):
            stored.update(settings)
            return settings

    monkeypatch.setattr(commands, "company_repository", _Repo())

    commands.update_company_settings(
        "c1", {"periode_essai": {"alerte_jours": 30, "bareme": []}}
    )

    assert stored["periode_essai"]["alerte_jours"] == 30
    # Les réglages voisins ne sont pas écrasés.
    assert stored["medical_follow_up_enabled"] is True
```

Adapter les noms de méthodes du faux dépôt à ceux réellement utilisés par `update_company_settings`, vérifiés en lisant le fichier.

- [ ] **Step 3 : lancer le test**

```bash
cd backend && python -m pytest tests/unit/companies/ -v
```

Attendu : PASSED.

- [ ] **Step 4 : ajouter le bloc de réglage frontend**

Un tableau éditable des lignes de barème (type de contrat, statut, durée, unité, renouvellement), un champ numérique pour le délai d'alerte, une case pour la règle légale CDD. Les valeurs par défaut affichées sont celles du barème légal, avec une mention explicite qu'elles s'appliquent tant qu'aucune ligne n'est saisie.

- [ ] **Step 5 : vérifier et commiter**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

```bash
git add backend/app/modules/companies/application/commands.py backend/tests/unit/companies/ frontend/src/pages/rh/CompanyPage.tsx
git commit -m "feat(essai): barème de période d'essai éditable dans les réglages société

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 17 : Retirer le jsonb du parcours de création

Le formulaire de création écrit encore `periode_essai` en jsonb avec un barème codé en dur.

**Files:**
- Modify: `frontend/src/features/employees/components/CreateEmployeeForm.tsx:38-52,124-127,218-228,666-689,1199-1265`
- Modify: `frontend/src/features/employees/components/createEmployeeFormSchema.ts:43-44,125-129`
- Modify: `backend/app/modules/employees/application/commands.py` (création du salarié)

**Interfaces:**
- Consumes: `resolve_trial_proposal` (Task 3), `create_trial_period` (Task 6)
- Produces: la création d'un salarié crée sa ligne `trial_periods`

- [ ] **Step 1 : déplacer la proposition côté serveur**

À la création d'un salarié, après l'insertion, appeler `resolve_trial_proposal` avec les réglages de la société, puis `create_trial_period` si la proposition n'est pas nulle et que la date d'entrée est connue. Le formulaire n'envoie plus qu'un booléen `has_periode_essai` et, si l'utilisateur l'a modifiée, une durée.

- [ ] **Step 2 : écrire le test**

Ajouter à `backend/tests/unit/employees/test_commands_trial.py` (créé) un test vérifiant que la création d'un salarié en CDI Cadre produit un payload de période d'essai de quatre mois, et qu'un apprenti n'en produit aucun. Utiliser un faux dépôt, comme dans les tests de commandes voisins.

- [ ] **Step 3 : nettoyer le frontend**

Retirer `defaultTrialSettings` du formulaire — le barème vit désormais côté serveur. Conserver la case « Période d'essai » et les champs de durée, qui restent une saisie possible, mais alimentés par un appel au barème plutôt que par des constantes.

- [ ] **Step 4 : vérifier**

```bash
cd backend && python -m pytest tests/unit/ -q
cd frontend && npx tsc --noEmit && npm run lint
```

Attendu : tous PASSED, aucune erreur.

- [ ] **Step 5 : commiter**

```bash
git add frontend/src/features/employees/components/ backend/app/modules/employees/application/commands.py backend/tests/unit/employees/
git commit -m "feat(essai): création de salarié alimentant la table trial_periods

Le barème codé en dur dans le formulaire disparaît au profit du barème
société résolu côté serveur.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 18 : Abandon du champ jsonb

**Files:**
- Create: `supabase/migrations/20260806100000_trial_periods_deprecate_jsonb.sql`
- Modify: `backend/app/modules/employees/schemas/requests.py`, `schemas/responses.py`

**Interfaces:**
- Consumes: rien
- Produces: colonne `employees.periode_essai` commentée comme abandonnée

La colonne n'est **pas supprimée** : la supprimer casserait toute session parallèle qui la lit encore, et elle est vide de toute façon. Elle est marquée abandonnée et retirée des schémas d'API.

- [ ] **Step 1 : vérifier qu'elle est toujours vide**

Sur la production, en lecture seule :

```sql
select count(*) from employees where periode_essai is not null;
```

Attendu : 0. **Si le compte n'est pas nul**, une autre session ou un import l'a alimentée : arrêter cette tâche, reprendre les données dans `trial_periods` et le signaler.

- [ ] **Step 2 : écrire la migration**

Créer `supabase/migrations/20260806100000_trial_periods_deprecate_jsonb.sql` :

```sql
-- employees.periode_essai est remplacé par la table trial_periods. La colonne
-- est conservée le temps que toutes les lectures aient basculé ; elle était
-- vide sur les 241 salariés actifs au moment de la bascule.

COMMENT ON COLUMN public.employees.periode_essai IS
    'ABANDONNÉ le 6 août 2026 au profit de la table trial_periods. Ne plus lire ni écrire.';
```

- [ ] **Step 3 : retirer le champ des schémas d'API**

Supprimer `periode_essai: Dict[str, Any] | None = None` de `EmployeeCreate`/`EmployeeUpdate` dans `requests.py` et de `FullEmployee` dans `responses.py`, en ajoutant à la place `trial_period: Dict[str, Any] | None = None` en lecture seule.

- [ ] **Step 4 : vérifier**

```bash
cd backend && python -m pytest tests/unit/ -q && grep -rn "periode_essai" app/ --include="*.py" | grep -v "fin_periode_essai" | grep -v "ABANDONNÉ"
```

Attendu : tous les tests PASSED, et le `grep` ne renvoie plus que `trial_period_shared.py` (fonction de compatibilité) — toute autre occurrence signale une lecture oubliée.

- [ ] **Step 5 : commiter**

```bash
git add supabase/migrations/20260806100000_trial_periods_deprecate_jsonb.sql backend/app/modules/employees/schemas/
git commit -m "chore(essai): abandonner employees.periode_essai

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 19 : Recette sur l'environnement de test

**Files:** aucun (vérification)

- [ ] **Step 1 : déployer sur le test**

```bash
gh workflow run deploy-test-env.yml -f migration=20260806100000_trial_periods_deprecate_jsonb.sql
gh run watch
```

Attendu : run vert. Rappel : un déploiement en attente d'approbation bloque tous les suivants sans message d'erreur.

- [ ] **Step 2 : parcours d'activation**

Sur l'environnement de test, ouvrir la fiche d'un salarié **embauché il y a plus d'un an** : la carte « Période d'essai » doit être visible, avec son interrupteur. L'activer, saisir deux mois, enregistrer.

Attendu : la fiche affiche une date de fin égale à la veille du quantième, et le salarié apparaît dans la page de suivi.

- [ ] **Step 3 : parcours de rattrapage**

Ouvrir `/trial-periods`, section « À qualifier », sélectionner deux salariés, appliquer le barème.

Attendu : deux périodes créées, avec quatre mois pour un cadre et deux mois pour un non-cadre en CDI. Les salariés écartés apparaissent dans le toast avec leur raison.

- [ ] **Step 4 : parcours de renouvellement et de confirmation**

Sur une période dont le renouvellement est ouvert, enregistrer un renouvellement daté avant le terme : la date de fin doit être repoussée, et le J-x recalculé. Tenter un renouvellement daté après le terme : l'API doit refuser avec un message explicite.

Confirmer une période depuis la page de suivi : elle quitte la section « à confirmer », le badge de la fiche passe à « confirmée », et la trace de confirmation s'affiche.

- [ ] **Step 5 : vérifier l'absence de fuite RLS**

Se connecter avec un compte n'ayant accès qu'à une société et vérifier qu'aucune période d'une autre société n'apparaît.

```sql
select count(*) from trial_periods;
```

Exécutée avec la clé anon d'un utilisateur d'une seule société, la requête ne doit remonter que ses propres lignes.

- [ ] **Step 6 : consigner la recette**

Noter le résultat de chaque parcours dans `docs/afaire.md` sous le point #28, en français, avec ce qui a été vérifié et ce qui reste ouvert.

```bash
git add docs/afaire.md
git commit -m "docs(afaire): recette du suivi des périodes d'essai (#28)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Vérification finale

- [ ] `cd backend && python -m pytest tests/unit/ -q` — tous PASSED
- [ ] `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run` — aucune erreur
- [ ] `grep -rn "periode_essai" backend/app frontend/src | grep -v fin_periode_essai | grep -v ABANDONNÉ` — ne renvoie que la fonction de compatibilité
- [ ] Les deux migrations sont appliquées sur le test et vérifiées
- [ ] Aucune donnée fabriquée : `select count(*) from trial_periods` en production reste à 0 tant qu'Elsa n'a rien saisi

## Points à remonter à Alexandre en fin de chantier

- Le déploiement en production et la fusion vers `main` demandent son accord.
- Hors périmètre, déjà signalé : ni `PAYSLIP_EMAIL_REDIRECT` ni `EMAIL_FORCE_REDIRECT_TO` ne sont posés sur le service `sirh-backend` de production. Environ 92 salariés y ont une adresse potentiellement réelle.
