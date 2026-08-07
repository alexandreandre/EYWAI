# Compteur JTC (Jour de Temps de Change) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Doter EYWAI d'un compteur JTC paramétrable par société — droit annuel proratisé sur l'année N-1, arrondi à l'entier inférieur, affiché comme un solde distinct des congés payés à l'écran et sur le bulletin.

**Architecture:** Le JTC est un 4ᵉ compteur qui suit le patron déjà en place pour les RTT : un value object de politique société (`LeavePolicySettings`), un calcul pur dans le domaine, un solde d'ouverture annuel stocké par salarié (`employee_leave_adjustments`), et un type d'absence pour la consommation. Différence assumée avec les RTT : le droit **n'est pas recalculé à la volée**. Il est figé une fois par an dans `jtc_opening_balance` — saisi à la main pour 2026, produit par une commande de calcul de janvier à partir de 2027. Le solde affiché est donc toujours `droit de l'année − jours posés dans l'année`, ce qui rend impossible le double comptage entre un droit repris et un droit calculé.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic v2 / pytest côté backend ; PostgreSQL (Supabase, migrations SQL numérotées) ; React + TypeScript + TanStack Query + shadcn/ui côté frontend.

## Global Constraints

Source de vérité : `data/_inbox/whatsapp-elsa-2026-08-02/00005441-Note JTC.docx` (Elsa André, 28/07/2026, « règles validées par la RH »).

- **Périmètre** : MBC (Mont Blanc Composite) uniquement. Le paramètre `jtc_enabled` est à `false` par défaut ; aucune autre société ne doit voir apparaître de compteur JTC.
- **Droit maximum** : 3 JTC par an pour une année complète de travail effectif.
- **Période de référence** : année civile N-1, du 01/01 au 31/12. Les JTC crédités début N sont acquis sur l'activité de N-1.
- **Moment du calcul** : janvier, sur les données N-1, à poser sur l'année N.
- **Prorata entrée** : au prorata des jours de présence sur N-1.
- **Prorata absences** : si les absences N-1 dépassent 30 jours, le droit est réduit au prorata des absences. Les absences ≤ 30 jours n'ont aucun impact.
- **Arrondi** : à l'entier inférieur. Le résultat est toujours 0, 1, 2 ou 3.
- **Nouvel entrant** : 0 JTC l'année de l'entrée. Premier calcul en janvier de l'année suivante.
- **Reprise** : l'ancienneté n'est pas reprise pour ce calcul.
- **Affichage** : le solde JTC est un nombre entier affiché **à côté** du solde CP, jamais additionné au total CP.
- **Aucune modification du moteur de paie dans ce plan.** La journée de solidarité (§5 de la note) et le paiement du solde au départ (§6) relèvent d'un lot 2 séparé.

### Un écart assumé avec la note

La note fixe comme base de calcul « les heures réellement faites ». EYWAI ne dispose d'aucune heure sur une année écoulée : la base de production ne contient que 2026, et MBC n'a ni pointage ni bulletin antérieur. Le calcul retenu approxime donc le temps de travail effectif par les **jours calendaires de présence contractuelle diminués des jours d'absence**, ce qui donne le même résultat pour tout salarié à horaire stable — c'est-à-dire l'écrasante majorité. Il divergerait pour un salarié dont la durée du travail a changé en cours d'année de référence. Conséquence directe : **les droits 2026 des 75 salariés MBC ne sont pas recalculables** et doivent être repris du fichier d'Elsa ; le premier calcul autonome sera celui de janvier 2027, sur les données 2026.

### Deux points en attente de réponse d'Elsa

Ils ne bloquent aucune tâche ci-dessous, mais ils fixent des valeurs par défaut à revoir :

1. **Prorata absences — seuil ou franchise ?** La note dit « absences > 30 j : le droit est réduit au prorata des absences ». Ce plan retient la lecture littérale : les 30 jours sont un **seuil de déclenchement**, et une fois franchi on proratise sur la **totalité** des absences. Conséquence assumée : 30 jours d'absence donnent 3 JTC, 31 jours en donnent 2. La bascule vers une lecture « franchise » (ne proratiser que l'excédent) est un changement d'une ligne dans `calculate_acquired_jtc`, isolé et couvert par un test.
2. **Quelles absences comptent ?** La note renvoie à un onglet « détail absences » qui n'a pas été transmis. Le défaut retenu est la liste citée dans la note : maladie, AT, maternité, plus les congés sans solde. Elle est stockée en base (`jtc_absence_types`), donc modifiable sans redéploiement.

---

## Structure des fichiers

**Backend — créations**

| Fichier | Responsabilité |
|---|---|
| `backend/app/modules/absences/domain/jtc.py` | Calcul pur du droit annuel : prorata entrée, prorata absences, arrondi, bornage. Aucune I/O. |
| `backend/tests/unit/absences/test_jtc.py` | Tests du calcul pur. |
| `backend/tests/unit/absences/test_jtc_balance.py` | Tests du solde (droit − pris) et de son affichage. |
| `supabase/migrations/20260807160000_company_jtc_settings.sql` | Colonnes de paramétrage société + solde d'ouverture salarié. |
| `supabase/migrations/20260807160100_absence_type_jtc.sql` | Ajout de la valeur `jtc` à l'enum `absence_type`. |

**Backend — modifications**

| Fichier | Modification |
|---|---|
| `backend/app/modules/absences/domain/leave_policy.py` | Champs `jtc_*` sur `LeavePolicySettings`, champ `jtc_opening_balance` sur `EmployeeLeaveAdjustment`, constantes de défaut. |
| `backend/app/modules/absences/domain/enums.py` | `"jtc"` dans le Literal `AbsenceType`. |
| `backend/app/modules/absences/domain/rules.py` | `compute_jtc_balance` + clé `jtc` dans le retour de `compute_absence_balances`. |
| `backend/app/modules/absences/application/balance_display.py` | Ligne « JTC » conditionnelle dans la liste API. |
| `backend/app/modules/absences/infrastructure/leave_settings_repository.py` | Mapping des colonnes `jtc_*` vers les value objects. |
| `backend/app/modules/absences/schemas/leave_settings.py` | Champs `jtc_*` sur `LeaveSettingsUpdate`, `EmployeeLeaveAdjustmentUpdate`, `LeaveAdjustmentImportRow`. |
| `backend/app/modules/absences/schemas/leave_settings_responses.py` | Champs `jtc_*` sur `LeaveSettingsResponse` et `EmployeeLeaveAdjustmentResponse`. |
| `backend/app/modules/absences/application/leave_settings_queries.py` | `_policy_to_response` expose les champs `jtc_*`. |
| `backend/app/modules/absences/application/leave_settings_commands.py` | Commande de calcul annuel (aperçu + application). |
| `backend/app/modules/absences/api/router.py` | Endpoints d'aperçu et d'application du calcul annuel. |
| `backend/app/modules/absences/application/queries.py` | Clé `jtc` dans les soldes du bulletin. |
| `backend/app/modules/payroll/documents/bulletin_view.py` | Colonne « JTC » dans le bloc compteurs. |

**Frontend — modifications**

| Fichier | Modification |
|---|---|
| `frontend/src/api/leaveSettings.ts` | Types des champs `jtc_*` et de la commande de calcul. |
| `frontend/src/api/absences.ts` | `'jtc'` dans les unions de type d'absence. |
| `frontend/src/lib/employeeAbsencesUtils.ts` | Libellé « JTC » et présence dans la liste des types décomptés. |
| `frontend/src/components/AbsenceRequestModal.tsx` | Libellé et option « JTC » dans le sélecteur. |
| `frontend/src/pages/rh/Absences.tsx`, `frontend/src/pages/rh/manager/LeaveRequests.tsx` | Libellé « JTC ». |
| `frontend/src/features/company/components/LeaveSettingsCard.tsx` | Section « JTC » dans la carte de paramétrage. |

---

### Task 1 : Calcul du droit annuel (domaine pur)

**Files:**
- Create: `backend/app/modules/absences/domain/jtc.py`
- Test: `backend/tests/unit/absences/test_jtc.py`

**Interfaces:**
- Consumes: rien (domaine pur, aucune dépendance interne).
- Produces:
  - `JtcSettings(enabled: bool = False, annual_days: int = 3, absence_threshold_days: int = 30, absence_types: tuple[str, ...] = JTC_ABSENCE_TYPES_DEFAULT)` — dataclass gelée.
  - `JTC_ANNUAL_DAYS_DEFAULT: int = 3`
  - `JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT: int = 30`
  - `JTC_ABSENCE_TYPES_DEFAULT: tuple[str, ...] = ("arret_maladie", "arret_at", "arret_maladie_pro", "arret_maternite", "sans_solde")`
  - `calculate_acquired_jtc(*, settings: JtcSettings, reference_year: int, hire_date: date | None, exit_date: date | None = None, absence_days: float = 0.0) -> int`

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/unit/absences/test_jtc.py` :

```python
"""Calcul du droit JTC — note de paramétrage Elsa André du 28/07/2026 (MBC)."""

from datetime import date

from app.modules.absences.domain.jtc import (
    JtcSettings,
    calculate_acquired_jtc,
)


ACTIVE = JtcSettings(enabled=True)


def test_annee_complete_sans_absence_donne_le_droit_plein():
    """Une année complète de travail effectif ouvre les 3 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
        )
        == 3
    )


def test_societe_non_activee_ne_donne_aucun_jtc():
    """Le JTC est propre à MBC : sans activation, aucun droit."""
    assert (
        calculate_acquired_jtc(
            settings=JtcSettings(),
            reference_year=2025,
            hire_date=date(2015, 3, 1),
        )
        == 0
    )


def test_nouvel_entrant_sans_presence_en_n1_na_aucun_jtc():
    """Entré en juin 2026 : 0 JTC en 2026, son premier droit sera calculé en janvier 2027."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2026, 6, 1),
        )
        == 0
    )


def test_entree_en_cours_dannee_proratise_sur_les_jours_de_presence():
    """Entré le 01/07/2025 : 184 jours sur 365 → 3 × 0,504 = 1,51 → 1 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2025, 7, 1),
        )
        == 1
    )


def test_sortie_en_cours_dannee_proratise_aussi():
    """Parti le 31/03/2025 : 90 jours sur 365 → 3 × 0,247 = 0,74 → 0 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            exit_date=date(2025, 3, 31),
        )
        == 0
    )


def test_absences_sous_le_seuil_nont_aucun_impact():
    """30 jours d'absence : sous le seuil, le droit reste plein."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            absence_days=30,
        )
        == 3
    )


def test_absences_au_dessus_du_seuil_proratisent_la_totalite():
    """31 jours d'absence : seuil franchi → 3 × (365 − 31)/365 = 2,74 → 2 JTC.

    Lecture littérale de la note : les 30 jours sont un seuil de déclenchement,
    pas une franchise. En attente de confirmation d'Elsa.
    """
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            absence_days=31,
        )
        == 2
    )


def test_absence_de_toute_lannee_ne_donne_aucun_jtc():
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            absence_days=365,
        )
        == 0
    )


def test_entree_et_absences_se_cumulent():
    """Entré le 01/07/2025 (184 j) puis 60 j d'absence → 3 × 124/365 = 1,02 → 1 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2025, 7, 1),
            absence_days=60,
        )
        == 1
    )


def test_annee_bissextile_utilise_366_jours():
    """2024 compte 366 jours : entré le 01/07/2024 → 184 j sur 366 → 1 JTC."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2024,
            hire_date=date(2024, 7, 1),
        )
        == 1
    )


def test_le_droit_ne_depasse_jamais_le_maximum_parametre():
    """Même avec des absences négatives ou une présence aberrante, le droit est borné."""
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=date(2015, 3, 1),
            absence_days=-10,
        )
        == 3
    )


def test_droit_annuel_parametrable():
    """Le maximum n'est pas une constante figée : une autre société pourrait en avoir 5."""
    assert (
        calculate_acquired_jtc(
            settings=JtcSettings(enabled=True, annual_days=5),
            reference_year=2025,
            hire_date=date(2015, 3, 1),
        )
        == 5
    )


def test_salarie_sans_date_dembauche_na_aucun_jtc():
    assert (
        calculate_acquired_jtc(
            settings=ACTIVE,
            reference_year=2025,
            hire_date=None,
        )
        == 0
    )
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.absences.domain.jtc'`

- [ ] **Step 3 : Écrire l'implémentation minimale**

Créer `backend/app/modules/absences/domain/jtc.py` :

```python
"""
JTC (Jour de Temps de Change) — droit annuel issu d'un accord d'entreprise.

Note de paramétrage Elsa André du 28/07/2026 : 3 jours par an au maximum pour
une année complète de travail effectif, proratisés sur l'année civile N-1,
arrondis à l'entier inférieur. Le dispositif n'est prévu par aucune convention
de branche : il n'existe que pour les sociétés qui l'ont activé.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date

JTC_ANNUAL_DAYS_DEFAULT = 3
JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT = 30
# Absences citées par la note : maladie, AT, maternité, « et autres absences ».
# L'onglet de détail annoncé n'ayant pas été transmis, les congés sans solde
# tiennent lieu d'« autres absences » jusqu'à confirmation.
JTC_ABSENCE_TYPES_DEFAULT: tuple[str, ...] = (
    "arret_maladie",
    "arret_at",
    "arret_maladie_pro",
    "arret_maternite",
    "sans_solde",
)


@dataclass(frozen=True)
class JtcSettings:
    """Paramètres JTC d'une société. Désactivé par défaut : seule MBC l'active."""

    enabled: bool = False
    annual_days: int = JTC_ANNUAL_DAYS_DEFAULT
    absence_threshold_days: int = JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT
    absence_types: tuple[str, ...] = field(default=JTC_ABSENCE_TYPES_DEFAULT)


def _days_in_year(year: int) -> int:
    return 366 if calendar.isleap(year) else 365


def _presence_days(
    reference_year: int, hire_date: date, exit_date: date | None
) -> int:
    """Jours calendaires de présence du salarié sur l'année de référence."""
    year_start = date(reference_year, 1, 1)
    year_end = date(reference_year, 12, 31)
    start = max(hire_date, year_start)
    end = min(exit_date, year_end) if exit_date else year_end
    if end < start:
        return 0
    return (end - start).days + 1


def calculate_acquired_jtc(
    *,
    settings: JtcSettings,
    reference_year: int,
    hire_date: date | None,
    exit_date: date | None = None,
    absence_days: float = 0.0,
) -> int:
    """
    Droit JTC de l'année N, acquis sur l'activité de `reference_year` (N-1).

    Le droit plein est réduit dans deux cas cumulables : entrée ou sortie en
    cours d'année de référence, et absences dépassant le seuil paramétré. Sous
    le seuil, les absences n'ont aucun effet ; au-dessus, elles sont déduites
    en totalité. Le résultat est arrondi à l'entier inférieur et borné au droit
    annuel.
    """
    if not settings.enabled or hire_date is None:
        return 0

    days_in_year = _days_in_year(reference_year)
    presence = _presence_days(reference_year, hire_date, exit_date)
    if presence <= 0:
        return 0

    deducted = absence_days if absence_days > settings.absence_threshold_days else 0.0
    effective = max(0.0, presence - deducted)

    acquired = settings.annual_days * effective / days_in_year
    return max(0, min(settings.annual_days, int(acquired)))
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc.py -v`

Expected: PASS — 13 tests passés, aucun warning.

- [ ] **Step 5 : Vérifier la non-régression du module absences**

Run: `cd backend && python3 -m pytest tests/unit/absences -q`

Expected: PASS — tous les tests existants restent verts.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/modules/absences/domain/jtc.py backend/tests/unit/absences/test_jtc.py
git commit -m "feat(conges): calcul du droit JTC annuel (note Elsa 28/07)"
```

---

### Task 2 : Paramétrage société et solde d'ouverture salarié

**Files:**
- Create: `supabase/migrations/20260807160000_company_jtc_settings.sql`
- Modify: `backend/app/modules/absences/domain/leave_policy.py`
- Modify: `backend/app/modules/absences/infrastructure/leave_settings_repository.py:18-70`
- Modify: `backend/app/modules/absences/schemas/leave_settings.py:12-55`
- Modify: `backend/app/modules/absences/schemas/leave_settings_responses.py:8-42`
- Modify: `backend/app/modules/absences/application/leave_settings_queries.py:77-107`
- Test: `backend/tests/unit/absences/test_jtc_settings.py`

**Interfaces:**
- Consumes: `JtcSettings`, `JTC_ANNUAL_DAYS_DEFAULT`, `JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT`, `JTC_ABSENCE_TYPES_DEFAULT` (Task 1).
- Produces:
  - `LeavePolicySettings.jtc_enabled: bool`, `.jtc_annual_days: int`, `.jtc_absence_threshold_days: int`, `.jtc_absence_types: tuple[str, ...]`
  - `LeavePolicySettings.jtc_settings` → propriété renvoyant un `JtcSettings`
  - `EmployeeLeaveAdjustment.jtc_opening_balance: float`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `backend/tests/unit/absences/test_jtc_settings.py` :

```python
"""Paramétrage JTC société — repli désactivé, dérivation vers le domaine de calcul."""

from app.modules.absences.domain.jtc import (
    JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT,
    JTC_ANNUAL_DAYS_DEFAULT,
)
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)


def test_jtc_desactive_par_defaut():
    """Aucune société hors MBC ne doit voir de compteur JTC apparaître."""
    policy = LeavePolicySettings()
    assert policy.jtc_enabled is False
    assert policy.jtc_settings.enabled is False


def test_jtc_settings_reprend_les_valeurs_de_la_politique():
    policy = LeavePolicySettings(
        jtc_enabled=True,
        jtc_annual_days=3,
        jtc_absence_threshold_days=30,
    )
    settings = policy.jtc_settings
    assert settings.enabled is True
    assert settings.annual_days == JTC_ANNUAL_DAYS_DEFAULT
    assert settings.absence_threshold_days == JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT


def test_solde_douverture_jtc_par_defaut_nul():
    assert EmployeeLeaveAdjustment.empty().jtc_opening_balance == 0.0
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc_settings.py -v`

Expected: FAIL — `TypeError: LeavePolicySettings.__init__() got an unexpected keyword argument 'jtc_enabled'`

- [ ] **Step 3 : Ajouter les champs au value object**

Dans `backend/app/modules/absences/domain/leave_policy.py`, ajouter l'import en tête de fichier, après les imports existants :

```python
from app.modules.absences.domain.jtc import (
    JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT,
    JTC_ABSENCE_TYPES_DEFAULT,
    JTC_ANNUAL_DAYS_DEFAULT,
    JtcSettings,
)
```

Ajouter dans `LeavePolicySettings`, après `rtt_year_end_reminder_days_before` :

```python
    jtc_enabled: bool = False
    jtc_annual_days: int = JTC_ANNUAL_DAYS_DEFAULT
    jtc_absence_threshold_days: int = JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT
    jtc_absence_types: tuple[str, ...] = JTC_ABSENCE_TYPES_DEFAULT
```

Ajouter la propriété, à la suite de `cp_annual_days_display` :

```python
    @property
    def jtc_settings(self) -> JtcSettings:
        """Vue domaine du paramétrage JTC, pour le calcul du droit annuel."""
        return JtcSettings(
            enabled=self.jtc_enabled,
            annual_days=self.jtc_annual_days,
            absence_threshold_days=self.jtc_absence_threshold_days,
            absence_types=self.jtc_absence_types,
        )
```

Ajouter dans `EmployeeLeaveAdjustment`, après `rtt_forfeited_days` :

```python
    jtc_opening_balance: float = 0.0
```

- [ ] **Step 4 : Lancer le test pour vérifier qu'il passe**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc_settings.py -v`

Expected: PASS — 3 tests passés.

- [ ] **Step 5 : Écrire la migration**

Créer `supabase/migrations/20260807160000_company_jtc_settings.sql` :

```sql
-- JTC (Jour de Temps de Change) — accord d'entreprise propre à Mont Blanc
-- Composite. Aucune convention de branche ne le prévoit : le défaut est donc
-- désactivé, et aucune des sept sociétés ne voit de compteur apparaître tant
-- qu'on ne l'a pas activé explicitement.
--
-- jtc_opening_balance porte le droit de l'année, figé : saisi à la main pour
-- 2026 (EYWAI n'a aucune donnée 2025 pour le recalculer), produit par la
-- commande de calcul de janvier à partir de 2027. Le solde affiché en découle
-- par simple soustraction des jours posés, ce qui exclut tout double compte
-- entre un droit repris et un droit calculé.

ALTER TABLE public.company_leave_settings
    ADD COLUMN IF NOT EXISTS jtc_enabled boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS jtc_annual_days integer NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS jtc_absence_threshold_days integer NOT NULL DEFAULT 30,
    ADD COLUMN IF NOT EXISTS jtc_absence_types text[] NOT NULL
        DEFAULT ARRAY['arret_maladie', 'arret_at', 'arret_maladie_pro',
                      'arret_maternite', 'sans_solde']::text[];

ALTER TABLE public.company_leave_settings
    ADD CONSTRAINT company_leave_settings_jtc_annual_days_positif
        CHECK (jtc_annual_days >= 0 AND jtc_annual_days <= 30);

ALTER TABLE public.company_leave_settings
    ADD CONSTRAINT company_leave_settings_jtc_seuil_absences_positif
        CHECK (jtc_absence_threshold_days >= 0 AND jtc_absence_threshold_days <= 365);

ALTER TABLE public.employee_leave_adjustments
    ADD COLUMN IF NOT EXISTS jtc_opening_balance numeric NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.company_leave_settings.jtc_enabled IS
    'Compteur JTC actif pour la société (accord d''entreprise MBC).';
COMMENT ON COLUMN public.employee_leave_adjustments.jtc_opening_balance IS
    'Droit JTC de l''année, figé en janvier sur les données N-1.';
```

- [ ] **Step 6 : Câbler le repository**

Dans `backend/app/modules/absences/infrastructure/leave_settings_repository.py`, compléter l'import du domaine :

```python
from app.modules.absences.domain.jtc import (
    JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT,
    JTC_ABSENCE_TYPES_DEFAULT,
    JTC_ANNUAL_DAYS_DEFAULT,
)
```

Ajouter à la fin du `return LeavePolicySettings(...)` de `_row_to_policy`, après `rtt_year_end_reminder_days_before` :

```python
        jtc_enabled=bool(row.get("jtc_enabled", False)),
        jtc_annual_days=int(row.get("jtc_annual_days") or JTC_ANNUAL_DAYS_DEFAULT),
        jtc_absence_threshold_days=int(
            row.get("jtc_absence_threshold_days")
            or JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT
        ),
        jtc_absence_types=tuple(
            row.get("jtc_absence_types") or JTC_ABSENCE_TYPES_DEFAULT
        ),
```

Ajouter dans le `return EmployeeLeaveAdjustment(...)` de `_row_to_adjustment`, après `rtt_forfeited_days` :

```python
        jtc_opening_balance=float(row.get("jtc_opening_balance") or 0),
```

- [ ] **Step 7 : Exposer les champs dans l'API**

Dans `backend/app/modules/absences/schemas/leave_settings.py`, ajouter à `LeaveSettingsUpdate` :

```python
    jtc_enabled: Optional[bool] = None
    jtc_annual_days: Optional[int] = Field(None, ge=0, le=30)
    jtc_absence_threshold_days: Optional[int] = Field(None, ge=0, le=365)
```

Ajouter à `EmployeeLeaveAdjustmentUpdate` :

```python
    jtc_opening_balance: Optional[float] = Field(None, ge=0, le=30)
```

Ajouter à `LeaveAdjustmentImportRow` :

```python
    jtc_solde: float = 0.0
```

Dans `backend/app/modules/absences/schemas/leave_settings_responses.py`, ajouter à `LeaveSettingsResponse` :

```python
    jtc_enabled: bool = False
    jtc_annual_days: int = 3
    jtc_absence_threshold_days: int = 30
```

et à `EmployeeLeaveAdjustmentResponse` :

```python
    jtc_opening_balance: float = 0.0
```

Dans `backend/app/modules/absences/application/leave_settings_queries.py`, ajouter dans le `LeaveSettingsResponse(...)` construit par `_policy_to_response` :

```python
        jtc_enabled=policy.jtc_enabled,
        jtc_annual_days=policy.jtc_annual_days,
        jtc_absence_threshold_days=policy.jtc_absence_threshold_days,
```

- [ ] **Step 8 : Vérifier la non-régression**

Run: `cd backend && python3 -m pytest tests/unit/absences -q`

Expected: PASS — aucun test cassé.

- [ ] **Step 9 : Commit**

```bash
git add supabase/migrations/20260807160000_company_jtc_settings.sql \
        backend/app/modules/absences/domain/leave_policy.py \
        backend/app/modules/absences/infrastructure/leave_settings_repository.py \
        backend/app/modules/absences/schemas/leave_settings.py \
        backend/app/modules/absences/schemas/leave_settings_responses.py \
        backend/app/modules/absences/application/leave_settings_queries.py \
        backend/tests/unit/absences/test_jtc_settings.py
git commit -m "feat(conges): paramétrage JTC par société et solde d'ouverture salarié"
```

---

### Task 3 : Type d'absence `jtc`

**Files:**
- Create: `supabase/migrations/20260807160100_absence_type_jtc.sql`
- Modify: `backend/app/modules/absences/domain/enums.py:9-21`
- Modify: `frontend/src/api/absences.ts:30,171`
- Modify: `frontend/src/lib/employeeAbsencesUtils.ts:7,126`
- Modify: `frontend/src/components/AbsenceRequestModal.tsx:64,266,361,379`
- Modify: `frontend/src/pages/rh/Absences.tsx:167`
- Modify: `frontend/src/pages/rh/manager/LeaveRequests.tsx:35`

**Interfaces:**
- Consumes: rien.
- Produces: la valeur `"jtc"` est acceptée partout où un type d'absence est attendu, back et front.

- [ ] **Step 1 : Écrire la migration**

Créer `supabase/migrations/20260807160100_absence_type_jtc.sql` :

```sql
-- Type d'absence JTC. Migration séparée du paramétrage : PostgreSQL interdit
-- d'utiliser une valeur d'enum dans la transaction qui l'ajoute, et une
-- migration ultérieure qui référencerait 'jtc' échouerait si les deux étaient
-- appliquées ensemble.

ALTER TYPE public.absence_type ADD VALUE IF NOT EXISTS 'jtc';
```

- [ ] **Step 2 : Écrire le test qui échoue**

Ajouter à `backend/tests/unit/absences/test_jtc_settings.py` :

```python
def test_jtc_est_un_type_dabsence_connu():
    """Le JTC se pose comme une absence : il doit être un type accepté."""
    from typing import get_args

    from app.modules.absences.domain.enums import AbsenceType

    assert "jtc" in get_args(AbsenceType)
```

- [ ] **Step 3 : Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc_settings.py::test_jtc_est_un_type_dabsence_connu -v`

Expected: FAIL — `AssertionError: assert 'jtc' in ('conge_paye', 'rtt', ...)`

- [ ] **Step 4 : Ajouter le type au domaine**

Dans `backend/app/modules/absences/domain/enums.py`, ajouter `"jtc"` au Literal `AbsenceType`, juste après `"rtt"` :

```python
AbsenceType = Literal[
    "conge_paye",
    "rtt",
    "jtc",
    "sans_solde",
    "repos_compensateur",
    "recuperation_modulation",
    "evenement_familial",
    "arret_maladie",
    "arret_at",
    "arret_paternite",
    "arret_maternite",
    "arret_maladie_pro",
]
```

- [ ] **Step 5 : Lancer le test pour vérifier qu'il passe**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc_settings.py -v`

Expected: PASS — 4 tests passés.

- [ ] **Step 6 : Répercuter côté frontend**

Dans `frontend/src/api/absences.ts`, ajouter `| 'jtc'` aux deux unions de types d'absence (lignes 30 et 171), après `'rtt'`.

Dans `frontend/src/lib/employeeAbsencesUtils.ts`, ajouter au dictionnaire de libellés (ligne 7 environ) :

```typescript
  jtc: 'JTC',
```

et `'jtc',` à la liste des types décomptés (ligne 126 environ).

Dans `frontend/src/components/AbsenceRequestModal.tsx` :
- ajouter `jtc: 'JTC',` aux deux dictionnaires de libellés (lignes 64 et 361) ;
- ajouter `| 'jtc'` à l'union de la ligne 266 ;
- ajouter `{ value: "jtc", label: "JTC" },` à la liste d'options de la ligne 379.

Dans `frontend/src/pages/rh/Absences.tsx` (ligne 167) et `frontend/src/pages/rh/manager/LeaveRequests.tsx` (ligne 35), ajouter `'jtc': 'JTC',` au dictionnaire de libellés.

- [ ] **Step 7 : Vérifier la compilation du frontend**

Run: `cd frontend && npx tsc --noEmit`

Expected: aucune erreur.

- [ ] **Step 8 : Commit**

```bash
git add supabase/migrations/20260807160100_absence_type_jtc.sql \
        backend/app/modules/absences/domain/enums.py \
        backend/tests/unit/absences/test_jtc_settings.py \
        frontend/src/api/absences.ts \
        frontend/src/lib/employeeAbsencesUtils.ts \
        frontend/src/components/AbsenceRequestModal.tsx \
        frontend/src/pages/rh/Absences.tsx \
        frontend/src/pages/rh/manager/LeaveRequests.tsx
git commit -m "feat(conges): type d'absence JTC, back et front"
```

---

### Task 4 : Solde JTC et affichage séparé

**Files:**
- Modify: `backend/app/modules/absences/domain/rules.py:653-808`
- Modify: `backend/app/modules/absences/application/balance_display.py:82-96`
- Modify: `backend/app/modules/absences/application/queries.py:478-486`
- Modify: `backend/app/modules/payroll/documents/bulletin_view.py:211-218`
- Test: `backend/tests/unit/absences/test_jtc_balance.py`

**Interfaces:**
- Consumes: `LeavePolicySettings.jtc_enabled` et `EmployeeLeaveAdjustment.jtc_opening_balance` (Task 2) ; type d'absence `"jtc"` (Task 3) ; les helpers existants `_balance(acquis, pris, solde=...)` et `count_absence_days_taken(requests, type, ref_date, period_start=, period_end=)` de `rules.py`.
- Produces:
  - `compute_jtc_balance(validated_requests: list[dict], ref_date: date, *, policy: LeavePolicySettings | None = None, adjustment: EmployeeLeaveAdjustment | None = None) -> dict[str, float]`
  - clé `"jtc"` dans le dictionnaire renvoyé par `compute_absence_balances`
  - clé `"jtc"` dans le dictionnaire renvoyé par `get_absence_balances_for_payslip`

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/unit/absences/test_jtc_balance.py` :

```python
"""Solde JTC — droit de l'année figé moins jours posés, jamais mêlé aux CP."""

from datetime import date

from app.modules.absences.application.balance_display import balances_to_api_list
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.domain.rules import (
    compute_absence_balances,
    compute_jtc_balance,
)


ACTIVE = LeavePolicySettings(jtc_enabled=True)
REF = date(2026, 6, 30)


def _jtc_request(*days: str) -> dict:
    # `selected_days` est un tableau de dates en base : une liste de chaînes ISO
    # côté Python, pas des dictionnaires (cf. `_parse_absence_day` dans rules.py).
    return {
        "type": "jtc",
        "status": "validated",
        "selected_days": list(days),
    }


def test_sans_activation_le_solde_jtc_est_nul():
    solde = compute_jtc_balance(
        [],
        REF,
        policy=LeavePolicySettings(),
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["acquis"] == 0
    assert solde["solde"] == 0


def test_le_droit_de_lannee_est_le_solde_douverture():
    solde = compute_jtc_balance(
        [],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["acquis"] == 3
    assert solde["pris"] == 0
    assert solde["solde"] == 3


def test_les_jours_poses_sont_decomptes():
    solde = compute_jtc_balance(
        [_jtc_request("2026-03-10")],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["pris"] == 1
    assert solde["solde"] == 2


def test_les_jours_poses_une_autre_annee_ne_comptent_pas():
    """Le JTC se pose sur l'année civile N : un jour de 2025 ne touche pas 2026."""
    solde = compute_jtc_balance(
        [_jtc_request("2025-03-10")],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["pris"] == 0
    assert solde["solde"] == 3


def test_le_solde_ne_devient_jamais_negatif():
    solde = compute_jtc_balance(
        [_jtc_request("2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13")],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert solde["solde"] == 0


def test_le_jtc_nest_pas_ajoute_au_total_des_conges_payes():
    """Exigence explicite de la note : deux compteurs séparés."""
    soldes = compute_absence_balances(
        date(2015, 3, 1),
        [],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=3),
    )
    assert soldes["jtc"]["solde"] == 3
    assert soldes["conges_payes"]["acquis"] == soldes["cp_legal_days"]
    assert "jtc" not in str(soldes["conges_payes"])


def test_la_ligne_jtc_apparait_quand_le_compteur_est_actif():
    soldes = compute_absence_balances(
        date(2015, 3, 1),
        [],
        REF,
        policy=ACTIVE,
        adjustment=EmployeeLeaveAdjustment(jtc_opening_balance=2),
    )
    lignes = balances_to_api_list(soldes, policy=ACTIVE)
    jtc = [ligne for ligne in lignes if ligne["type"] == "JTC"]
    assert len(jtc) == 1
    assert jtc[0]["remaining"] == 2


def test_aucune_ligne_jtc_pour_une_societe_non_concernee():
    """Les six autres sociétés ne doivent pas voir le compteur du tout."""
    policy = LeavePolicySettings()
    soldes = compute_absence_balances(date(2015, 3, 1), [], REF, policy=policy)
    lignes = balances_to_api_list(soldes, policy=policy)
    assert not [ligne for ligne in lignes if ligne["type"] == "JTC"]
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc_balance.py -v`

Expected: FAIL — `ImportError: cannot import name 'compute_jtc_balance' from 'app.modules.absences.domain.rules'`

- [ ] **Step 3 : Implémenter le solde**

Dans `backend/app/modules/absences/domain/rules.py`, ajouter juste après `compute_rtt_balance` (ligne 698) :

```python
def compute_jtc_balance(
    validated_requests: list[dict],
    ref_date: date,
    *,
    policy: LeavePolicySettings | None = None,
    adjustment: EmployeeLeaveAdjustment | None = None,
) -> dict[str, float]:
    """
    Solde JTC de l'année civile en cours.

    Le droit n'est pas recalculé ici : il a été figé en janvier sur les données
    de l'année précédente et vit dans `jtc_opening_balance`. Le solde n'est
    donc que ce droit diminué des jours effectivement posés sur l'année.
    """
    policy = policy or DEFAULT_LEAVE_POLICY
    adjustment = adjustment or EmployeeLeaveAdjustment.empty()

    if not policy.jtc_enabled:
        return _balance(0.0, 0.0)

    acquis = float(adjustment.jtc_opening_balance or 0)
    pris = count_absence_days_taken(
        validated_requests,
        "jtc",
        ref_date,
        period_start=date(ref_date.year, 1, 1),
        period_end=date(ref_date.year, 12, 31),
    )
    return _balance(acquis, pris, solde=max(0.0, round(acquis - pris, 2)))
```

Dans `compute_absence_balances`, ajouter avant le `return` final :

```python
    jtc = compute_jtc_balance(
        validated_requests, ref_date, policy=policy, adjustment=adjustment
    )
```

et la clé dans le dictionnaire retourné, après `"rtt": rtt,` :

```python
        "jtc": jtc,
```

- [ ] **Step 4 : Ajouter la ligne d'affichage**

Dans `backend/app/modules/absences/application/balance_display.py`, ajouter juste après le bloc RTT (ligne 88) :

```python
    if policy.jtc_enabled:
        jtc = _official_balance_row(soldes.get("jtc") or {})
        result.append(
            {
                "type": "JTC",
                **jtc,
            }
        )
```

- [ ] **Step 5 : Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc_balance.py -v`

Expected: PASS — 8 tests passés.

- [ ] **Step 6 : Exposer le solde au bulletin**

Dans `backend/app/modules/absences/application/queries.py`, ajouter à la construction du dictionnaire `balances` de `get_absence_balances_for_payslip`, après `"rtt": autres["rtt"],` :

```python
        "jtc": autres["jtc"],
```

Dans `backend/app/modules/payroll/documents/bulletin_view.py`, ajouter dans `construire_compteurs`, juste après le bloc RTT (ligne 212) :

```python
    if _compteur_alimente(solde.get("jtc")):
        colonnes.append(_colonne_compteur("JTC", solde.get("jtc")))
```

La colonne n'apparaît que si le compteur est alimenté : les bulletins des six autres sociétés sont inchangés.

- [ ] **Step 7 : Vérifier la non-régression complète**

Run: `cd backend && python3 -m pytest tests/unit/absences tests/unit/payroll -q`

Expected: PASS — aucun test cassé, aucun warning.

- [ ] **Step 8 : Commit**

```bash
git add backend/app/modules/absences/domain/rules.py \
        backend/app/modules/absences/application/balance_display.py \
        backend/app/modules/absences/application/queries.py \
        backend/app/modules/payroll/documents/bulletin_view.py \
        backend/tests/unit/absences/test_jtc_balance.py
git commit -m "feat(conges): solde JTC distinct à l'écran et sur le bulletin"
```

---

### Task 5 : Saisie du droit annuel et calcul de janvier

**Files:**
- Modify: `backend/app/modules/absences/application/leave_settings_commands.py`
- Modify: `backend/app/modules/absences/api/router.py`
- Modify: `backend/app/modules/absences/schemas/leave_settings_responses.py`
- Test: `backend/tests/unit/absences/test_jtc_annual_run.py`

**Interfaces:**
- Consumes: `calculate_acquired_jtc`, `JtcSettings` (Task 1) ; `LeavePolicySettings.jtc_settings` (Task 2) ; `upsert_employee_adjustment(employee_id, year, data)` et `list_company_adjustments(company_id, year)` du repository existant.
- Produces:
  - `build_jtc_annual_run(company_id: str, target_year: int, employees: list[dict], absence_days_by_employee: dict[str, float], policy: LeavePolicySettings) -> list[JtcAnnualRunRow]`
  - `JtcAnnualRunRow(employee_id: str, first_name: str, last_name: str, presence_days: int, absence_days: float, acquired_days: int)` — schéma Pydantic de réponse.

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `backend/tests/unit/absences/test_jtc_annual_run.py` :

```python
"""Calcul de janvier : aperçu des droits JTC de l'année, avant application."""

from datetime import date

from app.modules.absences.application.leave_settings_commands import (
    build_jtc_annual_run,
)
from app.modules.absences.domain.leave_policy import LeavePolicySettings


ACTIVE = LeavePolicySettings(jtc_enabled=True)


def _employee(emp_id: str, hire: str, exit_date: str | None = None) -> dict:
    return {
        "id": emp_id,
        "first_name": "Test",
        "last_name": emp_id.upper(),
        "hire_date": hire,
        "exit_date": exit_date,
    }


def test_apercu_du_droit_dune_annee_complete():
    """Droit 2027 calculé sur 2026 : présence pleine → 3 JTC."""
    rows = build_jtc_annual_run(
        company_id="mbc",
        target_year=2027,
        employees=[_employee("a", "2015-03-01")],
        absence_days_by_employee={},
        policy=ACTIVE,
    )
    assert len(rows) == 1
    assert rows[0].acquired_days == 3
    assert rows[0].absence_days == 0


def test_apercu_proratise_lentree_de_lannee_de_reference():
    """Entré le 01/07/2026, droit 2027 calculé sur 2026 → 1 JTC."""
    rows = build_jtc_annual_run(
        company_id="mbc",
        target_year=2027,
        employees=[_employee("a", "2026-07-01")],
        absence_days_by_employee={},
        policy=ACTIVE,
    )
    assert rows[0].acquired_days == 1


def test_apercu_tient_compte_des_absences():
    rows = build_jtc_annual_run(
        company_id="mbc",
        target_year=2027,
        employees=[_employee("a", "2015-03-01")],
        absence_days_by_employee={"a": 120},
        policy=ACTIVE,
    )
    assert rows[0].absence_days == 120
    assert rows[0].acquired_days == 2


def test_societe_non_activee_ne_produit_aucune_ligne():
    rows = build_jtc_annual_run(
        company_id="cartol",
        target_year=2027,
        employees=[_employee("a", "2015-03-01")],
        absence_days_by_employee={},
        policy=LeavePolicySettings(),
    )
    assert rows == []


def test_salarie_sans_date_dembauche_est_ignore():
    rows = build_jtc_annual_run(
        company_id="mbc",
        target_year=2027,
        employees=[{"id": "a", "first_name": "X", "last_name": "Y", "hire_date": None}],
        absence_days_by_employee={},
        policy=ACTIVE,
    )
    assert rows == []
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc_annual_run.py -v`

Expected: FAIL — `ImportError: cannot import name 'build_jtc_annual_run'`

- [ ] **Step 3 : Ajouter le schéma de réponse**

Dans `backend/app/modules/absences/schemas/leave_settings_responses.py`, ajouter :

```python
class JtcAnnualRunRow(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    presence_days: int
    absence_days: float
    acquired_days: int


class JtcAnnualRunResponse(BaseModel):
    target_year: int
    reference_year: int
    rows: List[JtcAnnualRunRow]
```

Si `List` n'est pas déjà importé dans ce fichier, ajouter `from typing import List` en tête.

- [ ] **Step 4 : Implémenter l'aperçu**

Dans `backend/app/modules/absences/application/leave_settings_commands.py`, ajouter les imports nécessaires :

```python
from datetime import date

from app.modules.absences.domain.jtc import calculate_acquired_jtc
from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.absences.schemas.leave_settings_responses import JtcAnnualRunRow
```

puis :

```python
def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def build_jtc_annual_run(
    company_id: str,
    target_year: int,
    employees: list[dict],
    absence_days_by_employee: dict[str, float],
    policy: LeavePolicySettings,
) -> list[JtcAnnualRunRow]:
    """
    Droits JTC de `target_year`, calculés sur l'année civile précédente.

    Renvoie un aperçu : rien n'est écrit tant que la RH n'a pas appliqué.
    """
    if not policy.jtc_enabled:
        return []

    reference_year = target_year - 1
    settings = policy.jtc_settings
    rows: list[JtcAnnualRunRow] = []

    for employee in employees:
        hire_date = _parse_date(employee.get("hire_date"))
        if hire_date is None:
            continue
        employee_id = str(employee.get("id"))
        absence_days = float(absence_days_by_employee.get(employee_id) or 0)
        exit_date = _parse_date(employee.get("exit_date"))
        acquired = calculate_acquired_jtc(
            settings=settings,
            reference_year=reference_year,
            hire_date=hire_date,
            exit_date=exit_date,
            absence_days=absence_days,
        )
        year_start = date(reference_year, 1, 1)
        year_end = date(reference_year, 12, 31)
        start = max(hire_date, year_start)
        end = min(exit_date, year_end) if exit_date else year_end
        presence_days = (end - start).days + 1 if end >= start else 0
        rows.append(
            JtcAnnualRunRow(
                employee_id=employee_id,
                first_name=str(employee.get("first_name") or ""),
                last_name=str(employee.get("last_name") or ""),
                presence_days=presence_days,
                absence_days=absence_days,
                acquired_days=acquired,
            )
        )
    return rows
```

- [ ] **Step 5 : Lancer le test pour vérifier qu'il passe**

Run: `cd backend && python3 -m pytest tests/unit/absences/test_jtc_annual_run.py -v`

Expected: PASS — 5 tests passés.

- [ ] **Step 6 : Exposer les endpoints**

Dans `backend/app/modules/absences/api/router.py`, à la suite des endpoints `/leave-settings`, ajouter un GET d'aperçu et un POST d'application, en reprenant exactement le style de dépendances et de garde d'accès des endpoints voisins (`Depends(get_current_user)`, résolution de `company_id`, contrôle RH). L'aperçu appelle `build_jtc_annual_run` ; l'application boucle sur les lignes retournées et écrit chaque droit via `upsert_employee_adjustment(employee_id, target_year, {"jtc_opening_balance": row.acquired_days})`.

- [ ] **Step 7 : Vérifier la non-régression**

Run: `cd backend && python3 -m pytest tests/unit/absences -q`

Expected: PASS.

- [ ] **Step 8 : Commit**

```bash
git add backend/app/modules/absences/application/leave_settings_commands.py \
        backend/app/modules/absences/api/router.py \
        backend/app/modules/absences/schemas/leave_settings_responses.py \
        backend/tests/unit/absences/test_jtc_annual_run.py
git commit -m "feat(conges): calcul annuel des droits JTC avec aperçu avant application"
```

---

### Task 6 : Paramétrage JTC dans l'interface société

**Files:**
- Modify: `frontend/src/api/leaveSettings.ts:14-57`
- Modify: `frontend/src/features/company/components/LeaveSettingsCard.tsx`

**Interfaces:**
- Consumes: les champs `jtc_enabled`, `jtc_annual_days`, `jtc_absence_threshold_days` de `LeaveSettingsResponse` et `LeaveSettingsUpdate` (Task 2).
- Produces: rien pour d'autres tâches.

- [ ] **Step 1 : Étendre les types de l'API**

Dans `frontend/src/api/leaveSettings.ts`, ajouter à l'interface de réponse :

```typescript
  jtc_enabled: boolean;
  jtc_annual_days: number;
  jtc_absence_threshold_days: number;
```

à l'union des clés modifiables :

```typescript
    | 'jtc_enabled'
    | 'jtc_annual_days'
    | 'jtc_absence_threshold_days'
```

et au type d'ajustement salarié :

```typescript
  jtc_opening_balance: number;
```

- [ ] **Step 2 : Ajouter la section à la carte de paramétrage**

Dans `frontend/src/features/company/components/LeaveSettingsCard.tsx` :

- ajouter les trois clés à l'union de champs éditables (autour de la ligne 78) ;
- initialiser le formulaire (autour de la ligne 87) :

```typescript
    jtc_enabled: form.jtc_enabled ?? false,
    jtc_annual_days: form.jtc_annual_days ?? 3,
    jtc_absence_threshold_days: form.jtc_absence_threshold_days ?? 30,
```

- ajouter une section « JTC » après la section RTT, sur le modèle exact du bloc `rtt_forfait_cadres_only` (Switch + Label + texte d'aide) :

```tsx
<div className="space-y-4 border-t pt-4">
  <div className="flex items-center justify-between">
    <div>
      <Label>Compteur JTC</Label>
      <p className="text-sm text-muted-foreground">
        Jours de temps de change : accord d&apos;entreprise, acquis sur
        l&apos;année précédente. À n&apos;activer que si la société en a un.
      </p>
    </div>
    <Switch
      checked={form.jtc_enabled ?? false}
      onCheckedChange={(v) =>
        setForm((f) => (f ? { ...f, jtc_enabled: v } : f))
      }
    />
  </div>
  {form.jtc_enabled && (
    <div className="grid gap-4 sm:grid-cols-2">
      <div>
        <Label>JTC par an (année complète)</Label>
        <Input
          type="number"
          min={0}
          max={30}
          value={form.jtc_annual_days ?? 3}
          onChange={(e) =>
            setForm((f) =>
              f ? { ...f, jtc_annual_days: Number(e.target.value) } : f,
            )
          }
        />
      </div>
      <div>
        <Label>Seuil d&apos;absences (jours)</Label>
        <Input
          type="number"
          min={0}
          max={365}
          value={form.jtc_absence_threshold_days ?? 30}
          onChange={(e) =>
            setForm((f) =>
              f
                ? { ...f, jtc_absence_threshold_days: Number(e.target.value) }
                : f,
            )
          }
        />
        <p className="text-sm text-muted-foreground">
          En dessous, les absences ne réduisent pas le droit.
        </p>
      </div>
    </div>
  )}
</div>
```

- [ ] **Step 3 : Vérifier la compilation**

Run: `cd frontend && npx tsc --noEmit`

Expected: aucune erreur.

- [ ] **Step 4 : Vérifier le rendu**

Run: `cd frontend && npm run build`

Expected: build réussi.

- [ ] **Step 5 : Commit**

```bash
git add frontend/src/api/leaveSettings.ts \
        frontend/src/features/company/components/LeaveSettingsCard.tsx
git commit -m "feat(conges): paramétrage JTC dans les réglages société"
```

---

## Recette avant déploiement

À jouer sur l'environnement de test, jamais directement en production :

1. Les six sociétés hors MBC n'affichent aucun compteur JTC, ni sur la page Absences, ni sur un bulletin, ni dans les réglages tant que l'interrupteur est fermé.
2. Sur MBC, activer le compteur : la ligne « JTC » apparaît à 0 pour les 75 salariés.
3. Saisir un droit de 3 sur un salarié : le solde affiche 3, à côté du solde CP et jamais additionné à lui.
4. Poser un JTC : le solde tombe à 2, la demande apparaît dans le circuit de validation comme n'importe quelle absence.
5. Générer un bulletin pour ce salarié : la colonne « JTC » figure au bloc compteurs, avec 2 en solde. Générer un bulletin Cartol : aucune colonne JTC.
6. Lancer l'aperçu du calcul annuel pour 2027 : vérifier qu'un salarié entré en cours de 2026 sort proratisé, et qu'aucune écriture n'a lieu tant que l'application n'est pas confirmée.

## Lot 2 — hors périmètre de ce plan

- **Journée de solidarité** (§5 de la note) : imputation automatique d'un JTC, repli sur un CP quand le solde est épuisé.
- **Paiement du solde au départ** (§6) : le solde JTC non pris doit être réglé dans le solde de tout compte. Touche le moteur de paie.
- **Reprise des soldes 2026** : import du fichier d'Elsa dès réception, par le chemin d'import d'ajustements existant, enrichi de la colonne `jtc_solde` prévue en Task 2.
