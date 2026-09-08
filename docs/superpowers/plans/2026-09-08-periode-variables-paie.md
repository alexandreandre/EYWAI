# Période des variables de paie — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** permettre à la gestionnaire de paie de fixer, société par société et mois par mois, la fenêtre sur laquelle sont comptées les heures supplémentaires et les paniers, le reste du bulletin restant sur le mois civil.

**Architecture :** une fenêtre est résolue une seule fois par couple (société, mois) — surcharge stockée, sinon règle `paie_jour_de_fin` / `paie_occurrence` existante — puis lue par les trois consommateurs qui comptent des variables : le moteur de bulletin, l'agrégateur de postes (paniers d'équipe) et le générateur de variables mensuelles. Le moteur reçoit désormais **deux** fenêtres, `periode_mois` et `periode_variables`, et rattache chaque événement à l'une ou l'autre selon son type.

**Tech Stack :** Python 3.12 / FastAPI / Supabase (PostgREST via `app.core.database`), pytest ; React + TypeScript, TanStack Query, vitest.

**Spec :** `docs/superpowers/specs/2026-09-08-periode-variables-paie-design.md`

## État d'exécution — 08/09/2026

Tâches 1 à 10 : **faites**, sur `fix/payslip-edit-state`. 7 082 tests backend,
538 front, `tsc` et lint propres.

Tâche 11 : **bloquée**. Le backtest régénère des bulletins et `backend/.env`
pointe sur la production (`slleauhyjnmiawosvlcg`, le test étant
`tlvkjwleahkmuzcegrde`). Aucun fichier d'environnement de test n'existe.

Trois écarts au plan, assumés :

1. **La migration n'est pas passée par `deploy-test-env.yml`.** Ce workflow
   redéploie aussi backend et frontend depuis la branche, et Gaëlle vérifie ses
   bulletins de juillet sur le test. Migration appliquée seule, en direct.
2. **Pas de test de composant pour le bloc de saisie.** Le front n'a pas de
   pile de test DOM (`environment: "node"`, `.test.ts` seulement, ni jsdom ni
   testing-library). La logique d'affichage est un module pur testé
   (`fenetreVariables.ts`), comme `periodePaie.ts` ; monter une pile de test au
   passage était hors sujet.
3. **La cible du backtest n'est plus 7/7.** Mesure de référence relevée en
   lecture seule (`--dry-run`) sur la production : Colorplast mai 2026 converge
   à **6/7**, avec un écart systémique `smu2_gan_mutuelle_famille` de 98,12 € —
   le sujet GIRERD traité par ailleurs. Le critère devient donc : toujours 6/7,
   le même écart, rien de neuf.

Deux décisions attendues :

- les identifiants du projet de test, pour rejouer le backtest avec le nouveau
  code sans écrire en production ;
- le reparamétrage de Comitech, MBC, Cartol et Lewis en `(4, -2)`. Elles sont
  réglées sur « mois civil » alors que Gaëlle décale leurs variables : sans ce
  changement, le bloc leur proposerait le 1er au 31 et elle devrait tout
  corriger à la main chaque mois.

---

## Global Constraints

- **Le moteur reste généraliste.** Aucune règle spécifique à un salarié ou à une société nommée dans le code : tout passe par un paramètre lu en base.
- **Semaines complètes.** Une fenêtre commence un lundi et se termine un dimanche. Une date de fin saisie en milieu de semaine est ramenée au dimanche de sa semaine (`normaliser_fin_semaine`), jamais tronquée.
- **Continuité.** Le début d'un mois est le lendemain de la fin du mois précédent. Jamais de trou, jamais de recouvrement.
- **Repli identique à l'existant.** Sans surcharge stockée, la fenêtre est exactement celle que `bornes_periode_de_paie(annee, mois, jour_de_fin, occurrence)` produit aujourd'hui. Aucun bulletin ne doit bouger tant que personne n'a saisi de surcharge, à la seule exception du changement de rattachement (tâche 4), couvert par le backtest de la tâche 9.
- **Ordre de déploiement.** La migration de la tâche 2 doit être appliquée sur l'environnement de test **avant** de pousser le code qui lit la table, sinon la CI d'intégration tombe en PGRST205 et bloque le déploiement de production. Workflow : `gh workflow run deploy-test-env.yml --ref main -f migration=20260909090000_company_variable_periods.sql`.
- **Deux fonctions portent le même nom** dans le dépôt, ne pas les confondre :
  - `app.modules.payroll.engine.period_forfait.bornes_periode_de_paie(annee, mois, jour_de_fin, occurrence)` — pure, celle qu'on utilise ;
  - `app.shared.infrastructure.forfait_jour.bornes_periode_de_paie(parametres_paie, year, month)` — enveloppe qui délègue à la première.
- **Tests backend** : lancés depuis `backend/` (`pytest.ini` y pose `pythonpath = .`). **Tests frontend** : lancés depuis `frontend/`.

---

## File Structure

**Créés**

| Fichier | Responsabilité |
|---|---|
| `backend/app/shared/domain/periode_variables.py` | Fonctions pures : normalisation à la semaine, choix entre surcharge et règle, bornes du mois civil. Aucune I/O. |
| `backend/app/modules/payroll/infrastructure/variable_periods_repository.py` | Lecture / écriture de `company_variable_periods`. |
| `backend/app/modules/payroll/application/periode_variables_service.py` | Résout la fenêtre d'un couple (société, mois) en combinant règle société, surcharge du mois et surcharge du mois précédent. Point d'entrée unique des trois consommateurs. |
| `supabase/migrations/20260909090000_company_variable_periods.sql` | Table + RLS. |
| `frontend/src/api/periodeVariables.ts` | Client HTTP. |
| `frontend/src/features/payroll/hooks/usePeriodeVariables.ts` | Hooks TanStack Query (lecture + enregistrement). |
| `frontend/src/features/payroll/components/BlocPeriodeVariables.tsx` | Le bloc de saisie affiché dans la modale de lancement. |

**Modifiés**

| Fichier | Changement |
|---|---|
| `backend/app/modules/payroll/documents/payslip_generator.py` | Injecte `periode_variables` dans `entreprise.json` ; recalcule `shift_payroll_summary` sur la fenêtre. |
| `backend/app/modules/payroll/documents/payslip_run_heures.py` | Calcule les deux fenêtres, charge le calendrier sur leur union. |
| `backend/app/modules/payroll/engine/calcul_brut.py` | Filtre chaque événement selon son type de rattachement. |
| `backend/app/modules/planning/application/shift_payroll_aggregation.py` | Bornes `start` / `end` explicites en option. |
| `backend/app/modules/payroll_variables/application/generate_monthly.py` | Les trois `_month_bounds` deviennent la fenêtre résolue. |
| `backend/app/modules/payroll_variables/api/router.py` | Deux routes : lecture et enregistrement de la fenêtre. |
| `backend/app/modules/payroll/documents/bulletin_view.py` | En-tête au mois civil + ligne « Variables du … au … ». |
| `frontend/src/features/dashboard/widgets/GeneratePayrollModal.tsx` | Insère le bloc sous le sélecteur de mois. |
| `frontend/src/features/company/lib/periodePaie.ts` | Libellés partagés du bloc. |
| `frontend/src/features/employee-detail/components/EmployeeDetailSaisiesTab.tsx` | Rappelle la fenêtre en vigueur — les saisies du mois n'étant pas datées, c'est le seul endroit où l'information peut apparaître. |
| `frontend/src/features/company/components/CompanyPayrollParamsEditCard.tsx` | Signale les mois dont la fenêtre a été corrigée à la main. |

---

### Task 1 : Les fonctions pures de la fenêtre

**Files:**
- Create: `backend/app/shared/domain/periode_variables.py`
- Test: `backend/tests/unit/payroll/test_periode_variables.py`

**Interfaces:**
- Consumes: `app.modules.payroll.engine.period_forfait.bornes_periode_de_paie` (appelée par l'appelant, pas par ce module — ce module reçoit des dates déjà calculées).
- Produces:
  - `normaliser_fin_semaine(jour: date) -> date`
  - `bornes_mois_civil(annee: int, mois: int) -> tuple[date, date]`
  - `FenetreVariables` (dataclass gelée : `debut: date`, `fin: date`, `origine: str`)
  - `resoudre_fenetre(bornes_regle, fin_mois_precedent, surcharge) -> FenetreVariables`
  - `semaines_iso(debut: date, fin: date) -> list[int]`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_periode_variables.py` :

```python
"""Fenêtre des variables (heures sup, paniers) — fonctions pures."""

from __future__ import annotations

from datetime import date

import pytest

from app.shared.domain.periode_variables import (
    FenetreVariables,
    bornes_mois_civil,
    normaliser_fin_semaine,
    resoudre_fenetre,
    semaines_iso,
)

pytestmark = pytest.mark.unit


def test_normalisation_au_dimanche_de_la_semaine():
    """Gaëlle arrête au samedi 25/07 ; la semaine 30 va jusqu'au dimanche 26."""
    assert normaliser_fin_semaine(date(2026, 7, 25)) == date(2026, 7, 26)


def test_normalisation_dun_dimanche_ne_bouge_pas():
    assert normaliser_fin_semaine(date(2026, 7, 26)) == date(2026, 7, 26)


def test_normalisation_dun_lundi_va_au_dimanche_suivant():
    assert normaliser_fin_semaine(date(2026, 7, 20)) == date(2026, 7, 26)


def test_bornes_mois_civil():
    assert bornes_mois_civil(2026, 7) == (date(2026, 7, 1), date(2026, 7, 31))


def test_sans_surcharge_la_regle_sapplique_telle_quelle():
    """Repli : le comportement actuel, à la date près."""
    fenetre = resoudre_fenetre(
        bornes_regle=(date(2026, 6, 22), date(2026, 7, 26)),
        fin_mois_precedent=date(2026, 6, 21),
        surcharge=None,
    )
    assert fenetre == FenetreVariables(
        debut=date(2026, 6, 22), fin=date(2026, 7, 26), origine="regle"
    )


def test_la_surcharge_impose_sa_fin_normalisee():
    """Cartol juillet : Gaëlle a arrêté au 18/07, la semaine 29 finit le 19."""
    fenetre = resoudre_fenetre(
        bornes_regle=(date(2026, 6, 22), date(2026, 7, 26)),
        fin_mois_precedent=date(2026, 6, 21),
        surcharge=date(2026, 7, 18),
    )
    assert fenetre == FenetreVariables(
        debut=date(2026, 6, 22), fin=date(2026, 7, 19), origine="manuel"
    )


def test_le_debut_suit_toujours_la_fin_du_mois_precedent():
    """Cartol août : juillet s'est arrêté au 19, août commence le 20."""
    fenetre = resoudre_fenetre(
        bornes_regle=(date(2026, 7, 27), date(2026, 8, 23)),
        fin_mois_precedent=date(2026, 7, 19),
        surcharge=None,
    )
    assert fenetre.debut == date(2026, 7, 20)
    assert fenetre.fin == date(2026, 8, 23)


def test_pavage_sans_trou_ni_recouvrement():
    juillet = resoudre_fenetre(
        bornes_regle=(date(2026, 6, 22), date(2026, 7, 26)),
        fin_mois_precedent=date(2026, 6, 21),
        surcharge=date(2026, 7, 18),
    )
    aout = resoudre_fenetre(
        bornes_regle=(date(2026, 7, 27), date(2026, 8, 23)),
        fin_mois_precedent=juillet.fin,
        surcharge=None,
    )
    assert (aout.debut - juillet.fin).days == 1


def test_une_fin_anterieure_au_debut_est_refusee():
    with pytest.raises(ValueError, match="antérieure"):
        resoudre_fenetre(
            bornes_regle=(date(2026, 7, 27), date(2026, 8, 23)),
            fin_mois_precedent=date(2026, 8, 30),
            surcharge=None,
        )


def test_semaines_iso_de_la_fenetre():
    assert semaines_iso(date(2026, 6, 22), date(2026, 7, 26)) == [26, 27, 28, 29, 30]
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_periode_variables.py -v
```

Attendu : `ModuleNotFoundError: No module named 'app.shared.domain.periode_variables'`.

- [ ] **Step 3: Écrire l'implémentation minimale**

Créer `backend/app/shared/domain/periode_variables.py` :

```python
"""
La fenêtre des variables d'un bulletin — heures supplémentaires et paniers.

Le bulletin porte le mois civil. Les variables, elles, sont comptées sur des
semaines complètes décalées : la gestionnaire de paie arrête les compteurs
quand elle boucle la paie, et le mois suivant reprend au lundi qui suit. La
règle société (`paie_jour_de_fin` / `paie_occurrence`) fournit la proposition ;
une surcharge mensuelle peut la corriger, jamais rompre la continuité.

Module PUR : aucune I/O, aucune dépendance au moteur. L'appelant fournit les
bornes déjà calculées par la règle.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

#: Origine d'une fenêtre : issue de la règle société, ou corrigée à la main.
ORIGINE_REGLE = "regle"
ORIGINE_MANUEL = "manuel"


@dataclass(frozen=True)
class FenetreVariables:
    """Bornes incluses de la fenêtre, et d'où elles viennent."""

    debut: date
    fin: date
    origine: str


def normaliser_fin_semaine(jour: date) -> date:
    """Dimanche de la semaine qui contient `jour`.

    Une semaine entamée est comptée en entier : la gestionnaire arrête au
    samedi, la semaine va jusqu'au dimanche. C'est la règle du moteur
    (`period_forfait.bornes_periode_de_paie`), reprise ici à l'identique pour
    qu'une saisie manuelle ne puisse pas créer un demi-week-end orphelin.
    """
    return jour + timedelta(days=6 - jour.weekday())


def bornes_mois_civil(annee: int, mois: int) -> tuple[date, date]:
    """Premier et dernier jour du mois."""
    dernier = calendar.monthrange(annee, mois)[1]
    return date(annee, mois, 1), date(annee, mois, dernier)


def semaines_iso(debut: date, fin: date) -> list[int]:
    """Numéros de semaine ISO couverts par la fenêtre, dans l'ordre."""
    numeros: list[int] = []
    jour = debut
    while jour <= fin:
        semaine = jour.isocalendar()[1]
        if semaine not in numeros:
            numeros.append(semaine)
        jour += timedelta(days=7)
    return numeros


def resoudre_fenetre(
    bornes_regle: tuple[date, date],
    fin_mois_precedent: date | None,
    surcharge: date | None,
) -> FenetreVariables:
    """Fenêtre effective d'un mois.

    `bornes_regle` : ce que la règle société produit pour ce mois.
    `fin_mois_precedent` : la fin réellement retenue le mois d'avant (surcharge
    comprise) ; c'est elle qui fixe le début, pas la règle.
    `surcharge` : la date d'arrêt choisie à la main, ou None.
    """
    debut_regle, fin_regle = bornes_regle
    debut = (
        fin_mois_precedent + timedelta(days=1)
        if fin_mois_precedent is not None
        else debut_regle
    )
    fin = normaliser_fin_semaine(surcharge) if surcharge is not None else fin_regle
    if fin < debut:
        raise ValueError(
            f"Fin de fenêtre ({fin:%d/%m/%Y}) antérieure à son début "
            f"({debut:%d/%m/%Y}) : la paie du mois précédent est allée plus loin."
        )
    return FenetreVariables(
        debut=debut,
        fin=fin,
        origine=ORIGINE_MANUEL if surcharge is not None else ORIGINE_REGLE,
    )


__all__ = [
    "FenetreVariables",
    "ORIGINE_MANUEL",
    "ORIGINE_REGLE",
    "bornes_mois_civil",
    "normaliser_fin_semaine",
    "resoudre_fenetre",
    "semaines_iso",
]
```

- [ ] **Step 4: Lancer les tests pour les voir passer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_periode_variables.py -v
```

Attendu : `10 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/shared/domain/periode_variables.py backend/tests/unit/payroll/test_periode_variables.py
git commit -m "feat(paie): fonctions pures de la fenêtre des variables"
```

---

### Task 2 : La table et son dépôt

**Files:**
- Create: `supabase/migrations/20260909090000_company_variable_periods.sql`
- Create: `backend/app/modules/payroll/infrastructure/variable_periods_repository.py`
- Test: `backend/tests/unit/payroll/test_variable_periods_repository.py`

**Interfaces:**
- Consumes: `app.core.database.supabase`
- Produces:
  - `get_variable_period(company_id: str, annee: int, mois: int) -> dict | None`
  - `list_variable_periods(company_id: str, annee: int) -> list[dict]`
  - `upsert_variable_period(company_id: str, annee: int, mois: int, debut: date, fin: date, origine: str, user_id: str | None) -> dict`

Chaque ligne renvoyée porte les clés `start_date` / `end_date` en `str` ISO, comme PostgREST les rend.

- [ ] **Step 1: Écrire la migration**

Créer `supabase/migrations/20260909090000_company_variable_periods.sql` :

```sql
-- Fenêtre des variables (heures sup, paniers) d'une société pour un mois donné.
--
-- Sans ligne ici, la fenêtre reste celle de la règle société
-- (companies.paie_jour_de_fin / paie_occurrence). Une ligne signifie que la
-- gestionnaire de paie a arrêté les compteurs à une autre date ce mois-là.
--
-- Idempotent : ré-exécutable sans erreur.

CREATE TABLE IF NOT EXISTS public.company_variable_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    year smallint NOT NULL,
    month smallint NOT NULL CHECK (month BETWEEN 1 AND 12),
    start_date date NOT NULL,
    end_date date NOT NULL,
    origin text NOT NULL DEFAULT 'manuel' CHECK (origin IN ('regle', 'manuel')),
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT company_variable_periods_bornes CHECK (end_date >= start_date)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_company_variable_periods_unicite
    ON public.company_variable_periods (company_id, year, month);

-- Table qui pilote la paie : aucun accès anonyme ni authentifié direct.
-- La lecture et l'écriture passent par le backend (service role), comme
-- company_work_time_periods depuis le 23/08/2026.
ALTER TABLE public.company_variable_periods ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.company_variable_periods FROM anon, authenticated;
```

- [ ] **Step 2: Écrire le test qui échoue**

Créer `backend/tests/unit/payroll/test_variable_periods_repository.py` :

```python
"""Dépôt des fenêtres de variables — appels PostgREST, client mocké."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture()
def supabase_mock(monkeypatch):
    from app.modules.payroll.infrastructure import variable_periods_repository as repo

    client = MagicMock()
    monkeypatch.setattr(repo, "supabase", client)
    return client


def test_get_variable_period_renvoie_none_sans_ligne(supabase_mock):
    from app.modules.payroll.infrastructure import variable_periods_repository as repo

    chaine = supabase_mock.table.return_value.select.return_value.match.return_value
    chaine.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    assert repo.get_variable_period("c1", 2026, 7) is None
    supabase_mock.table.assert_called_with("company_variable_periods")


def test_get_variable_period_renvoie_la_ligne(supabase_mock):
    from app.modules.payroll.infrastructure import variable_periods_repository as repo

    ligne = {"start_date": "2026-06-22", "end_date": "2026-07-19", "origin": "manuel"}
    chaine = supabase_mock.table.return_value.select.return_value.match.return_value
    chaine.maybe_single.return_value.execute.return_value = MagicMock(data=ligne)

    assert repo.get_variable_period("c1", 2026, 7) == ligne


def test_upsert_envoie_les_dates_en_iso(supabase_mock):
    from app.modules.payroll.infrastructure import variable_periods_repository as repo

    upsert = supabase_mock.table.return_value.upsert
    upsert.return_value.execute.return_value = MagicMock(data=[{"id": "p1"}])

    repo.upsert_variable_period(
        company_id="c1",
        annee=2026,
        mois=7,
        debut=date(2026, 6, 22),
        fin=date(2026, 7, 19),
        origine="manuel",
        user_id="u1",
    )

    payload = upsert.call_args[0][0]
    assert payload["start_date"] == "2026-06-22"
    assert payload["end_date"] == "2026-07-19"
    assert payload["company_id"] == "c1"
    assert payload["year"] == 2026
    assert payload["month"] == 7
    assert payload["origin"] == "manuel"
    assert payload["created_by"] == "u1"
    assert upsert.call_args[1]["on_conflict"] == "company_id,year,month"
```

- [ ] **Step 3: Lancer les tests pour les voir échouer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_variable_periods_repository.py -v
```

Attendu : `ModuleNotFoundError` sur `variable_periods_repository`.

- [ ] **Step 4: Écrire le dépôt**

Créer `backend/app/modules/payroll/infrastructure/variable_periods_repository.py` :

```python
"""Accès à `company_variable_periods` — la fenêtre des variables d'un mois."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.core.database import supabase

TABLE = "company_variable_periods"


def get_variable_period(company_id: str, annee: int, mois: int) -> dict[str, Any] | None:
    """La surcharge du mois, ou None si la règle société s'applique."""
    resp = (
        supabase.table(TABLE)
        .select("*")
        .match({"company_id": str(company_id), "year": int(annee), "month": int(mois)})
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def list_variable_periods(company_id: str, annee: int) -> list[dict[str, Any]]:
    """Toutes les surcharges d'une année, pour l'affichage société."""
    resp = (
        supabase.table(TABLE)
        .select("*")
        .match({"company_id": str(company_id), "year": int(annee)})
        .order("month")
        .execute()
    )
    return resp.data or []


def upsert_variable_period(
    company_id: str,
    annee: int,
    mois: int,
    debut: date,
    fin: date,
    origine: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Pose ou remplace la fenêtre du mois."""
    payload = {
        "company_id": str(company_id),
        "year": int(annee),
        "month": int(mois),
        "start_date": debut.isoformat(),
        "end_date": fin.isoformat(),
        "origin": origine,
        "created_by": str(user_id) if user_id else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = (
        supabase.table(TABLE)
        .upsert(payload, on_conflict="company_id,year,month")
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else payload


__all__ = [
    "get_variable_period",
    "list_variable_periods",
    "upsert_variable_period",
]
```

- [ ] **Step 5: Lancer les tests pour les voir passer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_variable_periods_repository.py -v
```

Attendu : `3 passed`.

- [ ] **Step 6: Appliquer la migration sur l'environnement de test**

```bash
gh workflow run deploy-test-env.yml --ref main -f migration=20260909090000_company_variable_periods.sql
gh run watch "$(gh run list --workflow=deploy-test-env.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status
```

Attendu : run vert. Vérifier ensuite que la table répond :

```bash
cd backend && python -c "
from app.core.database import supabase
print(supabase.table('company_variable_periods').select('id').limit(1).execute().data)
"
```

Attendu : `[]` (et non une erreur PGRST205).

- [ ] **Step 7: Commit**

```bash
git add supabase/migrations/20260909090000_company_variable_periods.sql backend/app/modules/payroll/infrastructure/variable_periods_repository.py backend/tests/unit/payroll/test_variable_periods_repository.py
git commit -m "feat(paie): table company_variable_periods et son dépôt"
```

---

### Task 3 : Le service de résolution

**Files:**
- Create: `backend/app/modules/payroll/application/periode_variables_service.py`
- Test: `backend/tests/unit/payroll/test_periode_variables_service.py`

**Interfaces:**
- Consumes: `resoudre_fenetre`, `bornes_mois_civil`, `semaines_iso`, `FenetreVariables` (tâche 1) ; `get_variable_period`, `upsert_variable_period` (tâche 2) ; `bornes_periode_de_paie` (moteur) ; `periode_de_paie_depuis_societe` (`app.shared.domain.periode_de_paie`).
- Produces:
  - `resoudre_fenetre_variables(company_id: str, annee: int, mois: int, societe: dict | None = None) -> FenetreVariables`
  - `enregistrer_fenetre_variables(company_id, annee, mois, fin: date, user_id: str | None) -> FenetreVariables`
  - `apercu_fenetre(company_id, annee, mois) -> dict` — la charge utile de l'API : `{"debut", "fin", "origine", "semaines", "mois_civil", "report_debut"}`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_periode_variables_service.py` :

```python
"""Résolution de la fenêtre : règle société, surcharge, continuité."""

from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.unit

COLORPLAST = {"id": "c1", "paie_jour_de_fin": 4, "paie_occurrence": -2}
MAJI = {"id": "c2", "paie_jour_de_fin": 31, "paie_occurrence": -1}


@pytest.fixture()
def service(monkeypatch):
    from app.modules.payroll.application import periode_variables_service as svc

    surcharges: dict[tuple[str, int, int], dict] = {}
    societes = {"c1": COLORPLAST, "c2": MAJI}

    monkeypatch.setattr(
        svc, "get_variable_period",
        lambda cid, a, m: surcharges.get((cid, a, m)),
    )
    monkeypatch.setattr(
        svc, "_charger_societe", lambda cid: societes[cid]
    )
    svc._surcharges_de_test = surcharges  # exposé pour les tests
    return svc


def test_sans_surcharge_colorplast_juillet_suit_la_regle(service):
    fenetre = service.resoudre_fenetre_variables("c1", 2026, 7)
    assert (fenetre.debut, fenetre.fin) == (date(2026, 6, 22), date(2026, 7, 26))
    assert fenetre.origine == "regle"


def test_societe_en_mois_civil_na_pas_de_decalage(service):
    fenetre = service.resoudre_fenetre_variables("c2", 2026, 7)
    assert (fenetre.debut, fenetre.fin) == (date(2026, 7, 1), date(2026, 7, 31))


def test_la_surcharge_de_juillet_sapplique(service):
    service._surcharges_de_test[("c1", 2026, 7)] = {
        "start_date": "2026-06-22", "end_date": "2026-07-19", "origin": "manuel",
    }
    fenetre = service.resoudre_fenetre_variables("c1", 2026, 7)
    assert (fenetre.debut, fenetre.fin) == (date(2026, 6, 22), date(2026, 7, 19))
    assert fenetre.origine == "manuel"


def test_aout_reprend_ou_juillet_sest_arrete(service):
    """Cartol : juillet arrêté au 19, août doit commencer le 20."""
    service._surcharges_de_test[("c1", 2026, 7)] = {
        "start_date": "2026-06-22", "end_date": "2026-07-19", "origin": "manuel",
    }
    fenetre = service.resoudre_fenetre_variables("c1", 2026, 8)
    assert fenetre.debut == date(2026, 7, 20)
    assert fenetre.fin == date(2026, 8, 23)


def test_apercu_expose_les_semaines_et_le_mois_civil(service):
    apercu = service.apercu_fenetre("c1", 2026, 7)
    assert apercu["debut"] == "2026-06-22"
    assert apercu["fin"] == "2026-07-26"
    assert apercu["semaines"] == [26, 27, 28, 29, 30]
    assert apercu["mois_civil"] == ["2026-07-01", "2026-07-31"]
    assert apercu["report_debut"] == "2026-07-27"
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_periode_variables_service.py -v
```

Attendu : `ModuleNotFoundError` sur `periode_variables_service`.

- [ ] **Step 3: Écrire le service**

Créer `backend/app/modules/payroll/application/periode_variables_service.py` :

```python
"""
Point d'entrée unique de la fenêtre des variables.

Trois consommateurs l'appellent : le moteur de bulletin, l'agrégateur de postes
(paniers d'équipe) et le générateur de variables mensuelles. Ils doivent lire la
même fenêtre, sinon les heures sup décalent et les paniers non.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.database import supabase
from app.modules.payroll.engine.period_forfait import bornes_periode_de_paie
from app.modules.payroll.infrastructure.variable_periods_repository import (
    get_variable_period,
    upsert_variable_period,
)
from app.shared.domain.periode_de_paie import periode_de_paie_depuis_societe
from app.shared.domain.periode_variables import (
    ORIGINE_MANUEL,
    FenetreVariables,
    bornes_mois_civil,
    normaliser_fin_semaine,
    resoudre_fenetre,
    semaines_iso,
)


def _charger_societe(company_id: str) -> dict[str, Any]:
    resp = (
        supabase.table("companies")
        .select("id, paie_jour_de_fin, paie_occurrence")
        .eq("id", str(company_id))
        .maybe_single()
        .execute()
    )
    return (resp.data if resp else None) or {}


def _mois_precedent(annee: int, mois: int) -> tuple[int, int]:
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def _bornes_regle(societe: dict[str, Any], annee: int, mois: int) -> tuple[date, date]:
    regles = periode_de_paie_depuis_societe(societe)
    return bornes_periode_de_paie(
        annee, mois, regles["jour_de_fin"], regles["occurrence"]
    )


def _fin_retenue(societe: dict[str, Any], company_id: str, annee: int, mois: int) -> date:
    """Fin réellement appliquée à un mois : sa surcharge, sinon sa règle."""
    ligne = get_variable_period(str(company_id), annee, mois)
    if ligne and ligne.get("end_date"):
        return date.fromisoformat(str(ligne["end_date"])[:10])
    return _bornes_regle(societe, annee, mois)[1]


def resoudre_fenetre_variables(
    company_id: str,
    annee: int,
    mois: int,
    societe: dict[str, Any] | None = None,
) -> FenetreVariables:
    """Fenêtre effective des variables pour (société, mois)."""
    societe = societe if societe is not None else _charger_societe(str(company_id))
    bornes = _bornes_regle(societe, annee, mois)

    annee_prec, mois_prec = _mois_precedent(annee, mois)
    fin_precedente = _fin_retenue(societe, str(company_id), annee_prec, mois_prec)

    ligne = get_variable_period(str(company_id), annee, mois)
    surcharge = (
        date.fromisoformat(str(ligne["end_date"])[:10])
        if ligne and ligne.get("end_date")
        else None
    )
    return resoudre_fenetre(
        bornes_regle=bornes,
        fin_mois_precedent=fin_precedente,
        surcharge=surcharge,
    )


def enregistrer_fenetre_variables(
    company_id: str,
    annee: int,
    mois: int,
    fin: date,
    user_id: str | None = None,
) -> FenetreVariables:
    """Enregistre l'arrêt choisi, normalisé à la semaine complète."""
    societe = _charger_societe(str(company_id))
    annee_prec, mois_prec = _mois_precedent(annee, mois)
    debut = _fin_retenue(societe, str(company_id), annee_prec, mois_prec) + timedelta(
        days=1
    )
    fin_normalisee = normaliser_fin_semaine(fin)
    if fin_normalisee < debut:
        raise ValueError(
            f"Fin de fenêtre ({fin_normalisee:%d/%m/%Y}) antérieure à son début "
            f"({debut:%d/%m/%Y})."
        )
    upsert_variable_period(
        company_id=str(company_id),
        annee=annee,
        mois=mois,
        debut=debut,
        fin=fin_normalisee,
        origine=ORIGINE_MANUEL,
        user_id=user_id,
    )
    return FenetreVariables(debut=debut, fin=fin_normalisee, origine=ORIGINE_MANUEL)


def apercu_fenetre(company_id: str, annee: int, mois: int) -> dict[str, Any]:
    """Charge utile de l'API : la fenêtre plus de quoi l'afficher sans recalcul."""
    fenetre = resoudre_fenetre_variables(str(company_id), annee, mois)
    debut_mois, fin_mois = bornes_mois_civil(annee, mois)
    return {
        "debut": fenetre.debut.isoformat(),
        "fin": fenetre.fin.isoformat(),
        "origine": fenetre.origine,
        "semaines": semaines_iso(fenetre.debut, fenetre.fin),
        "mois_civil": [debut_mois.isoformat(), fin_mois.isoformat()],
        "report_debut": (fenetre.fin + timedelta(days=1)).isoformat(),
    }


__all__ = [
    "apercu_fenetre",
    "enregistrer_fenetre_variables",
    "resoudre_fenetre_variables",
]
```

- [ ] **Step 4: Lancer les tests pour les voir passer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_periode_variables_service.py -v
```

Attendu : `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/payroll/application/periode_variables_service.py backend/tests/unit/payroll/test_periode_variables_service.py
git commit -m "feat(paie): service de résolution de la fenêtre des variables"
```

---

### Task 4 : Les deux fenêtres dans le moteur

C'est la tâche qui change un comportement existant. Elle sépare le rattachement : les heures supplémentaires et les paniers suivent la fenêtre, tout le reste — congés, arrêts, fériés, absences — revient au mois civil.

**Files:**
- Modify: `backend/app/modules/payroll/engine/calcul_brut.py:886-902`
- Modify: `backend/app/modules/payroll/documents/payslip_run_heures.py:296-322`
- Modify: `backend/app/modules/payroll/documents/payslip_generator.py:1006-1017`
- Test: `backend/tests/unit/payroll/test_rattachement_deux_fenetres.py`

**Interfaces:**
- Consumes: `resoudre_fenetre_variables` (tâche 3), `bornes_mois_civil` (tâche 1).
- Produces:
  - `app.modules.payroll.engine.calcul_brut.TYPES_RATTACHES_AUX_VARIABLES: frozenset[str]`
  - `calculer_salaire_brut(..., date_debut_variables: date | None = None, date_fin_variables: date | None = None)` — quand les deux sont `None`, le comportement est identique à aujourd'hui.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/payroll/test_rattachement_deux_fenetres.py` :

```python
"""Un événement va sur le bulletin du mois ou sur celui des variables."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import (
    TYPES_RATTACHES_AUX_VARIABLES,
    evenements_de_la_periode,
)

pytestmark = pytest.mark.unit

MOIS = (date(2026, 7, 1), date(2026, 7, 31))
VARIABLES = (date(2026, 6, 22), date(2026, 7, 26))


def _ev(jour: str, type_ev: str, heures: float = 7.0) -> dict:
    return {"date_complete": jour, "type": type_ev, "heures": heures}


def test_les_heures_sup_suivent_la_fenetre_des_variables():
    """Une HS du 24/06 est hors du mois de juillet mais dans la fenêtre."""
    evenements = [_ev("2026-06-24", "travail_hs25", 2.0)]
    retenus = evenements_de_la_periode(evenements, MOIS, VARIABLES)
    assert retenus == evenements


def test_un_conge_du_30_juillet_reste_sur_juillet():
    """Hors fenêtre (qui s'arrête au 26) mais dans le mois : il compte."""
    evenements = [_ev("2026-07-30", "conges_payes")]
    retenus = evenements_de_la_periode(evenements, MOIS, VARIABLES)
    assert retenus == evenements


def test_un_conge_du_24_juin_ne_compte_pas_en_juillet():
    """Dans la fenêtre mais dans le mois de juin : il a été payé en juin."""
    evenements = [_ev("2026-06-24", "conges_payes")]
    retenus = evenements_de_la_periode(evenements, MOIS, VARIABLES)
    assert retenus == []


def test_une_heure_sup_du_30_juillet_bascule_sur_aout():
    """Hors fenêtre : elle sera comptée sur la fenêtre du mois suivant."""
    evenements = [_ev("2026-07-30", "travail_hs25", 3.0)]
    retenus = evenements_de_la_periode(evenements, MOIS, VARIABLES)
    assert retenus == []


def test_sans_fenetre_variables_le_comportement_est_inchange():
    """Repli : une seule fenêtre, celle passée en premier argument."""
    evenements = [_ev("2026-07-30", "travail_hs25"), _ev("2026-06-24", "conges_payes")]
    retenus = evenements_de_la_periode(evenements, MOIS, None)
    assert retenus == [evenements[0]]


def test_une_regularisation_anterieure_passe_toujours():
    evenement = _ev("2026-05-12", "absence_non_remuneree")
    evenement["is_regularisation_anterieure"] = True
    retenus = evenements_de_la_periode([evenement], MOIS, VARIABLES)
    assert retenus == [evenement]


def test_le_catalogue_des_types_variables():
    assert TYPES_RATTACHES_AUX_VARIABLES == frozenset(
        {"travail_hs25", "travail_hs50"}
    )
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_rattachement_deux_fenetres.py -v
```

Attendu : `ImportError: cannot import name 'TYPES_RATTACHES_AUX_VARIABLES'`.

- [ ] **Step 3: Extraire le filtre et le rendre bi-fenêtre**

Dans `backend/app/modules/payroll/engine/calcul_brut.py`, ajouter avant `calculer_salaire_brut` (vers la ligne 595) :

```python
#: Types d'événements comptés sur la fenêtre des variables et non sur le mois
#: civil. Les heures supplémentaires sont les seules heures que la gestionnaire
#: de paie arrête à une date qu'elle choisit ; le salaire de base est
#: mensualisé, et congés, arrêts et fériés appartiennent au mois du bulletin.
TYPES_RATTACHES_AUX_VARIABLES = frozenset({"travail_hs25", "travail_hs50"})


def evenements_de_la_periode(
    calendrier_saisie: List[Dict[str, Any]],
    bornes_mois: tuple[date, date],
    bornes_variables: tuple[date, date] | None,
) -> List[Dict[str, Any]]:
    """Filtre les événements selon la fenêtre qui les concerne.

    `bornes_variables` à None = comportement historique, une seule fenêtre.
    """
    debut_mois, fin_mois = bornes_mois
    retenus: List[Dict[str, Any]] = []
    for evenement in calendrier_saisie:
        if evenement.get("is_regularisation_anterieure"):
            retenus.append(evenement)
            continue
        try:
            date_evenement = date.fromisoformat(evenement["date_complete"])
        except (KeyError, TypeError, ValueError):
            continue
        if bornes_variables is not None and evenement.get("type") in (
            TYPES_RATTACHES_AUX_VARIABLES
        ):
            debut, fin = bornes_variables
        else:
            debut, fin = debut_mois, fin_mois
        if debut <= date_evenement <= fin:
            retenus.append(evenement)
    return retenus
```

Puis remplacer la boucle de filtrage existante (lignes 886-902) par :

```python
    jours_dans_periode = []
    for evenement in evenements_de_la_periode(
        calendrier_saisie,
        (date_debut_periode, date_fin_periode),
        (date_debut_variables, date_fin_variables)
        if date_debut_variables and date_fin_variables
        else None,
    ):
        try:
            date_evenement = date.fromisoformat(evenement["date_complete"])
        except (KeyError, TypeError, ValueError):
            continue
        # Aucun événement ne peut produire de paie hors contrat.
        if date_entree_contrat and date_evenement < date_entree_contrat:
            continue
        if date_sortie_contrat and date_evenement > date_sortie_contrat:
            continue
        jours_dans_periode.append(evenement)
```

Et ajouter les deux paramètres à la signature (ligne 601) :

```python
def calculer_salaire_brut(
    contexte: ContextePaie,
    calendrier_saisie: List[Dict[str, Any]],
    date_debut_periode: date,
    date_fin_periode: date,
    primes_saisies: List[Dict[str, Any]] = None,
    jours_maintien: Optional[set[int]] = None,
    actual_hours_raw: Optional[List[Dict[str, Any]]] = None,
    actual_hours_all_months: Optional[List[Dict[str, Any]]] = None,
    nb_jours_travail_planifies: Optional[int] = None,
    date_debut_variables: Optional[date] = None,
    date_fin_variables: Optional[date] = None,
) -> Dict[str, Any]:
```

- [ ] **Step 4: Lancer les tests pour les voir passer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_rattachement_deux_fenetres.py -v
```

Attendu : `7 passed`.

- [ ] **Step 5: Brancher les deux fenêtres dans le générateur**

Dans `backend/app/modules/payroll/documents/payslip_generator.py`, dans le bloc `parametres_paie` (vers la ligne 1009), ajouter la fenêtre résolue à côté de la règle :

```python
                "parametres_paie": {
                    "idcc": company_data.get("idcc"),
                    "effectif": company_data.get("effectif"),
                    "periode_de_paie": {
                        "jour_de_fin": company_data.get("paie_jour_de_fin", 4),
                        "occurrence": (
                            company_data.get("paie_occurrence")
                            if company_data.get("paie_occurrence") is not None
                            else -2
                        ),
                    },
                    # Fenêtre des variables réellement retenue pour ce mois
                    # (surcharge de la gestionnaire de paie, sinon la règle
                    # ci-dessus). Le moteur s'en sert pour les heures sup ;
                    # le reste du bulletin suit le mois civil.
                    "periode_variables": {
                        "debut": fenetre_variables.debut.isoformat(),
                        "fin": fenetre_variables.fin.isoformat(),
                        "origine": fenetre_variables.origine,
                    },
```

et, juste avant la construction de `entreprise_json_content`, résoudre la fenêtre :

```python
        from app.modules.payroll.application.periode_variables_service import (
            resoudre_fenetre_variables,
        )

        fenetre_variables = resoudre_fenetre_variables(
            str(company_id), year, month, societe=company_data
        )
```

- [ ] **Step 6: Calculer les deux fenêtres dans le run**

Dans `backend/app/modules/payroll/documents/payslip_run_heures.py`, remplacer les lignes 298-322 :

```python
    date_debut_periode, date_fin_periode = definir_periode_de_paie(
        contexte, year, month
    )
```

par :

```python
    from app.shared.domain.periode_variables import bornes_mois_civil

    # Deux fenêtres : le bulletin porte le mois civil, les heures sup et les
    # paniers suivent la fenêtre arrêtée par la gestionnaire de paie.
    fenetre_variables_cfg = (
        contexte.entreprise.get("parametres_paie", {}).get("periode_variables") or {}
    )
    if fenetre_variables_cfg.get("debut") and fenetre_variables_cfg.get("fin"):
        date_debut_variables = date.fromisoformat(fenetre_variables_cfg["debut"])
        date_fin_variables = date.fromisoformat(fenetre_variables_cfg["fin"])
    else:
        # Repli : aucune fenêtre transmise (appel direct du moteur, tests) —
        # la règle société, comme avant.
        date_debut_variables, date_fin_variables = definir_periode_de_paie(
            contexte, year, month
        )

    date_debut_periode, date_fin_periode = bornes_mois_civil(year, month)
    contexte.date_debut_periode = date_debut_periode
    contexte.date_fin_periode = date_fin_periode
    contexte.date_debut_variables = date_debut_variables
    contexte.date_fin_variables = date_fin_variables
    logging.info(
        "Bulletin : %s - %s | variables : %s - %s",
        date_debut_periode.strftime("%d/%m/%Y"),
        date_fin_periode.strftime("%d/%m/%Y"),
        date_debut_variables.strftime("%d/%m/%Y"),
        date_fin_variables.strftime("%d/%m/%Y"),
    )
```

Le calendrier étendu doit couvrir **l'union** des deux fenêtres :

```python
    calendrier_etendu = creer_calendrier_etendu(
        employee_path,
        min(date_debut_periode, date_debut_variables),
        max(date_fin_periode, date_fin_variables),
    )
```

Et l'appel à `calculer_salaire_brut` (vers la ligne 604) reçoit les deux fenêtres :

```python
    resultat_brut = calculer_salaire_brut(
        contexte,
        calendrier_saisie=calendrier_etendu,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
        primes_saisies=primes_soumises,
        jours_maintien=jours_maintien,
        actual_hours_raw=calendrier_du_mois,
        nb_jours_travail_planifies=nb_jours_travail_planifies,
        date_debut_variables=date_debut_variables,
        date_fin_variables=date_fin_variables,
    )
```

Le rattachement du solde de tout compte suit désormais le mois civil : `resolve_exit_state_for_payslip` reçoit `date_debut_periode` / `date_fin_periode`, qui valent maintenant le mois. Aucune ligne à changer à cet endroit, mais c'est ce que le backtest de la tâche 9 doit confirmer.

- [ ] **Step 7: Lancer la suite paie complète**

```bash
cd backend && python -m pytest tests/unit/payroll -q
```

Attendu : aucun échec. Si un test échoue sur un rattachement d'absence, ne pas l'ajuster à la main sans avoir compris lequel des deux comportements est juste : c'est exactement la régression que cette tâche peut introduire.

- [ ] **Step 8: Commit**

```bash
git add backend/app/modules/payroll/engine/calcul_brut.py backend/app/modules/payroll/documents/payslip_run_heures.py backend/app/modules/payroll/documents/payslip_generator.py backend/tests/unit/payroll/test_rattachement_deux_fenetres.py
git commit -m "feat(paie): rattacher les heures sup à la fenêtre et le reste au mois civil"
```

---

### Task 5 : Les paniers d'équipe suivent la fenêtre

Les paniers d'équipe ne passent pas par le calendrier de paie : ils sont agrégés par mois civil à l'enregistrement du planning, mis en cache sur `employee_schedules.payroll_events.shift_payroll_summary`, puis relus tels quels par le bulletin. Sans cette tâche, les heures sup décalent et les paniers non.

**Files:**
- Modify: `backend/app/modules/planning/application/shift_payroll_aggregation.py:15-45`
- Modify: `backend/app/modules/payroll/documents/payslip_generator.py:640-647`
- Test: `backend/tests/unit/payroll/test_paniers_fenetre_variables.py`

**Interfaces:**
- Consumes: `resoudre_fenetre_variables` (tâche 3).
- Produces: `aggregate_shift_payroll_metrics(employee_id, year, month, *, company_id=None, start=None, end=None)` — `start` / `end` sont des `date`; quand ils sont absents, les bornes restent celles du mois civil, comme aujourd'hui.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `backend/tests/unit/payroll/test_paniers_fenetre_variables.py` :

```python
"""Les paniers d'équipe sont comptés sur la fenêtre, pas sur le mois civil."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture()
def supabase_mock(monkeypatch):
    from app.modules.planning.application import shift_payroll_aggregation as agg

    client = MagicMock()
    monkeypatch.setattr(agg, "supabase", client)
    return client


def _bornes_appelees(client) -> tuple[str, str]:
    """(gte, lte) transmis à PostgREST pour shift_date."""
    requete = client.table.return_value.select.return_value
    requete = requete.eq.return_value.eq.return_value.is_.return_value
    return requete.gte.call_args[0][1], requete.gte.return_value.lte.call_args[0][1]


def test_sans_bornes_explicites_on_reste_sur_le_mois(supabase_mock):
    from app.modules.planning.application.shift_payroll_aggregation import (
        aggregate_shift_payroll_metrics,
    )

    aggregate_shift_payroll_metrics("e1", 2026, 7)
    assert _bornes_appelees(supabase_mock) == ("2026-07-01", "2026-07-31")


def test_les_bornes_explicites_priment(supabase_mock):
    from app.modules.planning.application.shift_payroll_aggregation import (
        aggregate_shift_payroll_metrics,
    )

    aggregate_shift_payroll_metrics(
        "e1", 2026, 7, start=date(2026, 6, 22), end=date(2026, 7, 19)
    )
    assert _bornes_appelees(supabase_mock) == ("2026-06-22", "2026-07-19")
```

- [ ] **Step 2: Lancer le test pour le voir échouer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_paniers_fenetre_variables.py -v
```

Attendu : `TypeError: aggregate_shift_payroll_metrics() got an unexpected keyword argument 'start'`.

- [ ] **Step 3: Ajouter les bornes explicites**

Dans `backend/app/modules/planning/application/shift_payroll_aggregation.py`, remplacer la signature et les bornes :

```python
def aggregate_shift_payroll_metrics(
    employee_id: str,
    year: int,
    month: int,
    *,
    company_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> dict[str, Any]:
    """Somme nuit / pause / postes panier pour un salarié sur une période.

    `start` / `end` permettent de compter sur la fenêtre des variables plutôt
    que sur le mois civil — les paniers d'équipe en font partie. Sans elles,
    les bornes restent celles du mois (agrégation planning).
    """
    if start is not None and end is not None:
        borne_debut, borne_fin = start.isoformat(), end.isoformat()
    else:
        borne_debut, borne_fin = _month_bounds(year, month)
    query = (
        supabase.table("shifts")
        .select(
            "id, start_time, end_time, is_locked, transverse_category, "
            "shift_types(code, paid_break_minutes, night_windows, meal_allowance_eligible)"
        )
        .eq("employee_id", employee_id)
        .eq("is_locked", True)
        .is_("transverse_category", "null")
        .gte("shift_date", borne_debut)
        .lte("shift_date", borne_fin)
    )
```

Ajouter l'import `from datetime import date` en tête de fichier s'il n'y est pas déjà.

- [ ] **Step 4: Recalculer le résumé au moment du bulletin**

Dans `backend/app/modules/payroll/documents/payslip_generator.py`, remplacer la lecture du cache (vers la ligne 641) :

```python
        current_schedule = db_data_map.get((year, month)) or {}
        payroll_events_raw = current_schedule.get("payroll_events") or {}
        if isinstance(payroll_events_raw, dict):
            summary = payroll_events_raw.get("shift_payroll_summary")
            if isinstance(summary, dict) and summary:
                saisies_data["shift_payroll_summary"] = summary
```

par :

```python
        # Le cache posé à l'enregistrement du planning compte sur le mois
        # civil ; les paniers d'équipe suivent la fenêtre des variables. On
        # recalcule ici sur la bonne fenêtre plutôt que de relire le cache.
        from app.modules.planning.application.shift_payroll_aggregation import (
            aggregate_shift_payroll_metrics,
        )

        try:
            summary = aggregate_shift_payroll_metrics(
                str(employee_id),
                year,
                month,
                company_id=str(company_id),
                start=fenetre_variables.debut,
                end=fenetre_variables.fin,
            )
        except Exception as agg_exc:  # le bulletin ne tombe pas pour un panier
            logger.warning("Agrégation postes indisponible : %s", agg_exc)
            current_schedule = db_data_map.get((year, month)) or {}
            payroll_events_raw = current_schedule.get("payroll_events") or {}
            summary = (
                payroll_events_raw.get("shift_payroll_summary")
                if isinstance(payroll_events_raw, dict)
                else None
            )
        if isinstance(summary, dict) and summary:
            saisies_data["shift_payroll_summary"] = summary
```

`fenetre_variables` est la variable résolue à la tâche 4, étape 5 : elle doit être calculée **avant** ce bloc dans la fonction.

- [ ] **Step 5: Lancer les tests**

```bash
cd backend && python -m pytest tests/unit/payroll/test_paniers_fenetre_variables.py tests/unit/planning -q
```

Attendu : aucun échec.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/planning/application/shift_payroll_aggregation.py backend/app/modules/payroll/documents/payslip_generator.py backend/tests/unit/payroll/test_paniers_fenetre_variables.py
git commit -m "feat(paie): compter les paniers d'équipe sur la fenêtre des variables"
```

---

### Task 6 : Les variables générées par règle

**Files:**
- Modify: `backend/app/modules/payroll_variables/application/generate_monthly.py:39-41, 231, 262, 415`
- Test: `backend/tests/unit/payroll_variables/test_generate_monthly_fenetre.py`

**Interfaces:**
- Consumes: `resoudre_fenetre_variables` (tâche 3).
- Produces: `_bornes_variables(company_id: str, year: int, month: int) -> tuple[date, date]` — interne au module, remplace les appels à `_month_bounds`.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `backend/tests/unit/payroll_variables/test_generate_monthly_fenetre.py` (créer le dossier et un `__init__.py` vide s'il n'existe pas) :

```python
"""Les règles de variables comptent sur la fenêtre, pas sur le mois civil."""

from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.unit


def test_bornes_variables_suivent_le_service(monkeypatch):
    from app.modules.payroll_variables.application import generate_monthly as gm
    from app.shared.domain.periode_variables import FenetreVariables

    monkeypatch.setattr(
        gm,
        "resoudre_fenetre_variables",
        lambda cid, a, m: FenetreVariables(
            debut=date(2026, 6, 22), fin=date(2026, 7, 19), origine="manuel"
        ),
    )
    assert gm._bornes_variables("c1", 2026, 7) == (date(2026, 6, 22), date(2026, 7, 19))


def test_repli_sur_le_mois_si_la_resolution_echoue(monkeypatch):
    from app.modules.payroll_variables.application import generate_monthly as gm

    def _boum(cid, a, m):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(gm, "resoudre_fenetre_variables", _boum)
    assert gm._bornes_variables("c1", 2026, 7) == (date(2026, 7, 1), date(2026, 7, 31))
```

- [ ] **Step 2: Lancer le test pour le voir échouer**

```bash
cd backend && python -m pytest tests/unit/payroll_variables/test_generate_monthly_fenetre.py -v
```

Attendu : `AttributeError: module ... has no attribute '_bornes_variables'`.

- [ ] **Step 3: Implémenter**

Dans `backend/app/modules/payroll_variables/application/generate_monthly.py`, ajouter après `_month_bounds` :

```python
from app.modules.payroll.application.periode_variables_service import (
    resoudre_fenetre_variables,
)


def _bornes_variables(company_id: str, year: int, month: int) -> tuple[date, date]:
    """Fenêtre sur laquelle les règles de variables comptent.

    Repli sur le mois civil si la résolution échoue : une prime manquante vaut
    mieux qu'une génération qui tombe.
    """
    try:
        fenetre = resoudre_fenetre_variables(str(company_id), year, month)
        return fenetre.debut, fenetre.fin
    except Exception:  # noqa: BLE001 — repli volontaire, cf. docstring
        return _month_bounds(year, month)
```

Puis remplacer les trois `start, end = _month_bounds(year, month)` par `start, end = _bornes_variables(company_id, year, month)` :

- **ligne 415**, dans `generate_monthly_variables` — `company_id` est son premier paramètre, rien d'autre à faire ;
- **ligne 262**, dans `_resolve_quantity` — `company_id` est déjà un de ses paramètres, rien d'autre à faire ;
- **ligne 231**, dans `_count_shift_type_occurrences` — `company_id` n'y est **pas**. Ajouter le paramètre :

```python
def _count_shift_type_occurrences(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    shift_type_codes: list[str] | None,
) -> float:
    start, end = _bornes_variables(company_id, year, month)
```

et corriger son appelant dans `_resolve_quantity` en lui passant `company_id` en deuxième position.

L'appel à `aggregate_shift_payroll_metrics` de la ligne 276 reçoit les mêmes bornes :

```python
        live = aggregate_shift_payroll_metrics(
            eid, year, month, company_id=company_id, start=start, end=end
        )
```

- [ ] **Step 4: Lancer les tests**

```bash
cd backend && python -m pytest tests/unit/payroll_variables -q
```

Attendu : aucun échec.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/payroll_variables/application/generate_monthly.py backend/tests/unit/payroll_variables/
git commit -m "feat(paie): générer les variables mensuelles sur la fenêtre"
```

---

### Task 7 : L'en-tête du bulletin

Le bulletin imprime aujourd'hui les bornes de la fenêtre glissante — d'où le « Du 22/06/2026 Au 26/07/2026 » que Gaëlle a relevé. Il doit porter le mois civil, et mentionner la fenêtre à part.

**Files:**
- Modify: `backend/app/modules/payroll/documents/bulletin_view.py:118-145`
- Test: `backend/tests/unit/payroll/test_bulletin_view.py` (fichier existant, ajouter les cas)

**Interfaces:**
- Produces: la vue d'en-tête gagne la clé `variables` — `str` vide quand la fenêtre est le mois civil, sinon `"du 22/06/2026 au 25/07/2026"`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/unit/payroll/test_bulletin_view.py` :

```python
def test_entete_porte_le_mois_civil_et_pas_la_fenetre():
    from app.modules.payroll.documents.bulletin_view import construire_entete

    vue = construire_entete(
        {
            "annee": 2026,
            "mois": 7,
            "date_debut_periode": "2026-07-01",
            "date_fin_periode": "2026-07-31",
            "date_debut_variables": "2026-06-22",
            "date_fin_variables": "2026-07-26",
        },
        {"raison_sociale": "Colorplast"},
    )
    assert vue["du"] == "01/07/2026"
    assert vue["au"] == "31/07/2026"
    assert vue["variables"] == "du 22/06/2026 au 26/07/2026"


def test_pas_de_ligne_variables_quand_la_fenetre_est_le_mois():
    from app.modules.payroll.documents.bulletin_view import construire_entete

    vue = construire_entete(
        {
            "annee": 2026,
            "mois": 7,
            "date_debut_periode": "2026-07-01",
            "date_fin_periode": "2026-07-31",
            "date_debut_variables": "2026-07-01",
            "date_fin_variables": "2026-07-31",
        },
        {"raison_sociale": "MAJI"},
    )
    assert vue["variables"] == ""
```

La fonction s'appelle `construire_bandeau(bulletin)` et prend le bulletin entier : elle en extrait elle-même `bulletin["en_tete"]`. Les tests ci-dessus doivent donc l'appeler ainsi :

```python
    vue = construire_bandeau(
        {
            "en_tete": {
                "annee": 2026,
                "mois": 7,
                "entreprise": {"raison_sociale": "Colorplast"},
                "date_debut_periode": "2026-07-01",
                "date_fin_periode": "2026-07-31",
                "date_debut_variables": "2026-06-22",
                "date_fin_variables": "2026-07-26",
            }
        }
    )
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

```bash
cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py -v
```

Attendu : `KeyError: 'variables'`.

- [ ] **Step 3: Implémenter**

Dans `bulletin_view.py`, remplacer le calcul de `du` / `au` :

```python
    du = au = ""
    variables = ""
    # Le bulletin porte le mois civil. La fenêtre des variables (heures sup,
    # paniers) s'affiche à part quand elle en diffère, comme le fait Quadra.
    if annee and mois:
        dernier_jour = calendar.monthrange(int(annee), int(mois))[1]
        du = f"01/{int(mois):02d}/{int(annee)}"
        au = f"{dernier_jour:02d}/{int(mois):02d}/{int(annee)}"
    debut_variables = _date_fr(en_tete.get("date_debut_variables"))
    fin_variables = _date_fr(en_tete.get("date_fin_variables"))
    if debut_variables and fin_variables and (debut_variables, fin_variables) != (du, au):
        variables = f"du {debut_variables} au {fin_variables}"
```

et ajouter `"variables": variables,` au dictionnaire retourné par `construire_bandeau`.

Puis le gabarit, `backend/app/runtime/payroll/templates/template_bulletin.html` ligne 76. Remplacer :

```html
                {% if vue.bandeau.du %}<div class="periode">Du : {{ vue.bandeau.du }} &nbsp; Au : {{ vue.bandeau.au }}</div>{% endif %}
```

par :

```html
                {% if vue.bandeau.du %}<div class="periode">Du : {{ vue.bandeau.du }} &nbsp; Au : {{ vue.bandeau.au }}</div>{% endif %}
                {% if vue.bandeau.variables %}<div class="periode">Variables {{ vue.bandeau.variables }}</div>{% endif %}
```

`date_debut_variables` / `date_fin_variables` doivent être écrites dans l'en-tête par le moteur : dans `payslip_run_heures.py`, là où l'en-tête du bulletin est construit, ajouter les deux clés à partir des variables posées à la tâche 4.

- [ ] **Step 4: Lancer les tests**

```bash
cd backend && python -m pytest tests/unit/payroll/test_bulletin_view.py -v
```

Attendu : tous verts.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/payroll/documents/bulletin_view.py backend/app/modules/payroll/documents/payslip_run_heures.py backend/tests/unit/payroll/test_bulletin_view.py
git commit -m "feat(paie): en-tête de bulletin au mois civil, fenêtre des variables à part"
```

---

### Task 8 : Les deux routes API

**Files:**
- Modify: `backend/app/modules/payroll_variables/api/router.py`
- Modify: `backend/app/modules/payroll_variables/schemas/requests.py`
- Test: `backend/tests/integration/payroll_variables/test_variable_period_api.py`

**Interfaces:**
- Consumes: `apercu_fenetre`, `enregistrer_fenetre_variables` (tâche 3) ; `_resolve_company_id`, `_require_rh` (déjà dans le routeur).
- Produces:
  - `GET /api/payroll-variables/period?company_id=&year=&month=` → `PeriodeVariablesSchema`
  - `PUT /api/payroll-variables/period` → corps `PeriodeVariablesUpdate { company_id, year, month, fin }` → `PeriodeVariablesSchema`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `backend/tests/integration/payroll_variables/test_variable_period_api.py` (créer le dossier et son `__init__.py` s'il n'existe pas) :

```python
"""Routes de la fenêtre des variables."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_lecture_de_la_fenetre(client, rh_headers, company_id):
    reponse = client.get(
        "/api/payroll-variables/period",
        params={"company_id": company_id, "year": 2026, "month": 7},
        headers=rh_headers,
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert set(corps) >= {"debut", "fin", "origine", "semaines", "mois_civil"}
    assert corps["mois_civil"] == ["2026-07-01", "2026-07-31"]


def test_enregistrement_normalise_a_la_semaine(client, rh_headers, company_id):
    reponse = client.put(
        "/api/payroll-variables/period",
        json={"company_id": company_id, "year": 2026, "month": 7, "fin": "2026-07-25"},
        headers=rh_headers,
    )
    assert reponse.status_code == 200
    assert reponse.json()["fin"] == "2026-07-26"
    assert reponse.json()["origine"] == "manuel"


def test_une_autre_societe_est_refusee(client, rh_headers):
    reponse = client.get(
        "/api/payroll-variables/period",
        params={
            "company_id": "00000000-0000-0000-0000-000000000000",
            "year": 2026,
            "month": 7,
        },
        headers=rh_headers,
    )
    assert reponse.status_code == 403
```

Les fixtures viennent de `backend/tests/conftest.py` : `client` (TestClient, ligne 30), `auth_headers` (ligne 61) et `test_company_id` (ligne 144). Le test ci-dessus doit donc s'écrire avec `client`, `auth_headers` et `test_company_id` — remplacer `rh_headers` par `auth_headers` et `company_id` par `test_company_id` dans les trois signatures.

- [ ] **Step 2: Lancer le test pour le voir échouer**

```bash
cd backend && python -m pytest tests/integration/payroll_variables/test_variable_period_api.py -v
```

Attendu : `404 Not Found` sur les deux routes.

- [ ] **Step 3: Ajouter les schémas**

Dans `backend/app/modules/payroll_variables/schemas/requests.py` :

```python
class PeriodeVariablesSchema(BaseModel):
    """Fenêtre des variables d'un mois, telle qu'affichée au lancement de paie."""

    debut: str
    fin: str
    origine: str
    semaines: list[int]
    mois_civil: list[str]
    report_debut: str


class PeriodeVariablesUpdate(BaseModel):
    company_id: str | None = None
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    fin: date
```

Ajouter `from datetime import date` en tête si absent.

- [ ] **Step 4: Ajouter les routes**

Dans `backend/app/modules/payroll_variables/api/router.py` :

```python
@router.get("/period", response_model=PeriodeVariablesSchema)
def lire_periode_variables(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Fenêtre en vigueur pour ce mois — surcharge si elle existe, sinon règle."""
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    from app.modules.payroll.application.periode_variables_service import apercu_fenetre

    return apercu_fenetre(cid, year, month)


@router.put("/period", response_model=PeriodeVariablesSchema)
def enregistrer_periode_variables(
    body: PeriodeVariablesUpdate,
    current_user: User = Depends(get_current_user),
):
    """Arrête les variables du mois à la date choisie (semaine complète)."""
    cid = _resolve_company_id(body.company_id, current_user)
    _require_rh(current_user, cid)
    from app.modules.payroll.application.periode_variables_service import (
        apercu_fenetre,
        enregistrer_fenetre_variables,
    )

    try:
        enregistrer_fenetre_variables(
            cid, body.year, body.month, body.fin, user_id=str(current_user.id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return apercu_fenetre(cid, body.year, body.month)
```

Ajouter `PeriodeVariablesSchema` et `PeriodeVariablesUpdate` à l'import des schémas en tête de fichier.

- [ ] **Step 5: Lancer les tests**

```bash
cd backend && python -m pytest tests/integration/payroll_variables -v
```

Attendu : `3 passed`.

- [ ] **Step 6: Le snapshot des routes**

L'ajout de routes casse le test de snapshot d'API. Le régénérer :

```bash
cd backend && python -m pytest tests/integration -k "route" -q
```

Si un test de snapshot échoue, suivre la procédure indiquée dans son message d'erreur pour le mettre à jour, puis relancer.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/payroll_variables/ backend/tests/integration/payroll_variables/
git commit -m "feat(paie): routes de lecture et d'enregistrement de la fenêtre des variables"
```

---

### Task 9 : Le bloc de saisie au lancement de la paie

**Files:**
- Create: `frontend/src/api/periodeVariables.ts`
- Create: `frontend/src/features/payroll/hooks/usePeriodeVariables.ts`
- Create: `frontend/src/features/payroll/components/BlocPeriodeVariables.tsx`
- Modify: `frontend/src/features/dashboard/widgets/GeneratePayrollModal.tsx:253-266`
- Modify: `frontend/src/lib/queryKeys.ts`
- Test: `frontend/src/features/payroll/components/BlocPeriodeVariables.test.tsx`

**Interfaces:**
- Consumes: `GET`/`PUT /api/payroll-variables/period` (tâche 8).
- Produces:
  - `PeriodeVariables` (type) : `{ debut: string; fin: string; origine: 'regle' | 'manuel'; semaines: number[]; mois_civil: [string, string]; report_debut: string }`
  - `getPeriodeVariables(year, month)`, `putPeriodeVariables(year, month, fin)`
  - `usePeriodeVariables(year, month, enabled)`, `useEnregistrerPeriodeVariables()`
  - `<BlocPeriodeVariables year={number} month={number} />`

- [ ] **Step 1: Écrire le client HTTP**

Créer `frontend/src/api/periodeVariables.ts` :

```typescript
import apiClient from '@/api/apiClient';

/** Fenêtre sur laquelle les heures sup et les paniers d'un mois sont comptés. */
export interface PeriodeVariables {
  debut: string;
  fin: string;
  origine: 'regle' | 'manuel';
  semaines: number[];
  mois_civil: [string, string];
  report_debut: string;
}

export async function getPeriodeVariables(
  year: number,
  month: number,
): Promise<PeriodeVariables> {
  const { data } = await apiClient.get<PeriodeVariables>('/api/payroll-variables/period', {
    params: { year, month },
  });
  return data;
}

export async function putPeriodeVariables(
  year: number,
  month: number,
  fin: string,
): Promise<PeriodeVariables> {
  const { data } = await apiClient.put<PeriodeVariables>('/api/payroll-variables/period', {
    year,
    month,
    fin,
  });
  return data;
}
```

- [ ] **Step 2: Écrire les hooks**

Ajouter à `frontend/src/lib/queryKeys.ts`, à côté de `payrollPreflight` :

```typescript
  periodeVariables: (companyId: string | undefined, year: number, month: number) =>
    ['periode-variables', companyId, year, month] as const,
```

Créer `frontend/src/features/payroll/hooks/usePeriodeVariables.ts` :

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getPeriodeVariables, putPeriodeVariables } from '@/api/periodeVariables';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';

export function usePeriodeVariables(year: number, month: number, enabled = true) {
  const companyId = useActiveCompanyId();

  return useQuery({
    queryKey: queryKeys.periodeVariables(companyId, year, month),
    queryFn: () => getPeriodeVariables(year, month),
    enabled: enabled && year > 0 && month >= 1 && month <= 12,
    staleTime: 30_000,
  });
}

export function useEnregistrerPeriodeVariables(year: number, month: number) {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (fin: string) => putPeriodeVariables(year, month, fin),
    onSuccess: (data) => {
      queryClient.setQueryData(
        queryKeys.periodeVariables(companyId, year, month),
        data,
      );
    },
  });
}
```

- [ ] **Step 3: Écrire le test du bloc, qui échoue**

Créer `frontend/src/features/payroll/components/BlocPeriodeVariables.test.tsx` :

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BlocPeriodeVariables } from './BlocPeriodeVariables';

vi.mock('../hooks/usePeriodeVariables', () => ({
  usePeriodeVariables: () => ({
    data: {
      debut: '2026-06-22',
      fin: '2026-07-26',
      origine: 'regle',
      semaines: [26, 27, 28, 29, 30],
      mois_civil: ['2026-07-01', '2026-07-31'],
      report_debut: '2026-07-27',
    },
    isLoading: false,
  }),
  useEnregistrerPeriodeVariables: () => ({ mutate: vi.fn(), isPending: false }),
}));

describe('BlocPeriodeVariables', () => {
  it('affiche la fenêtre, ses semaines et le report', () => {
    render(<BlocPeriodeVariables year={2026} month={7} />);

    expect(screen.getByText(/22\/06\/2026/)).toBeInTheDocument();
    expect(screen.getByText(/26\/07\/2026/)).toBeInTheDocument();
    expect(screen.getByText(/semaines 26 à 30/i)).toBeInTheDocument();
    expect(screen.getByText(/27\/07\/2026/)).toBeInTheDocument();
  });

  it('verrouille le début', () => {
    render(<BlocPeriodeVariables year={2026} month={7} />);
    expect(screen.getByText(/suite du mois précédent/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Lancer le test pour le voir échouer**

```bash
cd frontend && npx vitest run src/features/payroll/components/BlocPeriodeVariables.test.tsx
```

Attendu : `Failed to resolve import "./BlocPeriodeVariables"`.

- [ ] **Step 5: Écrire le composant**

Créer `frontend/src/features/payroll/components/BlocPeriodeVariables.tsx` :

```tsx
import { useState } from 'react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  usePeriodeVariables,
  useEnregistrerPeriodeVariables,
} from '../hooks/usePeriodeVariables';

const formatFr = (iso: string): string => {
  const [a, m, j] = iso.split('-');
  return `${j}/${m}/${a}`;
};

const libelleSemaines = (semaines: number[]): string => {
  if (semaines.length === 0) return '';
  if (semaines.length === 1) return `semaine ${semaines[0]}`;
  return `semaines ${semaines[0]} à ${semaines[semaines.length - 1]}`;
};

interface Props {
  year: number;
  month: number;
}

/**
 * Fenêtre des heures sup et des paniers pour le mois lancé.
 *
 * Le début n'est pas modifiable : il est la suite du mois précédent, et c'est
 * ce qui garantit qu'aucune semaine n'est ni perdue ni payée deux fois. Seule
 * la date d'arrêt se choisit, et elle est ramenée à la semaine complète.
 */
export function BlocPeriodeVariables({ year, month }: Props) {
  const { data, isLoading } = usePeriodeVariables(year, month);
  const enregistrer = useEnregistrerPeriodeVariables(year, month);
  const [finSaisie, setFinSaisie] = useState<string>('');

  if (isLoading || !data) return null;

  const surLeMoisCivil =
    data.debut === data.mois_civil[0] && data.fin === data.mois_civil[1];

  return (
    <div className="rounded-md border p-3 space-y-2">
      <Label className="text-sm font-medium">Variables (heures sup et paniers)</Label>

      {surLeMoisCivil ? (
        <p className="text-sm text-muted-foreground">
          Mois civil — du {formatFr(data.mois_civil[0])} au {formatFr(data.mois_civil[1])}.
        </p>
      ) : (
        <>
          <p className="text-sm">
            Du <strong>{formatFr(data.debut)}</strong> au{' '}
            <strong>{formatFr(data.fin)}</strong> — {libelleSemaines(data.semaines)}.
          </p>
          <p className="text-xs text-muted-foreground">
            Le début est la suite du mois précédent et n'est pas modifiable.
          </p>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Label htmlFor="fin-variables" className="text-xs">
                J'arrête les variables le
              </Label>
              <Input
                id="fin-variables"
                type="date"
                value={finSaisie || data.fin}
                min={data.debut}
                onChange={(e) => setFinSaisie(e.target.value)}
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              disabled={enregistrer.isPending || !finSaisie || finSaisie === data.fin}
              onClick={() => enregistrer.mutate(finSaisie)}
            >
              Appliquer
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            La semaine entamée est comptée en entier. Ce qui suit le{' '}
            {formatFr(data.fin)} partira sur le mois suivant, à partir du{' '}
            {formatFr(data.report_debut)}.
          </p>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Lancer le test pour le voir passer**

```bash
cd frontend && npx vitest run src/features/payroll/components/BlocPeriodeVariables.test.tsx
```

Attendu : `2 passed`.

- [ ] **Step 7: Insérer le bloc dans la modale**

Dans `frontend/src/features/dashboard/widgets/GeneratePayrollModal.tsx`, juste après le `<Select>` du mois (vers la ligne 266), ajouter :

```tsx
            {selectedMonth && parsedMonth.year > 0 && (
              <div className="mt-3">
                <BlocPeriodeVariables
                  year={parsedMonth.year}
                  month={parsedMonth.month}
                />
              </div>
            )}
```

et l'import correspondant :

```tsx
import { BlocPeriodeVariables } from '@/features/payroll/components/BlocPeriodeVariables';
```

- [ ] **Step 8: Vérifier la compilation et le lint**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

Attendu : aucune erreur.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/periodeVariables.ts frontend/src/features/payroll/hooks/usePeriodeVariables.ts frontend/src/features/payroll/components/BlocPeriodeVariables.tsx frontend/src/features/payroll/components/BlocPeriodeVariables.test.tsx frontend/src/features/dashboard/widgets/GeneratePayrollModal.tsx frontend/src/lib/queryKeys.ts
git commit -m "feat(paie): bloc de saisie de la fenêtre des variables au lancement"
```

---

### Task 10 : Les deux rappels de la fenêtre ailleurs dans l'application

Les saisies de `monthly_inputs` — heures sup conjoncturelles, paniers saisis à la main, primes — n'ont pas de date : aucune fenêtre ne peut les découper. Elles valent pour la paie du mois, telles que la gestionnaire les saisit. On ne change rien à leur traitement, mais l'écran doit dire sur quelle période elle compte. Et la fiche société doit cesser d'annoncer un régime que la surcharge du mois a corrigé.

**Files:**
- Modify: `backend/app/modules/payroll_variables/api/router.py`
- Modify: `frontend/src/api/periodeVariables.ts`
- Modify: `frontend/src/features/payroll/hooks/usePeriodeVariables.ts`
- Modify: `frontend/src/features/employee-detail/components/EmployeeDetailSaisiesTab.tsx:31-33`
- Modify: `frontend/src/features/company/components/CompanyPayrollParamsEditCard.tsx:102-114`
- Test: `frontend/src/features/payroll/hooks/usePeriodeVariables.test.ts`

**Interfaces:**
- Consumes: `list_variable_periods` (tâche 2), `usePeriodeVariables` (tâche 9).
- Produces:
  - `GET /api/payroll-variables/periods?company_id=&year=` → `list[PeriodeVariablesSurcharge]` avec `{ month: int, debut: str, fin: str }`
  - `getSurchargesPeriodeVariables(year)` et `useSurchargesPeriodeVariables(year)` côté front.

- [ ] **Step 1: Ajouter la route de listage**

Dans `backend/app/modules/payroll_variables/schemas/requests.py` :

```python
class PeriodeVariablesSurcharge(BaseModel):
    """Un mois dont la fenêtre a été corrigée à la main."""

    month: int
    debut: str
    fin: str
```

Dans `backend/app/modules/payroll_variables/api/router.py` :

```python
@router.get("/periods", response_model=list[PeriodeVariablesSurcharge])
def lister_surcharges_periode_variables(
    year: int = Query(..., ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Mois de l'année dont la fenêtre a été corrigée à la main."""
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    from app.modules.payroll.infrastructure.variable_periods_repository import (
        list_variable_periods,
    )

    return [
        {
            "month": int(ligne["month"]),
            "debut": str(ligne["start_date"])[:10],
            "fin": str(ligne["end_date"])[:10],
        }
        for ligne in list_variable_periods(cid, year)
    ]
```

- [ ] **Step 2: Vérifier la route**

```bash
cd backend && python -m pytest tests/integration/payroll_variables -q
```

Attendu : aucun échec (le snapshot de routes peut redemander une mise à jour, même procédure qu'à la tâche 8).

- [ ] **Step 3: Étendre le client et les hooks**

Ajouter à `frontend/src/api/periodeVariables.ts` :

```typescript
export interface PeriodeVariablesSurcharge {
  month: number;
  debut: string;
  fin: string;
}

export async function getSurchargesPeriodeVariables(
  year: number,
): Promise<PeriodeVariablesSurcharge[]> {
  const { data } = await apiClient.get<PeriodeVariablesSurcharge[]>(
    '/api/payroll-variables/periods',
    { params: { year } },
  );
  return data;
}
```

Ajouter à `frontend/src/features/payroll/hooks/usePeriodeVariables.ts` :

```typescript
export function useSurchargesPeriodeVariables(year: number) {
  const companyId = useActiveCompanyId();

  return useQuery({
    queryKey: [...queryKeys.periodeVariables(companyId, year, 0), 'surcharges'],
    queryFn: () => getSurchargesPeriodeVariables(year),
    enabled: year > 0,
    staleTime: 60_000,
  });
}
```

et compléter l'import : `import { getPeriodeVariables, getSurchargesPeriodeVariables, putPeriodeVariables } from '@/api/periodeVariables';`

- [ ] **Step 4: Rappeler la fenêtre sur l'écran de saisie**

Dans `frontend/src/features/employee-detail/components/EmployeeDetailSaisiesTab.tsx`, remplacer la description de la carte (ligne 32) :

```tsx
                <CardDescription>Primes, acomptes et autres variables pour la paie de ce mois.</CardDescription>
```

par :

```tsx
                <CardDescription>
                  Primes, acomptes et autres variables pour la paie de ce mois.
                  {fenetre && !surLeMoisCivil && (
                    <>
                      {' '}Heures sup et paniers sont comptés du{' '}
                      {formatFr(fenetre.debut)} au {formatFr(fenetre.fin)}.
                    </>
                  )}
                </CardDescription>
```

en ajoutant en tête du composant :

```tsx
import { usePeriodeVariables } from '@/features/payroll/hooks/usePeriodeVariables';

const formatFr = (iso: string): string => {
  const [a, m, j] = iso.split('-');
  return `${j}/${m}/${a}`;
};
```

et dans le corps, avant le `return` :

```tsx
  const { data: fenetre } = usePeriodeVariables(selectedDate.year, selectedDate.month);
  const surLeMoisCivil =
    !!fenetre &&
    fenetre.debut === fenetre.mois_civil[0] &&
    fenetre.fin === fenetre.mois_civil[1];
```

- [ ] **Step 5: Signaler les surcharges sur la fiche société**

Dans `frontend/src/features/company/components/CompanyPayrollParamsEditCard.tsx`, sous la description du régime (après la ligne 113, `{DESCRIPTIONS_REGIME_PERIODE_PAIE[regime]}`), ajouter :

```tsx
              {surcharges && surcharges.length > 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  Fenêtre corrigée à la main sur{' '}
                  {surcharges.length === 1 ? 'le mois' : 'les mois'} de{' '}
                  {surcharges
                    .map((s) =>
                      new Date(anneeCourante, s.month - 1).toLocaleString('fr-FR', {
                        month: 'long',
                      }),
                    )
                    .join(', ')}
                  .
                </p>
              )}
```

avec, en tête du composant :

```tsx
import { useSurchargesPeriodeVariables } from '@/features/payroll/hooks/usePeriodeVariables';
```

et dans le corps :

```tsx
  const anneeCourante = new Date().getFullYear();
  const { data: surcharges } = useSurchargesPeriodeVariables(anneeCourante);
```

- [ ] **Step 6: Vérifier la compilation, le lint et les tests front**

```bash
cd frontend && npx tsc --noEmit && npm run lint && npm test
```

Attendu : aucune erreur, aucun test rouge.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/payroll_variables/ frontend/src/api/periodeVariables.ts frontend/src/features/payroll/hooks/usePeriodeVariables.ts frontend/src/features/employee-detail/components/EmployeeDetailSaisiesTab.tsx frontend/src/features/company/components/CompanyPayrollParamsEditCard.tsx
git commit -m "feat(paie): rappeler la fenêtre des variables sur les écrans de saisie et de société"
```

---

### Task 11 : La preuve sur les vraies données

Aucune de ces tâches n'est terminée tant que ces quatre vérifications ne sont pas passées. Elles tournent **en session directe**, pas dans un sous-agent : un backtest dépasse le chien de garde.

**Files:**
- Test: aucune création — exécution des outils existants.

- [ ] **Step 1: La suite complète**

```bash
cd backend && python -m pytest tests/unit -q && python -m pytest tests/integration -q -m "not e2e"
```

Attendu : aucun échec.

- [ ] **Step 2: Le backtest Colorplast mai 2026**

C'est le garde-fou du changement de rattachement : le mois convergeait déjà à 7/7 au centime avec l'ancien découpage, il doit converger à l'identique.

```bash
cd backend && python -m pytest tests/unit/payroll/backtest -q
```

Puis le backtest réel contre les bulletins du cabinet :

```bash
cd backend && .venv/bin/python -m scripts.backtest.backtest_company_payroll \
  --company Colorplast --year 2026 --month 5
```

Attendu : **7/7 bulletins à ±0,05 €**. Tout écart nouveau est une régression de la tâche 4 : ne pas ajuster le moteur pour le masquer, remonter la cause.

- [ ] **Step 3: Le panier qui change de mois**

Sur l'environnement de test, chez une société à postes : poser un poste verrouillé ouvrant droit au panier le 28/07/2026, régénérer juillet puis août.

Attendu : le panier n'apparaît pas sur juillet (fenêtre arrêtée au 26/07) et apparaît sur août. C'est le test qui prouve que le moteur, l'agrégateur de postes et le générateur de variables lisent la même fenêtre.

- [ ] **Step 4: Le rejeu de juillet**

Saisir les cinq fenêtres de juillet 2026 via la modale, sur l'environnement de test :

| société | arrêt saisi | fenêtre stockée |
|---|---|---|
| Colorplast, Comitech, MBC | 25/07/2026 | 22/06 → 26/07 |
| Cartol, Lewis | 18/07/2026 | 22/06 → 19/07 |

**Sauvegarder les bulletins de juillet avant de régénérer** — un mois rejoué applique les données du jour, pas celles d'origine.

```bash
cd backend && python -c "
from app.core.database import supabase
import json, pathlib
lignes = supabase.table('payslips').select('*').eq('year', 2026).eq('month', 7).execute().data
pathlib.Path('/tmp/sauvegarde_payslips_2026_07.json').write_text(json.dumps(lignes, default=str))
print(len(lignes), 'bulletins sauvegardés')
"
```

Puis régénérer et vérifier que les heures sup et paniers de Cartol et Lewis s'arrêtent bien au 19/07.

- [ ] **Step 5: Commit final**

```bash
git add -A docs/superpowers/plans/2026-09-08-periode-variables-paie.md
git commit -m "docs(paie): plan de la période des variables exécuté"
```
